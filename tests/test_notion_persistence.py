"""
Notion DB Persistence / State Integrity 修正のためのUnit / Regression Tests.

このテストはNotionへは一切書き込まない。requests.post/patchを
unittest.mock.patchで差し替え、実際のHTTP通信を発生させない。

google-genai が利用可能な環境では実ライブラリを使用する。未導入の限定環境だけ、
pipeline.py のimportに必要な最小限のスタブへフォールバックする。
"""
import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.models = MagicMock()


class _FakeAPIError(Exception):
    pass


def _ensure_google_genai_available(import_module=importlib.import_module, modules=None):
    """実SDKを優先し、ImportErrorのときだけ最小Stubを登録する。"""
    modules = sys.modules if modules is None else modules
    try:
        import_module("google.genai")
        import_module("google.genai.errors")
        return False
    except ImportError:
        # 既存のgoogle namespace packageは上書きしない。
        google_pkg = modules.get("google")
        if google_pkg is None:
            google_pkg = types.ModuleType("google")
            google_pkg.__path__ = []
            modules["google"] = google_pkg

        genai_mod = modules.get("google.genai")
        if genai_mod is None:
            genai_mod = types.ModuleType("google.genai")
            modules["google.genai"] = genai_mod
        if not hasattr(genai_mod, "Client"):
            genai_mod.Client = _FakeClient

        errors_mod = modules.get("google.genai.errors")
        if errors_mod is None:
            errors_mod = types.ModuleType("google.genai.errors")
            modules["google.genai.errors"] = errors_mod
        if not hasattr(errors_mod, "APIError"):
            errors_mod.APIError = _FakeAPIError
        setattr(genai_mod, "errors", errors_mod)
        setattr(google_pkg, "genai", genai_mod)
        return True


# google-genaiが導入済みならsys.modulesを書き換えない。
_GOOGLE_GENAI_STUB_ACTIVE = _ensure_google_genai_available()

# --- pipeline.py が import 時点で依存する環境変数（Notion未設定のFail-Safe動作を
# テストしたいので、あえて NOTION_API_KEY 等は未設定のままにする） ---
os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "false")

# pipeline.py の場所を解決する。
# このテストファイルと同じディレクトリに置かれるケース（従来）と、
# リポジトリの tests/ 配下に置かれ pipeline.py がリポジトリルートにあるケースの
# 両方に対応するため、テストファイル自身のディレクトリと、その1つ上の
# ディレクトリ（tests/ の親 = リポジトリルート想定）の両方をsys.pathへ追加する。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
for _candidate_dir in (_THIS_DIR, _PARENT_DIR):
    if _candidate_dir not in sys.path:
        sys.path.insert(0, _candidate_dir)
import pipeline  # noqa: E402


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


class TestGoogleGenaiStubSafety(unittest.TestCase):
    """実SDK優先と、未導入時だけの最小Stubを回帰テストする。"""

    def test_available_sdk_is_not_replaced(self):
        real_genai = types.ModuleType("google.genai")
        real_genai.Client = object
        real_errors = types.ModuleType("google.genai.errors")
        real_errors.APIError = RuntimeError
        available = {"google.genai": real_genai, "google.genai.errors": real_errors}

        self.assertFalse(_ensure_google_genai_available(available.__getitem__, {}))
        self.assertIsNot(real_genai.Client, _FakeClient)

    def test_missing_sdk_installs_minimal_client_and_api_error_stub(self):
        modules = {}

        def missing(_name):
            raise ImportError("google-genai missing")

        self.assertTrue(_ensure_google_genai_available(missing, modules))
        self.assertIs(modules["google.genai"].Client, _FakeClient)
        self.assertIs(modules["google.genai.errors"].APIError, _FakeAPIError)

    def test_existing_google_module_is_preserved_when_stub_is_needed(self):
        existing_google = types.ModuleType("google")
        modules = {"google": existing_google}

        def missing(_name):
            raise ImportError("google.genai missing")

        _ensure_google_genai_available(missing, modules)
        self.assertIs(existing_google, modules["google"])
        self.assertIs(existing_google.genai, modules["google.genai"])

    def test_non_import_error_is_not_hidden_by_stub(self):
        def broken(_name):
            raise RuntimeError("real SDK initialization failed")

        with self.assertRaisesRegex(RuntimeError, "initialization failed"):
            _ensure_google_genai_available(broken, {})


class TestNotionHeaders(unittest.TestCase):
    """A, B: _notion_headers()がdictを返し、必須keyが存在する。"""

    def test_returns_dict(self):
        headers = pipeline._notion_headers()
        self.assertIsInstance(headers, dict)

    def test_has_required_keys(self):
        headers = pipeline._notion_headers()
        self.assertIn("Authorization", headers)
        self.assertIn("Content-Type", headers)
        self.assertIn("Notion-Version", headers)
        self.assertTrue(headers["Authorization"].startswith("Bearer "))


class TestStockSave(unittest.TestCase):
    """C, D: Stock保存成功/失敗でpage_idの有無が変わる。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_ds = patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "test-ds")
        self.patched_key.start()
        self.patched_ds.start()

    def tearDown(self):
        self.patched_key.stop()
        self.patched_ds.stop()

    def _repo(self):
        return {
            "nameWithOwner": "octo/example",
            "url": "https://github.com/octo/example",
            "source": "GitHub",
            "stargazerCount": 100,
            "publishedAt": "2026-08-01T00:00:00Z",
            "description": "desc",
            "licenseInfo": {"spdxId": "MIT"},
        }

    def test_stock_save_success_returns_page_id(self):
        with patch.object(pipeline.requests, "post",
                           return_value=_mock_response(200, {"id": "page-123"})):
            page_id = pipeline.save_screening_metadata_to_notion(self._repo(), 80, "reason")
        self.assertEqual(page_id, "page-123")

    def test_stock_save_failure_returns_none(self):
        with patch.object(pipeline.requests, "post",
                           return_value=_mock_response(400, {}, text="bad request")):
            page_id = pipeline.save_screening_metadata_to_notion(self._repo(), 80, "reason")
        self.assertIsNone(page_id)

    def test_stock_save_includes_license_for_github(self):
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["payload"] = json
            return _mock_response(200, {"id": "page-999"})

        with patch.object(pipeline.requests, "post", side_effect=fake_post):
            pipeline.save_screening_metadata_to_notion(self._repo(), 80, "reason")
        props = captured["payload"]["properties"]
        self.assertIn(pipeline.PROP_LICENSE, props)
        self.assertEqual(
            props[pipeline.PROP_LICENSE]["rich_text"][0]["text"]["content"], "MIT"
        )


class TestUpgradeReadyIntegrity(unittest.TestCase):
    """G, H, I: children/properties両方成功時のみReady相当のcommitが起きる。
    properties成功+children失敗という不整合経路が存在しないことも確認する。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_key.start()
        # デフォルトでは「既存manuscript childなし」を返す。冪等性チェック自体の
        # 分岐はTestUpgradeChildrenSuccessPropertiesFailで個別に検証する。
        self.patched_get = patch.object(
            pipeline.requests, "get", return_value=_mock_response(200, {"results": []}))
        self.patched_get.start()

    def tearDown(self):
        self.patched_key.stop()
        self.patched_get.stop()

    def _call_upgrade(self):
        return pipeline.upgrade_notion_page_with_report(
            "page-abc", "octo/example", "https://github.com/octo/example",
            80, "breakdown", "what", "why", "why-not", "action",
            "MIT", "manuscript body",
        )

    def test_children_and_properties_both_succeed_returns_true(self):
        with patch.object(pipeline.requests, "patch", return_value=_mock_response(200)):
            result = self._call_upgrade()
        self.assertTrue(result)

    def test_children_fail_returns_false_and_properties_never_called(self):
        calls = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            calls.append(url)
            if "/blocks/" in url:
                return _mock_response(400, {}, text="children failed")
            return _mock_response(200)

        with patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            result = self._call_upgrade()
        self.assertFalse(result)
        # properties (pages/{id}) へのPATCHは一度も呼ばれていないこと。
        self.assertFalse(any("/pages/" in c for c in calls))
        self.assertTrue(any("/blocks/" in c for c in calls))

    def test_properties_fail_after_children_success_returns_false(self):
        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "block-1"}]})
            return _mock_response(400, {}, text="properties failed")

        with patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=_mock_response(200)):
            result = self._call_upgrade()
        self.assertFalse(result)

    def test_upgrade_uses_same_page_id_no_new_page_created(self):
        """I: Stock済みpage_idがある場合、新規Notionページを作らず同じpageをupgradeする。"""
        with patch.object(pipeline.requests, "patch", return_value=_mock_response(200)) as mock_patch, \
             patch.object(pipeline.requests, "post") as mock_post:
            self._call_upgrade()
        mock_post.assert_not_called()
        for call in mock_patch.call_args_list:
            self.assertIn("page-abc", call.args[0])


class TestUpgradeChildrenSuccessPropertiesFail(unittest.TestCase):
    """P1 Regression: children成功 -> properties失敗という不整合経路への対処。
    (1) best-effortでchildren blockをrollback(archive)する。
    (2) 呼び出し側でPending Retryへ遷移させ、次回get_pending_retry_items()
        から復元できるようにする。
    (3) rollbackが失敗していても、次回試行で本文が二重appendされない
        （冪等性チェックでre-appendをスキップする）。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_key.start()
        self.addCleanup(self.patched_key.stop)

    def _call_upgrade(self):
        return pipeline.upgrade_notion_page_with_report(
            "page-abc", "octo/example", "https://github.com/octo/example",
            80, "breakdown", "what", "why", "why-not", "action",
            "MIT", "manuscript body",
        )

    def test_properties_fail_triggers_pending_retry_transition(self):
        """最低条件: Notion upgrade失敗 -> Article Status = Not Planned,
        Content Status = Pending Retry へ更新される。"""
        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "block-1"}]})
            return _mock_response(400, {}, text="properties failed")

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=_mock_response(200)), \
             patch.object(pipeline, "update_notion_pending_retry") as mock_pending:
            result = self._call_upgrade()

        self.assertFalse(result)
        mock_pending.assert_called_once()
        args, _ = mock_pending.call_args
        self.assertEqual(args[0], "page-abc")

    def test_properties_fail_pending_retry_sets_correct_notion_properties(self):
        """呼び出し側のPending Retry遷移が実際にNotionへ送るpropertiesの内容
        （Content Status = Pending Retry, Article Status = Not Planned）を、
        update_notion_pending_retryをモックせずに検証する。"""
        page_patch_payloads = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "block-1"}]})
            page_patch_payloads.append(json)
            # 1回目 = properties commit（失敗させる）, 2回目以降 = Pending Retry更新（成功させる）
            if len(page_patch_payloads) == 1:
                return _mock_response(400, {}, text="properties failed")
            return _mock_response(200)

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=_mock_response(200)):
            result = self._call_upgrade()

        self.assertFalse(result)
        self.assertEqual(len(page_patch_payloads), 2)
        pending_retry_props = page_patch_payloads[1]["properties"]
        self.assertEqual(
            pending_retry_props[pipeline.PROP_CONTENT_STATUS]["select"]["name"],
            pipeline.CONTENT_STATUS_PENDING_RETRY,
        )
        self.assertEqual(
            pending_retry_props[pipeline.PROP_ARTICLE_STATUS]["select"]["name"],
            pipeline.ARTICLE_STATUS_NOT_PLANNED,
        )

    def test_properties_fail_triggers_best_effort_rollback_of_appended_blocks(self):
        """今回のPhase 1で追加したchildren blockのidに対してDELETEが
        best-effortで発行されること。"""
        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "block-1"}, {"id": "block-2"}]})
            return _mock_response(400, {}, text="properties failed")

        deleted_urls = []

        def fake_delete(url, headers=None, timeout=None):
            deleted_urls.append(url)
            return _mock_response(200)

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", side_effect=fake_delete), \
             patch.object(pipeline, "update_notion_pending_retry"):
            result = self._call_upgrade()

        self.assertFalse(result)
        self.assertTrue(any("block-1" in u for u in deleted_urls))
        self.assertTrue(any("block-2" in u for u in deleted_urls))

    def test_rollback_delete_failure_is_swallowed_and_still_returns_false(self):
        """rollback自体が失敗しても例外を上げず、Falseを返し続けること
        （rollbackが失敗した場合の最後の砦は冪等性チェック側で担保する）。"""
        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "block-1"}]})
            return _mock_response(400, {}, text="properties failed")

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=_mock_response(500, {}, text="delete failed")), \
             patch.object(pipeline, "update_notion_pending_retry"):
            result = self._call_upgrade()
        self.assertFalse(result)

    def test_idempotency_skips_reappend_when_manuscript_child_already_exists(self):
        """rollbackが失敗して本文が残っていた状態からのRetryを想定:
        既にmanuscript child(markdown codeブロック)が存在する場合、
        children PATCH（re-append）を呼ばずにproperties commitのみ行う。"""
        existing_children_response = _mock_response(200, {
            "results": [{"type": "code", "code": {"language": "markdown"}}]
        })
        patch_calls = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            patch_calls.append(url)
            return _mock_response(200)

        with patch.object(pipeline.requests, "get", return_value=existing_children_response), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            result = self._call_upgrade()

        self.assertTrue(result)
        # children re-append（/blocks/{id}/children へのPATCH）は呼ばれていないこと。
        self.assertFalse(any("/blocks/" in c and "/children" in c for c in patch_calls))
        # properties commit（/pages/{id}）は呼ばれていること。
        self.assertTrue(any("/pages/" in c for c in patch_calls))

    def test_pending_retry_transition_failure_is_escalated(self):
        """P1最終補強: children成功 -> properties commit失敗 ->
        update_notion_pending_retry自体もFalse（Notion側への保存にも失敗）という
        二重障害時に、Telegramで運用者へエスカレーションされること。
        Quality FailedにもReadyにも変更しない。"""
        page_patch_payloads = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "block-1"}]})
            page_patch_payloads.append(json)
            # properties commit / Pending Retry更新、どちらのpages/ PATCHも失敗させる
            return _mock_response(400, {}, text="pages patch failed")

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=_mock_response(200)), \
             patch.object(pipeline, "send_telegram_alert") as mock_telegram:
            result = self._call_upgrade()

        # upgrade_notion_page_with_report=False
        self.assertFalse(result)
        # Telegram警告が発生する
        mock_telegram.assert_called_once()
        self.assertIn("Pending Retry", mock_telegram.call_args[0][0])
        # Readyにならない・Quality Failedにもならない:
        # 1回目のPATCH(properties commit)はReadyへのcommit試行そのものだが
        # 400で拒否されているためNotion側には反映されていない。
        # 2回目のPATCH(update_notion_pending_retryによる後始末)は
        # Ready/Quality Failedへは一切変更せず、Pending Retry/Not Plannedのみ
        # 送っていることを確認する。
        self.assertEqual(len(page_patch_payloads), 2)  # properties commit + pending retry更新
        recovery_props = page_patch_payloads[1].get("properties", {})
        self.assertEqual(
            (recovery_props.get(pipeline.PROP_ARTICLE_STATUS) or {}).get("select", {}).get("name"),
            pipeline.ARTICLE_STATUS_NOT_PLANNED,
        )
        self.assertEqual(
            (recovery_props.get(pipeline.PROP_CONTENT_STATUS) or {}).get("select", {}).get("name"),
            pipeline.CONTENT_STATUS_PENDING_RETRY,
        )

    def test_no_existing_manuscript_child_appends_normally(self):
        """比較対照: 既存manuscript childが無ければ通常通りchildren PATCHが呼ばれる。"""
        patch_calls = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            patch_calls.append(url)
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "block-1"}]})
            return _mock_response(200)

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            result = self._call_upgrade()

        self.assertTrue(result)
        self.assertTrue(any("/blocks/" in c and "/children" in c for c in patch_calls))


class TestScreeningReasonPreserved(unittest.TestCase):
    """J, K: Pending Retry / Needs Editorial ReviewでScreening Reasonが維持される
    （= PROP_SCREENING_REASONを一切書き換えない）。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_key.start()

    def tearDown(self):
        self.patched_key.stop()

    def test_pending_retry_does_not_touch_screening_reason(self):
        captured = {}

        def fake_patch(url, json=None, headers=None, timeout=None):
            captured["payload"] = json
            return _mock_response(200)

        with patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            pipeline.update_notion_pending_retry("page-1", "octo/example", "some transient error")
        self.assertNotIn(pipeline.PROP_SCREENING_REASON, captured["payload"]["properties"])

    def test_editorial_review_does_not_touch_screening_reason(self):
        captured = {}

        def fake_patch(url, json=None, headers=None, timeout=None):
            captured["payload"] = json
            return _mock_response(200)

        with patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            pipeline.update_notion_needs_editorial_review("page-1", "octo/example", ["reason A", "reason B"])
        self.assertNotIn(pipeline.PROP_SCREENING_REASON, captured["payload"]["properties"])
        self.assertIn(pipeline.PROP_ARTICLE_STATUS, captured["payload"]["properties"])


class TestGithubLicenseRestoration(unittest.TestCase):
    """L: GitHub MIT -> Pending Retry -> reconstruct -> MIT維持。Apache-2.0も同様。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_ds = patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "test-ds")
        self.patched_key.start()
        self.patched_ds.start()

    def tearDown(self):
        self.patched_key.stop()
        self.patched_ds.stop()

    def _page(self, license_text):
        return {
            "id": "page-lic",
            "properties": {
                pipeline.PROP_URL: {"url": "https://github.com/octo/example"},
                pipeline.PROP_SOURCE: {"select": {"name": "GitHub"}},
                pipeline.PROP_NAME: {"title": [{"plain_text": "octo/example"}]},
                pipeline.PROP_SOURCE_SUMMARY: {"rich_text": []},
                pipeline.PROP_ENGAGEMENT: {"number": 42},
                pipeline.PROP_PUBLISHED_AT: {"date": {"start": "2026-08-01T00:00:00Z"}},
                pipeline.PROP_SCREENING_SCORE: {"number": 80},
                pipeline.PROP_SCREENING_REASON: {"rich_text": [{"plain_text": "元のスクリーニング理由"}]},
                pipeline.PROP_LICENSE: {"rich_text": [{"plain_text": license_text}]},
            },
        }

    def _run(self, license_text):
        with patch.object(pipeline, "_query_notion_db_with_retry",
                           return_value=_mock_response(200, {"results": [self._page(license_text)]})):
            items = pipeline.get_pending_retry_items()
        return items

    def test_mit_license_preserved_through_reconstruction(self):
        items = self._run("MIT")
        self.assertEqual(items[0]["repo"]["licenseInfo"], {"spdxId": "MIT"})

    def test_apache_license_preserved_through_reconstruction(self):
        items = self._run("Apache-2.0")
        self.assertEqual(items[0]["repo"]["licenseInfo"], {"spdxId": "Apache-2.0"})

    def test_screening_reason_also_restored(self):
        items = self._run("MIT")
        self.assertEqual(items[0]["screening_reason"], "元のスクリーニング理由")


class TestUrlCanonicalization(unittest.TestCase):
    """O, P: trackingパラメータ違いは重複、意味のあるqueryは非重複。"""

    def test_tracking_param_and_trailing_slash_are_duplicate(self):
        a = pipeline.canonicalize_url("https://example.com/product")
        b = pipeline.canonicalize_url("https://example.com/product/?utm_source=hn")
        self.assertEqual(a, b)

    def test_meaningful_query_param_not_collapsed(self):
        a = pipeline.canonicalize_url("https://example.com/product?id=123")
        b = pipeline.canonicalize_url("https://example.com/product?id=456")
        self.assertNotEqual(a, b)

    def test_fragment_is_ignored(self):
        a = pipeline.canonicalize_url("https://example.com/product#section")
        b = pipeline.canonicalize_url("https://example.com/product")
        self.assertEqual(a, b)

    def test_fbclid_and_gclid_and_ref_and_source_stripped(self):
        base = pipeline.canonicalize_url("https://example.com/x")
        for suffix in ["?fbclid=abc", "?gclid=abc", "?ref=abc", "?source=abc"]:
            self.assertEqual(pipeline.canonicalize_url("https://example.com/x" + suffix), base)


class TestStaleContentTargetsReadyOnly(unittest.TestCase):
    """Q: Stockが毎日追加されていても、ReadyがSTALE_THRESHOLD_DAYS以上
    経過していればstale warning対象になる（Stockのcreated_timeに惑わされない）。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_ds = patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "test-ds")
        self.patched_key.start()
        self.patched_ds.start()

    def tearDown(self):
        self.patched_key.stop()
        self.patched_ds.stop()

    def test_query_filters_on_ready_only_and_sorts_by_analyzed_at(self):
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["payload"] = json
            return _mock_response(200, {"results": []})

        with patch.object(pipeline.requests, "post", side_effect=fake_post), \
             patch.object(pipeline, "send_telegram_alert") as mock_alert:
            pipeline.check_stale_content()

        payload = captured["payload"]
        self.assertEqual(payload["filter"]["property"], pipeline.PROP_ARTICLE_STATUS)
        self.assertEqual(payload["filter"]["select"]["equals"], pipeline.ARTICLE_STATUS_READY)
        self.assertNotIn("or", payload["filter"])
        self.assertEqual(payload["sorts"][0]["property"], pipeline.PROP_ANALYZED_AT)
        # Needs Editorial Reviewではstaleを隠せない。Readyが無ければアラート。
        mock_alert.assert_called_once()

    def test_stale_alert_fires_when_last_ready_older_than_threshold(self):
        import datetime as dt
        old_iso = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=pipeline.STALE_THRESHOLD_DAYS + 5)).isoformat()
        page = {"properties": {pipeline.PROP_ANALYZED_AT: {"date": {"start": old_iso}}}}
        with patch.object(pipeline.requests, "post",
                           return_value=_mock_response(200, {"results": [page]})), \
             patch.object(pipeline, "send_telegram_alert") as mock_alert:
            pipeline.check_stale_content()
        mock_alert.assert_called_once()

    def test_no_alert_when_recent_ready_exists(self):
        import datetime as dt
        recent_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        page = {"properties": {pipeline.PROP_ANALYZED_AT: {"date": {"start": recent_iso}}}}
        with patch.object(pipeline.requests, "post",
                           return_value=_mock_response(200, {"results": [page]})), \
             patch.object(pipeline, "send_telegram_alert") as mock_alert:
            pipeline.check_stale_content()
        mock_alert.assert_not_called()


class TestNotionUnsetFailSafe(unittest.TestCase):
    """12: Notion未設定時の既存Fail-Safeを維持（本番へ書き込まない）。"""

    def test_save_screening_metadata_returns_none_without_config(self):
        with patch.object(pipeline, "NOTION_API_KEY", None):
            result = pipeline.save_screening_metadata_to_notion(
                {"nameWithOwner": "x", "url": "https://x", "source": "GitHub"}, 80, "r")
        self.assertIsNone(result)

    def test_upgrade_returns_false_without_config(self):
        with patch.object(pipeline, "NOTION_API_KEY", None):
            result = pipeline.upgrade_notion_page_with_report(
                "p", "n", "u", 1, "b", "w", "wi", "wn", "a", "MIT", "m")
        self.assertFalse(result)

    def test_pending_retry_items_returns_empty_list_without_config(self):
        with patch.object(pipeline, "NOTION_API_KEY", None):
            result = pipeline.get_pending_retry_items()
        self.assertEqual(result, [])


class TestGenerateIntelligenceReportReadyIntegrity(unittest.TestCase):
    """E, F: Quality Gate PASSでもNotion保存/アップグレードが失敗した場合は
    Readyにならない（record_gate_outcomeにARTICLE_STATUS_READYが渡らない）。

    generate_intelligence_report()内部のScreening/Gemini/各種Gateロジックは
    変更禁止の対象なので、それらは全てモックで固定し、Notion永続化の
    成否だけを切り替えてReady判定への影響を検証する。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_key.start()
        self.addCleanup(self.patched_key.stop)

        self.repo = {
            "nameWithOwner": "octo/example",
            "url": "https://github.com/octo/example",
            "source": "GitHub",
            "stargazerCount": 100,
            "publishedAt": "2026-08-01T00:00:00Z",
            "description": "desc",
            "licenseInfo": {"spdxId": "MIT"},
        }

        parsed = {
            "note_draft": "本文", "title_text": "タイトル", "score": 80,
            "score_breakdown_text": "内訳", "source_summary_text": "概要",
            "what_text": "what", "why_important_text": "why",
            "paradigm_shift_text": "p", "alternative_comparison_text": "a",
            "migration_cost_text": "m", "decision_text": "TRY",
            "decision_reason_text": "dr", "why_not_important_text": "wn",
            "who_should_use_text": "wu", "who_should_not_use_text": "wnu",
            "action_text": "action", "future_scenario_text": "fs",
            "article_value": 50, "grounding_status": pipeline.GROUNDING_SOURCE_NATIVE,
            "evidence_urls_text": "",
        }

        fake_response = MagicMock()
        fake_response.text = "dummy"

        patches = {
            "legal_safety_gate": (True, "MIT"),
            "prepare_source_context": {
                "primary_source_resolved": True, "primary_url": self.repo["url"],
                "context": "method architecture 著者 limitation constraint",
                "method": pipeline.GROUNDING_SOURCE_NATIVE, "source": "GitHub",
                "deep_source_scanned": False,
            },
            "resolve_followup_freshness": {"triggered": False, "followup_found": False, "context": ""},
            "assess_evidence_sufficiency": {
                "state": pipeline.EVIDENCE_SUFFICIENT, "core_missing": [],
                "blocking_missing": [], "decision_scope_safe": True,
                "action_risk_tier": "LOW",
            },
            "classify_action_risk_tier": "LOW",
            "_response_was_truncated": False,
            "_parse_gemini_response": parsed,
            "validate_fact_gate": (True, []),
            "validate_editorial_gate": (True, []),
            "validate_publication_readiness_gate": ("PASS", []),
            "validate_human_appeal_gate": ("ACCEPTABLE", []),
            "build_clean_note_manuscript": "clean manuscript",
            "generate_eyecatch_image": None,
        }
        self._active_patches = []
        for name, retval in patches.items():
            p = patch.object(pipeline, name, return_value=retval)
            p.start()
            self._active_patches.append(p)
            self.addCleanup(p.stop)

        p_gemini = patch.object(
            pipeline, "call_gemini_grounded_deep_dive",
            return_value=(fake_response, {"grounding_status": pipeline.GROUNDING_SOURCE_NATIVE, "evidence_urls": []}),
        )
        p_gemini.start()
        self.addCleanup(p_gemini.stop)

        p_telegram = patch.object(pipeline, "send_telegram_alert")
        self.mock_telegram = p_telegram.start()
        self.addCleanup(p_telegram.stop)

    def test_upgrade_failure_does_not_produce_ready(self):
        """E: Deep Dive upgrade_notion_page_with_report() = False -> Readyにならない。
        P0: 戻り値もNoneであること（呼び出し元のtruthy checkで誤加算されないため）。"""
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "upgrade_notion_page_with_report", return_value=False) as mock_upgrade:
            result = pipeline.generate_intelligence_report(
                self.repo, notion_page_id="existing-page-id",
                screening_score=80, screening_reason="reason",
            )
        mock_upgrade.assert_called_once()
        final_statuses = [r.get("final_status") for r in pipeline.DEEP_DIVE_GATE_FUNNEL.records]
        self.assertNotIn(pipeline.ARTICLE_STATUS_READY, final_statuses)
        self.assertIn(pipeline.CONTENT_STATUS_PERSISTENCE_FAILED, final_statuses)
        self.mock_telegram.assert_called()
        self.assertIsNone(result)

    def test_save_to_notion_failure_does_not_produce_ready(self):
        """F: Deep Dive save_to_notion() = False -> Readyにならない。
        P0: 戻り値もNoneであること。"""
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "save_to_notion", return_value=False) as mock_save:
            result = pipeline.generate_intelligence_report(
                self.repo, notion_page_id=None,
                screening_score=80, screening_reason="reason",
            )
        mock_save.assert_called_once()
        final_statuses = [r.get("final_status") for r in pipeline.DEEP_DIVE_GATE_FUNNEL.records]
        self.assertNotIn(pipeline.ARTICLE_STATUS_READY, final_statuses)
        self.assertIn(pipeline.CONTENT_STATUS_PERSISTENCE_FAILED, final_statuses)
        self.assertIsNone(result)

    def test_upgrade_success_produces_ready(self):
        """比較対照: Notion永続化が成功すればReadyになる。
        P0: persistence成功時だけ非None（clean_manuscript）を返すこと。"""
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "upgrade_notion_page_with_report", return_value=True):
            result = pipeline.generate_intelligence_report(
                self.repo, notion_page_id="existing-page-id",
                screening_score=80, screening_reason="reason",
            )
        final_statuses = [r.get("final_status") for r in pipeline.DEEP_DIVE_GATE_FUNNEL.records]
        self.assertIn(pipeline.ARTICLE_STATUS_READY, final_statuses)
        self.assertIsNotNone(result)
        self.assertEqual(result, "clean manuscript")

    def test_upgrade_failure_return_value_does_not_increment_caller_counter(self):
        """P0 Regression 1: main()のDeep Dive集計
        `if report: generated_count += 1` に相当するtruthy checkが、
        upgrade失敗時に誤加算されないことを直接確認する。"""
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "upgrade_notion_page_with_report", return_value=False):
            result = pipeline.generate_intelligence_report(
                self.repo, notion_page_id="existing-page-id",
                screening_score=80, screening_reason="reason",
            )
        generated_count = 0
        if result:
            generated_count += 1
        self.assertEqual(generated_count, 0)

    def test_save_to_notion_failure_return_value_does_not_increment_caller_counter(self):
        """P0 Regression 2: Pending Retry処理側の
        `if generate_intelligence_report(...): retry_generated += 1` に相当する
        truthy checkが、save_to_notion失敗時に誤加算されないことを直接確認する。"""
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "save_to_notion", return_value=False):
            result = pipeline.generate_intelligence_report(
                self.repo, notion_page_id=None,
                screening_score=80, screening_reason="reason",
            )
        retry_generated = 0
        if result:
            retry_generated += 1
        self.assertEqual(retry_generated, 0)

    def test_upgrade_success_return_value_increments_caller_counter(self):
        """P0 Regression 3: persistence成功時は非Noneが返り、
        呼び出し元のtruthy checkで正しく1件加算されること。"""
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "upgrade_notion_page_with_report", return_value=True):
            result = pipeline.generate_intelligence_report(
                self.repo, notion_page_id="existing-page-id",
                screening_score=80, screening_reason="reason",
            )
        generated_count = 0
        if result:
            generated_count += 1
        self.assertEqual(generated_count, 1)


class TestArxivIntegrityNotionReflection(unittest.TestCase):
    """M, N: arXiv transient failureはPending Retry、恒久Source Integrity Failure
    はNotionにもFailure状態を反映する（Pending Retryにはしない）。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_key.start()
        self.addCleanup(self.patched_key.stop)
        self.repo = {
            "nameWithOwner": "arXiv:9999.99999", "url": "https://arxiv.org/abs/9999.99999",
            "source": "ArXiv", "stargazerCount": 0, "description": "d",
        }

    def test_transient_failure_triggers_pending_retry_not_notion_quality_failed(self):
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "_verify_arxiv_source_integrity",
                           return_value=(False, "TRANSIENT: timeout", None)), \
             patch.object(pipeline, "update_notion_pending_retry") as mock_pending, \
             patch.object(pipeline, "update_notion_quality_failed") as mock_qf:
            pipeline.generate_intelligence_report(
                self.repo, notion_page_id="page-arxiv", screening_score=80, screening_reason="r",
            )
        mock_pending.assert_called_once()
        mock_qf.assert_not_called()

    def test_permanent_integrity_failure_reflected_in_notion_not_pending_retry(self):
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "_verify_arxiv_source_integrity",
                           return_value=(False, "arXiv ID不正: title mismatch", None)), \
             patch.object(pipeline, "update_notion_pending_retry") as mock_pending, \
             patch.object(pipeline, "update_notion_quality_failed") as mock_qf, \
             patch.object(pipeline, "save_quality_failed_article", return_value="path"), \
             patch.object(pipeline, "send_telegram_alert"):
            pipeline.generate_intelligence_report(
                self.repo, notion_page_id="page-arxiv", screening_score=80, screening_reason="r",
            )
        mock_pending.assert_not_called()
        mock_qf.assert_called_once()
        args, kwargs = mock_qf.call_args
        self.assertEqual(args[0], "page-arxiv")


class TestNeedsEditorialReviewPersistence(unittest.TestCase):
    """Needs Editorial Review本文を内部Notion DBへ保持し、公開状態と混同しない。"""

    def setUp(self):
        self.patched_key = patch.object(pipeline, "NOTION_API_KEY", "test-key")
        self.patched_key.start()
        self.addCleanup(self.patched_key.stop)

    def _base_props(self):
        return {
            pipeline.PROP_STATUS: {"select": {"name": pipeline.STATUS_DEEP_DIVE}},
            pipeline.PROP_CONTENT_STATUS: {"select": {"name": pipeline.CONTENT_STATUS_DEEP_DIVE}},
            pipeline.PROP_ARTICLE_STATUS: {"select": {"name": pipeline.ARTICLE_STATUS_READY}},
            pipeline.PROP_SUBSCRIPTION_VISIBILITY: {"select": {"name": pipeline.VISIBILITY_FREE_ARTICLE}},
        }

    def test_review_manuscript_is_stored_internal_and_not_public_approved(self):
        page_payloads = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                child = json["children"][0]
                self.assertEqual(child["code"]["caption"][0]["text"]["content"], pipeline.MANUSCRIPT_CAPTION_REVIEW)
                return _mock_response(200, {"results": [{"id": "review-block"}]})
            page_payloads.append(json)
            return _mock_response(200)

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            result = pipeline.persist_notion_needs_editorial_review(
                "page-1", "octo/example", "review manuscript", self._base_props(), ["reason"]
            )
        self.assertTrue(result)
        props = page_payloads[0]["properties"]
        self.assertEqual(props[pipeline.PROP_STATUS]["select"]["name"], pipeline.STATUS_DEEP_DIVE)
        self.assertEqual(props[pipeline.PROP_CONTENT_STATUS]["select"]["name"], pipeline.CONTENT_STATUS_DEEP_DIVE)
        self.assertEqual(props[pipeline.PROP_ARTICLE_STATUS]["select"]["name"], pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW)
        self.assertEqual(props[pipeline.PROP_SUBSCRIPTION_VISIBILITY]["select"]["name"], pipeline.VISIBILITY_SUBSCRIBER_ONLY)
        self.assertNotIn(pipeline.PROP_REVIEW_STATUS, props)

    def test_review_properties_failure_rolls_back_and_enters_pending_retry_recovery(self):
        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "review-block"}]})
            return _mock_response(400, {}, text="properties failed")

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": []})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline, "_rollback_notion_manuscript_children") as mock_rollback, \
             patch.object(pipeline, "_mark_pending_retry_or_escalate") as mock_pending:
            result = pipeline.persist_notion_needs_editorial_review(
                "page-1", "octo/example", "review manuscript", self._base_props(), ["reason"]
            )
        self.assertFalse(result)
        mock_rollback.assert_called_once()
        mock_pending.assert_called_once()

    def test_review_manuscript_is_not_mistaken_for_ready_manuscript(self):
        block = {
            "id": "review-block", "type": "code",
            "code": {
                "language": "markdown",
                "caption": [{"plain_text": pipeline.MANUSCRIPT_CAPTION_REVIEW}],
            },
        }
        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": [block]})):
            self.assertFalse(pipeline._notion_page_has_manuscript_child("page-1", {}))

    def test_ready_upgrade_archives_prior_review_manuscript_after_commit(self):
        review_block = {
            "id": "review-block", "type": "code",
            "code": {"language": "markdown", "caption": [{"plain_text": pipeline.MANUSCRIPT_CAPTION_REVIEW}]},
        }

        def fake_patch(url, json=None, headers=None, timeout=None):
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "ready-block"}]})
            return _mock_response(200)

        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": [review_block]})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=_mock_response(200)) as mock_delete:
            result = pipeline.upgrade_notion_page_with_report(
                "page-1", "octo/example", "https://github.com/octo/example",
                80, "breakdown", "what", "why", "why-not", "action",
                "MIT", "ready manuscript",
            )
        self.assertTrue(result)
        self.assertTrue(any("review-block" in call.args[0] for call in mock_delete.call_args_list))

    def test_new_review_replaces_old_review_only_after_successful_commit(self):
        old_block = {
            "id": "old-review", "type": "code",
            "code": {"language": "markdown", "caption": [{"plain_text": pipeline.MANUSCRIPT_CAPTION_REVIEW}]},
        }
        patch_calls = []
        def fake_patch(url, json=None, headers=None, timeout=None):
            patch_calls.append((url, json))
            if "/blocks/" in url:
                return _mock_response(200, {"results": [{"id": "new-review"}]})
            return _mock_response(200)
        with patch.object(pipeline.requests, "get", return_value=_mock_response(200, {"results": [old_block]})), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch), \
             patch.object(pipeline.requests, "delete", return_value=_mock_response(200)) as mock_delete:
            result = pipeline.persist_notion_needs_editorial_review(
                "page-1", "octo/example", "new review manuscript", self._base_props(), ["reason"]
            )
        self.assertTrue(result)
        self.assertTrue(any("/blocks/page-1/children" in u for u, _ in patch_calls))
        self.assertTrue(any("old-review" in call.args[0] for call in mock_delete.call_args_list))



if __name__ == "__main__":
    unittest.main(verbosity=2)
