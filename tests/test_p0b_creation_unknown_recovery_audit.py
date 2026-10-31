from __future__ import annotations

import importlib
import importlib.util
import inspect
import tempfile
from pathlib import Path

import pytest

from note_delivery_ledger import DeliveryState, SQLiteDeliveryLedger, build_delivery_snapshot
from note_document_contract import Document, Paragraph, Text


def _module():
    spec = importlib.util.find_spec("note_delivery_creation_recovery")
    assert spec is not None, "note_delivery_creation_recovery must exist before ambiguous draft recovery can run"
    return importlib.import_module("note_delivery_creation_recovery")


def _snapshot(sync_id: str = "a" * 32, note_target: str = "trendhub_biz"):
    return build_delivery_snapshot(
        sync_id=sync_id,
        queue_page_id="queue-page",
        title="Private recovery target",
        manuscript_sha256="1" * 64,
        publication_policy_sha256="2" * 64,
        document=Document((Paragraph((Text("canonical body"),)),)),
        transform_versions=(("run222", "note-presentation-integrity-v1"),),
        eyecatch_sha256="3" * 64,
        eyecatch_asset_id="asset-id",
        note_target=note_target,
        ready_provenance="ready-waiting-current-publication-v1:test",
    )


def test_safe_projection_excludes_private_identity_and_unpublished_content():
    recovery = _module()
    full = {
        "status": "recovery_candidate_found",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 1,
        "history_candidate_count": 7,
        "editor_route_hash": "abcdef123456",
        "recovered_draft_id": "private-draft-id",
        "sync_id": "a" * 32,
        "draft_url": "https://note.com/notes/private-draft-id/edit",
        "title": "secret unpublished title",
        "manuscript": "secret unpublished body",
    }
    safe = recovery.safe_recovery_projection(full)
    assert safe == {
        "status": "recovery_candidate_found",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "match_count": 1,
        "history_candidate_count": 7,
        "editor_route_hash": "abcdef123456",
        "rejection_counts": {bucket: 0 for bucket in recovery.REJECTION_BUCKETS},
        "inspection_stage_counts": {stage: 0 for stage in recovery.INSPECTION_STAGES},
        "title_failure_counts": {code: 0 for code in recovery.TITLE_FAILURE_CODES},
        "title_dom_signal_counts": {code: 0 for code in recovery.TITLE_DOM_SIGNAL_CODES},
        "title_context_signal_counts": {code: 0 for code in recovery.TITLE_CONTEXT_CODES},
        "title_route_shape_counts": {code: 0 for code in recovery.TITLE_ROUTE_SHAPES},
        "title_atomic_dom_counts": {code: 0 for code in recovery.TITLE_ATOMIC_DOM_CODES},
        "failed_screen_signal_counts": {code: 0 for code in recovery.SCREEN_SIGNAL_CODES},
        "control_screen_signal_counts": {code: 0 for code in recovery.SCREEN_SIGNAL_CODES},
        "official_list_proof_counts": {code: 0 for code in recovery.OFFICIAL_LIST_CODES},
        "official_list_scan_counts": {code: 0 for code in recovery.OFFICIAL_LIST_SCAN_CODES},
    }
    for forbidden in ("recovered_draft_id", "sync_id", "draft_url", "title", "manuscript"):
        assert forbidden not in safe


def test_recovery_requires_existing_creation_unknown_without_draft_identity():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        ambiguous = ledger.record_blocked(
            decision.record.operation_key,
            state=DeliveryState.CREATION_UNKNOWN,
            category="creation_result_ambiguous",
            expected_version=decision.record.state_version,
        )

        loaded = recovery.require_creation_unknown_record(
            ledger,
            sync_id="a" * 32,
            note_target="trendhub_biz",
        )
        assert loaded.record_id == ambiguous.record_id
        assert loaded.state == DeliveryState.CREATION_UNKNOWN
        assert loaded.draft_id is None


def test_recovery_rejects_missing_or_non_ambiguous_delivery():
    recovery = _module()
    with tempfile.TemporaryDirectory() as tmp:
        ledger = SQLiteDeliveryLedger(Path(tmp) / "delivery.sqlite3")
        ledger.initialize()
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_creation_unknown_record(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub_biz",
            )

        decision = ledger.begin_or_load(_snapshot(), run_correlation_id="run-a")
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_creation_unknown_record(
                ledger,
                sync_id="a" * 32,
                note_target="trendhub_biz",
            )
        assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED


def test_recovery_candidate_selection_is_exactly_one_or_fail_closed():
    recovery = _module()
    one = recovery.require_unique_recovery_match([
        {"draft_id": "opaque-1", "editor_route_hash": "hash-1"}
    ])
    assert one["draft_id"] == "opaque-1"

    for matches in ([], [{"draft_id": "a"}, {"draft_id": "b"}]):
        with pytest.raises(recovery.CreationRecoveryAuditError):
            recovery.require_unique_recovery_match(matches)


def test_recovery_module_is_read_only_and_reuses_current_contract_verification():
    recovery = _module()
    source = inspect.getsource(recovery)
    assert "run194_note_current_contract" in source
    assert "run291_note_private_draft_audit" in source
    assert "_recent_private_edit_urls" in source
    # The sole permitted click is the exact account menu opener. It is
    # unique, aria-haspopup=menu, owner-verified, and never an article action.
    allowed_menu_click = 'semantic[0].click(timeout=3000)'
    assert source.count(".click(") == 1
    assert allowed_menu_click in source
    menu_source = inspect.getsource(recovery._safe_owner_articles_menu_route)
    assert 'button[aria-haspopup="menu"]:visible' in menu_source
    assert 'codes.add("account_proven")' in inspect.getsource(recovery._probe_official_article_list)
    source = source.replace(allowed_menu_click, "")
    forbidden = (
        "_create_browser_draft(",
        "_mark_draft_created(",
        "record_draft_created(",
        "record_verified(",
        "record_queue_confirmed(",
        "patch_and_readback_draft_binding(",
        ".click(",
        ".fill(",
        "keyboard.press",
        "keyboard.insert_text",
        "page.screenshot(",
        "requests.post(",
    )
    for token in forbidden:
        assert token not in source


def test_recovery_requires_immutable_snapshot_and_lossless_canonical_dom_evidence():
    recovery = _module()
    source = inspect.getsource(recovery)

    # The ambiguous attempt itself, not merely the current mutable queue projection,
    # remains the authority for which revision may be recovered.
    assert "delivery_runtime.prepare_delivery(" in source
    assert ".snapshot != record.snapshot" in source

    # A title/prefix/length heuristic is insufficient to recover external identity.
    # Candidate body must survive the same semantic DOM -> canonical document path as P0-A
    # and hash exactly to the immutable snapshot recorded before the ambiguous create.
    assert "snapshot_note_body(" in source
    assert "document_from_note_snapshot(" in source
    assert "NOTE_LIST_ITEM_PARAGRAPH_WRAPPER" in source
    assert "NOTE_BLOCKQUOTE_FIGURE_WRAPPER" in source
    assert "canonical_document_sha256(" in source
    assert "record.snapshot.canonical_document_sha256" in source


def test_non_unique_readonly_audit_reports_counts_without_authorizing_recovery(monkeypatch):
    import types
    recovery = _module()
    monkeypatch.setattr(recovery, "SQLiteDeliveryLedger", lambda _: object())
    monkeypatch.setattr(recovery, "require_creation_unknown_record", lambda *a, **kw: object())
    monkeypatch.setattr(
        recovery, "_expected_prepared_delivery",
        lambda _: types.SimpleNamespace(article={"title": "private", "manuscript": "body"}),
    )

    for matches, expected in (
        ([], "recovery_no_verified_match"),
        ([{"draft_id": "opaque-one"}, {"draft_id": "opaque-two"}],
         "recovery_multiple_verified_matches"),
    ):
        monkeypatch.setattr(
            recovery, "_discover_verified_matches",
            lambda article, record, matches=matches: (
                matches, 6,
                {"different_title": 6 - len(matches)},
                {"title_read": 1},
                {"title_selector_unavailable": 1},
                {"ready_complete": 1, "editables_missing": 1},
                {"http_2xx": 1, "route_same_identity": 1, "js_responding": 1},
                {"shape_strict_supported": 1},
                {"atomic_available": 1, "atomic_ready_complete": 1},
                {"surface_not_found_hint": 1, "surface_header_present": 1},
                {"surface_header_present": 2, "surface_main_present": 2},
                {"account_proven": 1, "list_open": 1, "title_button_unique": 1},
                {"list_scroll_attempted": 1},
            ),
        )
        result = recovery.run(
            confirm=recovery.CONFIRM_TOKEN, sync_id="a" * 32,
            note_target="trendhub_biz", ledger_path="/unused/read-only/ledger",
        )
        assert result["status"] == expected
        assert result["match_count"] == len(matches)
        assert result["history_candidate_count"] == 6
        assert result["rejection_counts"]["different_title"] == 6 - len(matches)
        assert result["inspection_stage_counts"]["title_read"] == 1
        assert result["title_failure_counts"]["title_selector_unavailable"] == 1
        assert result["title_dom_signal_counts"]["ready_complete"] == 1
        assert result["title_dom_signal_counts"]["editables_missing"] == 1
        assert result["title_context_signal_counts"]["route_same_identity"] == 1
        assert result["title_route_shape_counts"]["shape_strict_supported"] == 1
        assert result["title_atomic_dom_counts"]["atomic_ready_complete"] == 1
        assert result["failed_screen_signal_counts"]["surface_not_found_hint"] == 1
        assert result["control_screen_signal_counts"]["surface_main_present"] == 2
        assert result["official_list_proof_counts"]["title_button_unique"] == 1
        assert result["official_list_scan_counts"]["list_scroll_attempted"] == 1
        assert result["read_only"] is True
        assert result["draft_mutation"] is False
        assert result["public_release"] is False
        assert "recovered_draft_id" not in result


def test_cli_writes_safe_blocked_result_then_returns_failure(tmp_path, monkeypatch, capsys):
    import json
    import sys
    recovery = _module()
    blocked = {
        "status": "recovery_no_verified_match",
        "read_only": True, "zero_gemini_calls": True,
        "draft_mutation": False, "public_release": False,
        "match_count": 0, "history_candidate_count": 9,
        "editor_route_hash": "",
        "rejection_counts": {"different_title": 9},
    }
    monkeypatch.setattr(recovery, "run", lambda **kwargs: dict(blocked))
    target = tmp_path / "read-only-result.json"
    monkeypatch.setattr(sys, "argv", ["audit", "--result-file", str(target)])
    with pytest.raises(recovery.CreationRecoveryAuditError):
        recovery.main()
    assert json.loads(target.read_text(encoding="utf-8")) == blocked
    output = capsys.readouterr().out
    assert '"match_count": 0' in output
    assert '"history_candidate_count": 9' in output
    assert "draft_id" not in output


def test_rejection_diagnostics_are_fixed_bucket_counts_without_private_identity():
    recovery = _module()
    unsafe = {
        "status": "recovery_no_verified_match",
        "rejection_counts": {
            "different_title": 16,
            "logged_out": 2,
            "inspection_error": 6,
            "candidate_private_url": "https://note.com/notes/secret/edit",
            "secret_manuscript": "private text",
        },
        "recovered_draft_id": "secret",
    }
    safe = recovery.safe_recovery_projection(unsafe)
    assert safe["rejection_counts"] == {
        "logged_out": 2, "non_editor": 0, "different_title": 16,
        "content_or_eyecatch": 0, "canonical_hash": 0,
        "inspection_error": 6,
    }
    assert "candidate_private_url" not in str(safe)
    assert "secret_manuscript" not in str(safe)
    assert "recovered_draft_id" not in str(safe)


def test_failed_recovery_still_requires_exact_one_verified_match():
    recovery = _module()
    assert "recovery_no_verified_match" in inspect.getsource(recovery.run)
    assert "recovery_multiple_verified_matches" in inspect.getsource(recovery.run)
    assert "len(matches) != 1" in inspect.getsource(recovery.run)


def test_inspection_stage_projection_is_fixed_and_never_leaks_raw_browser_data():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "status": "recovery_no_verified_match",
        "inspection_stage_counts": {
            "title_read": 5, "navigation": 1,
            "private_editor_url": "https://note.com/notes/secret/edit",
            "raw_browser_error": "Private title is secret",
        },
    })
    assert safe["inspection_stage_counts"]["title_read"] == 5
    assert safe["inspection_stage_counts"]["navigation"] == 1
    assert set(safe["inspection_stage_counts"]) == set(recovery.INSPECTION_STAGES)
    assert "private_editor_url" not in str(safe)
    assert "raw_browser_error" not in str(safe)
    assert "secret" not in str(safe).lower()


def test_readonly_title_fallback_uses_existing_explicit_finder_without_navigation(monkeypatch):
    recovery = _module()
    field = object()

    class Page:
        url = "https://editor.note.com/notes/existing/edit"

        def __init__(self):
            self.waits = []

        def wait_for_timeout(self, milliseconds):
            self.waits.append(milliseconds)

        def goto(self, *args, **kwargs):
            raise AssertionError("read-only recovery must never navigate to create a draft")

    def old_finder(_):
        raise recovery.draft_audit.note_base.NoteDraftError("legacy title selector absent")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", lambda _: field)
    page = Page()
    assert recovery._read_only_title_field(page, old_finder) is field
    assert page.waits == []


def test_readonly_title_prefers_original_finder_and_does_not_use_fallback(monkeypatch):
    recovery = _module()
    field = object()

    class Page:
        url = "https://note.com/notes/existing/edit"

    def fallback(_):
        raise AssertionError("fallback should not run when canonical finder succeeds")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", fallback)
    assert recovery._read_only_title_field(Page(), lambda _: field) is field


def test_readonly_title_absence_stays_blocked_without_guessing_or_writes(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://note.com/notes/existing/edit"

        def __init__(self):
            self.waits = []

        def wait_for_timeout(self, milliseconds):
            self.waits.append(milliseconds)

    def old_finder(_):
        raise recovery.draft_audit.note_base.NoteDraftError("missing")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", lambda _: None)
    page = Page()
    with pytest.raises(recovery.TitleReadInspectionError) as exc:
        recovery._read_only_title_field(page, old_finder)
    assert exc.value.code == "title_selector_unavailable"
    assert page.waits == [450, 450, 450]


def test_readonly_title_fallback_requires_existing_editor_route(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://note.com/"

    def forbidden(_):
        raise AssertionError("must not inspect title on a non-editor route")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", forbidden)
    with pytest.raises(recovery.CreationRecoveryAuditError):
        recovery._read_only_title_field(Page(), forbidden)


def test_readonly_finder_scoped_across_title_body_and_canonical_checks():
    recovery = _module()
    source = inspect.getsource(recovery._discover_verified_matches)
    assert 'patch.object(draft_audit.note_base, "_find_title", read_only_title_finder)' in source
    assert source.index('patch.object(draft_audit.note_base, "_find_title"') < source.index('draft_audit._title_value(page)')
    assert source.index('patch.object(draft_audit.note_base, "_find_title"') < source.index('draft_audit._audit_current_page(')
    assert source.index('patch.object(draft_audit.note_base, "_find_title"') < source.index('_current_canonical_sha256(page)')
    assert "record.snapshot.canonical_document_sha256" in source
    assert "len(matches)" not in inspect.getsource(recovery._read_only_title_field)

def test_title_failure_safe_projection_drops_untrusted_browser_details():
    recovery = _module()
    result = recovery.safe_recovery_projection({
        "title_failure_counts": {
            "title_selector_unavailable": 2,
            "title_selector_exception": 1,
            "title_value_unreadable": 3,
            "title_retry_interrupted": 0,
            "title_other": 0,
            "raw_page_url": "https://note.com/notes/private-identity/edit",
            "exception_text": "private manuscript and title",
        }
    })
    assert result["title_failure_counts"] == {
        "title_selector_unavailable": 2,
        "title_selector_exception": 1,
        "title_retry_interrupted": 0,
        "title_value_unreadable": 3,
        "title_other": 0,
    }
    assert "private-identity" not in str(result)
    assert "manuscript" not in str(result)
    assert set(result["title_failure_counts"]) == set(recovery.TITLE_FAILURE_CODES)


def test_title_fallback_failed_explicit_selector_is_fixed_code_only(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://note.com/notes/existing/edit"
        def wait_for_timeout(self, milliseconds):
            assert milliseconds == 450

    def legacy(_):
        raise RuntimeError("secret URL https://note.com/notes/private-id/edit")

    def broken_explicit(_):
        raise ValueError("secret unpublished title")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", broken_explicit)
    with pytest.raises(recovery.TitleReadInspectionError) as exc:
        recovery._read_only_title_field(Page(), legacy)
    assert exc.value.code == "title_selector_exception"
    assert "secret" not in str(exc.value)
    assert "private-id" not in str(exc.value)
    assert recovery._title_failure_code(exc.value) == "title_selector_exception"


def test_title_fallback_retry_interrupted_is_coded_without_exception_text(monkeypatch):
    recovery = _module()

    class Page:
        url = "https://editor.note.com/notes/existing/edit"
        def wait_for_timeout(self, milliseconds):
            raise RuntimeError("candidate editor private path")

    def legacy(_):
        raise RuntimeError("private title")

    monkeypatch.setattr(recovery.editor_readiness, "_explicit_title", lambda _: None)
    with pytest.raises(recovery.TitleReadInspectionError) as exc:
        recovery._read_only_title_field(Page(), legacy)
    assert exc.value.code == "title_retry_interrupted"
    assert "private" not in str(exc.value)


def test_title_failure_code_never_propagates_raw_exception():
    recovery = _module()
    assert recovery._title_failure_code(
        recovery.draft_audit.PrivateDraftAuditError("secret unpublished title")
    ) == "title_value_unreadable"
    assert recovery._title_failure_code(RuntimeError("https://note.com/notes/hidden/edit")) == "title_other"
    assert recovery._title_failure_code(
        recovery.TitleReadInspectionError("title_selector_unavailable")
    ) == "title_selector_unavailable"
    with pytest.raises(ValueError):
        recovery.TitleReadInspectionError("raw_private_browser_error")


def test_title_failure_audit_counts_are_independent_of_safety_state():
    recovery = _module()
    source = inspect.getsource(recovery._discover_verified_matches)
    assert 'if stage == "title_read":' in source
    assert 'title_failures[_title_failure_code(exc)] += 1' in source
    assert "counts[\"inspection_error\"] += 1" in source
    assert "record.snapshot.canonical_document_sha256" in source
    assert "context.close()" in source


def test_title_dom_probe_reads_only_fixed_presence_signals_without_page_content():
    recovery = _module()
    class Locator:
        def __init__(self, count):
            self.value = count
        def count(self):
            return self.value

    class Page:
        url = "https://editor.note.com/notes/private-test-id/edit"
        def evaluate(self, expression):
            assert expression == "document.readyState"
            return "complete"
        def locator(self, selector):
            assert selector in {
                "body",
                "input, textarea",
                '[contenteditable="true"], [contenteditable="plaintext-only"]',
                '[role="textbox"]',
                '[role="progressbar"], [aria-busy="true"]',
            }
            return Locator({
                "body": 1,
                "input, textarea": 0,
                '[contenteditable="true"], [contenteditable="plaintext-only"]': 0,
                '[role="textbox"]': 0,
                '[role="progressbar"], [aria-busy="true"]': 1,
            }[selector])
        def content(self):
            raise AssertionError("raw DOM/HTML must never be read")
        def screenshot(self, *args, **kwargs):
            raise AssertionError("screenshots are forbidden")
        def goto(self, *args, **kwargs):
            raise AssertionError("navigation is forbidden")

    signals = recovery._safe_title_dom_signals(Page())
    assert signals == (
        "ready_complete", "body_present", "inputs_missing",
        "editables_missing", "textboxes_missing", "busy_present",
    )
    assert set(signals).issubset(set(recovery.TITLE_DOM_SIGNAL_CODES))
    assert "private-test-id" not in str(signals)


def test_title_dom_probe_fails_closed_to_unknown_when_js_or_locator_fails():
    recovery = _module()
    class Page:
        url = "https://note.com/notes/private/edit"
        def evaluate(self, expression):
            raise RuntimeError("private title text 123")
        def locator(self, selector):
            raise RuntimeError("https://note.com/notes/private/edit")
    signals = recovery._safe_title_dom_signals(Page())
    assert signals == (
        "ready_unknown", "body_unknown", "inputs_unknown",
        "editables_unknown", "textboxes_unknown", "busy_unknown",
    )
    assert "private" not in str(signals)


def test_title_dom_probe_never_interprets_raw_browser_values_as_output():
    recovery = _module()
    class Locator:
        def count(self):
            return 0
    class Page:
        url = "https://note.com/notes/private/edit"
        def evaluate(self, expression):
            return "secret manuscript from browser"
        def locator(self, selector):
            return Locator()
    signals = recovery._safe_title_dom_signals(Page())
    assert signals[0] == "ready_unknown"
    assert all(signal.endswith("_missing") for signal in signals[1:])
    assert "secret" not in str(signals)


def test_title_dom_projection_drops_private_keys_and_arbitrary_page_data():
    recovery = _module()
    result = recovery.safe_recovery_projection({
        "title_dom_signal_counts": {
            "ready_complete": 2,
            "editables_missing": 2,
            "busy_present": 1,
            "draft_url": "https://note.com/notes/private-draft/edit",
            "raw_html": "private manuscript",
        },
    })
    assert result["title_dom_signal_counts"]["ready_complete"] == 2
    assert result["title_dom_signal_counts"]["editables_missing"] == 2
    assert result["title_dom_signal_counts"]["busy_present"] == 1
    assert set(result["title_dom_signal_counts"]) == set(recovery.TITLE_DOM_SIGNAL_CODES)
    assert "private-draft" not in str(result)
    assert "private manuscript" not in str(result)


def test_title_dom_probe_only_follows_existing_selector_unavailable_failure():
    recovery = _module()
    source = inspect.getsource(recovery._discover_verified_matches)
    assert 'stage == "title_read"' in source
    assert 'exc.code == "title_selector_unavailable"' in source
    assert "_safe_title_dom_signals(page)" in source
    assert 'counts["inspection_error"] += 1' in source
    assert "record.snapshot.canonical_document_sha256" in source
    forbidden = (".click(", ".fill(", "page.content(", "page.screenshot(", "requests.post(")
    function_source = inspect.getsource(recovery._safe_title_dom_signals)
    assert all(token not in function_source for token in forbidden)


def test_title_context_probe_distinguishes_http_route_browser_and_login_markers(monkeypatch):
    recovery = _module()
    class Response:
        status = 200
    class Page:
        url = "https://editor.note.com/notes/secret1/edit"
        def is_closed(self):
            return False
        def evaluate(self, expression):
            assert expression == "1"
            return 1
        def content(self):
            raise AssertionError("must not read raw HTML")
        def screenshot(self, *args, **kwargs):
            raise AssertionError("must not capture screenshots")
        def goto(self, *args, **kwargs):
            raise AssertionError("must not navigate")
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda p: False)
    signals = recovery._safe_title_context_signals(
        Page(), "https://note.com/notes/secret1/edit/", Response()
    )
    assert signals == (
        "http_2xx", "route_same_identity", "browser_open",
        "js_responding", "login_markers_absent",
    )
    assert set(signals).issubset(set(recovery.TITLE_CONTEXT_CODES))
    assert "secret1" not in str(signals)


def test_title_context_probe_classifies_another_editor_identity_and_client_http(monkeypatch):
    recovery = _module()
    class Response:
        status = 404
    class Page:
        url = "https://editor.note.com/notes/different/edit"
        def is_closed(self): return False
        def evaluate(self, expression): return 1
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda p: True)
    signals = recovery._safe_title_context_signals(
        Page(), "https://editor.note.com/notes/expected/edit", Response()
    )
    assert signals == (
        "http_4xx", "route_other_identity", "browser_open",
        "js_responding", "login_markers_present",
    )


def test_title_context_probe_unknowns_do_not_leak_browser_exception_content(monkeypatch):
    recovery = _module()
    class Response:
        @property
        def status(self):
            raise RuntimeError("secret HTTP response body")
    class Page:
        url = "https://note.com/notes/secret/edit"
        def is_closed(self):
            raise RuntimeError("secret screenshot text")
        def evaluate(self, expression):
            raise RuntimeError("secret user manuscript")
    def login(_):
        raise RuntimeError("session token secret")
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", login)
    signals = recovery._safe_title_context_signals(
        Page(), "https://note.com/notes/secret/edit", Response()
    )
    assert signals == (
        "http_unknown", "route_same_identity", "browser_unknown",
        "js_unavailable", "login_markers_unknown",
    )
    assert "secret" not in str(signals)
    assert "token" not in str(signals)


def test_title_context_probe_closed_page_and_invalid_routes_are_fail_closed(monkeypatch):
    recovery = _module()
    class Page:
        url = "https://editor.note.com/notes/secret/edit?malformed=1"
        def is_closed(self): return True
        def evaluate(self, expression):
            raise AssertionError("no JS required on closed page")
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda _: False)
    signals = recovery._safe_title_context_signals(
        Page(), "https://note.com/notes/secret/edit", None
    )
    assert signals == (
        "http_unknown", "route_unverified", "browser_closed",
        "js_unavailable", "login_markers_absent",
    )


def test_title_context_projection_allowlist_disallows_private_keys_and_error_text():
    recovery = _module()
    projection = recovery.safe_recovery_projection({
        "title_context_signal_counts": {
            "http_4xx": 1, "route_unverified": 1,
            "js_unavailable": 1,
            "raw_draft_url": "https://note.com/notes/private/edit",
            "response_body": "secret unpublished manuscript",
            "exception_detail": "private token",
        }
    })
    counts = projection["title_context_signal_counts"]
    assert set(counts) == set(recovery.TITLE_CONTEXT_CODES)
    assert counts["http_4xx"] == 1
    assert counts["route_unverified"] == 1
    assert counts["js_unavailable"] == 1
    assert "private" not in str(projection)
    assert "manuscript" not in str(projection)


def test_title_context_probe_only_inspects_title_selector_unavailable_without_mutation():
    recovery = _module()
    code = inspect.getsource(recovery._discover_verified_matches)
    assert 'exc.code == "title_selector_unavailable"' in code
    assert "_safe_title_context_signals(page, candidate, response)" in code
    assert "record.snapshot.canonical_document_sha256" in code
    assert 'counts["inspection_error"] += 1' in code
    diagnostic = inspect.getsource(recovery._safe_title_context_signals)
    for forbidden in (".click(", ".fill(", ".goto(", ".content(", ".screenshot(", "requests.post("):
        assert forbidden not in diagnostic


def test_title_route_shape_distinguishes_suffix_and_www_without_leaking_path():
    recovery = _module()
    classify = recovery._safe_title_route_shape
    base = "https://editor.note.com/notes/private123/edit"
    assert classify(base) == "shape_strict_supported"
    assert classify(base + "?tab=edit") == "shape_query_or_fragment"
    assert classify(base + "#draft") == "shape_query_or_fragment"
    assert classify("https://www.note.com/notes/private123/edit") == "shape_www_host"
    assert classify("http://note.com/notes/private123/edit") == "shape_non_https"
    assert classify("https://note.com/notes/private123/edit/extra") == "shape_other_path"
    assert classify("https://note.com/notes/invalid@id/edit") == "shape_invalid_identity"
    assert classify("https://example.invalid/notes/private123/edit") == "shape_other_host"
    assert "private123" not in str([classify(base + "?tab=edit"), classify(base)])


def test_atomic_dom_snapshot_one_read_does_not_return_private_browser_content():
    recovery = _module()
    class Page:
        url = "https://editor.note.com/notes/private123/edit"
        def __init__(self): self.evaluate_calls = 0
        def evaluate(self, code):
            self.evaluate_calls += 1
            assert "d.readyState" in code
            assert "querySelector" in code
            assert "textContent" not in code
            assert "innerHTML" not in code
            return {
                "ready": "complete", "body": True, "inputs": False,
                "editables": False, "textboxes": False, "busy": False,
                "untrusted": "secret manuscript and private link",
            }
        def content(self):
            raise AssertionError("never access HTML")
        def screenshot(self, *args, **kwargs):
            raise AssertionError("never capture screenshots")
        def goto(self, *args, **kwargs):
            raise AssertionError("no navigation")
    page = Page()
    signals = recovery._safe_title_atomic_dom_signals(page)
    assert signals == (
        "atomic_available", "atomic_ready_complete", "atomic_body_present",
        "atomic_inputs_missing", "atomic_editables_missing",
        "atomic_textboxes_missing", "atomic_busy_missing",
    )
    assert page.evaluate_calls == 1
    assert set(signals).issubset(set(recovery.TITLE_ATOMIC_DOM_CODES))
    assert "secret" not in str(signals)


def test_atomic_dom_snapshot_unavailable_is_safe_and_does_not_guess():
    recovery = _module()
    class Page:
        def evaluate(self, _):
            raise RuntimeError("private editor URL and secret draft title")
    assert recovery._safe_title_atomic_dom_signals(Page()) == ("atomic_unavailable",)
    class UnexpectedPage:
        def evaluate(self, _):
            return {"ready": "private", "body": "secret", "inputs": 1,
                    "editables": {}, "textboxes": [], "busy": None}
    unknown = recovery._safe_title_atomic_dom_signals(UnexpectedPage())
    assert unknown[0] == "atomic_available"
    assert unknown[1] == "atomic_ready_unknown"
    assert unknown[2:] == (
        "atomic_body_unknown", "atomic_inputs_unknown",
        "atomic_editables_unknown", "atomic_textboxes_unknown",
        "atomic_busy_unknown",
    )


def test_atomic_dom_projection_only_fixed_codes_and_no_candidate_identifiers():
    recovery = _module()
    result = recovery.safe_recovery_projection({
        "title_route_shape_counts": {
            "shape_www_host": 1,
            "untrusted_url": "https://note.com/notes/private123/edit",
        },
        "title_atomic_dom_counts": {
            "atomic_unavailable": 1,
            "raw_html": "a private manuscript",
        },
    })
    assert result["title_route_shape_counts"]["shape_www_host"] == 1
    assert result["title_atomic_dom_counts"]["atomic_unavailable"] == 1
    assert set(result["title_route_shape_counts"]) == set(recovery.TITLE_ROUTE_SHAPES)
    assert set(result["title_atomic_dom_counts"]) == set(recovery.TITLE_ATOMIC_DOM_CODES)
    assert "private" not in str(result)
    assert "manuscript" not in str(result)


def test_route_and_atomic_dom_diagnostics_do_not_change_recovery_authority():
    recovery = _module()
    source = inspect.getsource(recovery._discover_verified_matches)
    assert 'exc.code == "title_selector_unavailable"' in source
    assert "_safe_title_route_shape(str(page.url or \"\"))" in source
    assert "_safe_title_atomic_dom_signals(page)" in source
    assert "record.snapshot.canonical_document_sha256" in source
    assert 'counts["inspection_error"] += 1' in source
    for name in ("_safe_title_route_shape", "_safe_title_atomic_dom_signals"):
        diagnostic = inspect.getsource(getattr(recovery, name))
        for forbidden in (".click(", ".fill(", ".goto(", ".content(", ".screenshot(", "requests.post("):
            assert forbidden not in diagnostic


def test_private_screen_evidence_uses_fixed_bitmask_only():
    recovery = _module()
    class Page:
        def __init__(self, value):
            self.value = value
            self.calls = 0
        def evaluate(self, code):
            self.calls += 1
            assert "document" in code
            assert "innerText" in code
            assert "return mask" in code
            assert "console.log" not in code
            assert "fetch(" not in code
            return self.value
        def content(self):
            raise AssertionError("never return raw private DOM")
        def screenshot(self, *args, **kwargs):
            raise AssertionError("never capture private screenshot")
        def goto(self, *args, **kwargs):
            raise AssertionError("never navigate from diagnostic")
    page = Page(1 | 16 | 64 | 1024)
    result = recovery._safe_visible_screen_signals(page)
    assert result == (
        "surface_not_found_hint", "surface_header_present",
        "surface_button_present", "surface_short_visible_text",
    )
    assert page.calls == 1
    assert set(result).issubset(set(recovery.SCREEN_SIGNAL_CODES))


def test_private_screen_evidence_fails_closed_on_untrusted_values():
    recovery = _module()
    for raw in ("a private draft title", True, -1, 8192, 1.1, None, {}):
        class Page:
            def evaluate(self, _):
                return raw
        assert recovery._safe_visible_screen_signals(Page()) == ("surface_probe_unavailable",)
    class Page:
        def evaluate(self, _):
            raise RuntimeError("https://note.com/notes/secret/edit private article")
    result = recovery._safe_visible_screen_signals(Page())
    assert result == ("surface_probe_unavailable",)
    assert "secret" not in str(result)


def test_private_screen_evidence_has_explicit_zero_mask_and_disallows_unknown_bits():
    recovery = _module()
    class Page:
        def evaluate(self, _):
            return 0
    assert recovery._safe_visible_screen_signals(Page()) == ("surface_no_indicators",)


def test_private_screen_projections_allow_only_fixed_codes():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "failed_screen_signal_counts": {
            "surface_permission_hint": 2,
            "title": "secret",
            "raw_text": "private article content",
        },
        "control_screen_signal_counts": {
            "surface_editor_link_present": 17,
            "cookie": "session secret",
        },
    })
    assert set(safe["failed_screen_signal_counts"]) == set(recovery.SCREEN_SIGNAL_CODES)
    assert set(safe["control_screen_signal_counts"]) == set(recovery.SCREEN_SIGNAL_CODES)
    assert safe["failed_screen_signal_counts"]["surface_permission_hint"] == 2
    assert safe["control_screen_signal_counts"]["surface_editor_link_present"] == 17
    assert "private" not in str(safe)
    assert "cookie" not in str(safe)
    assert "secret" not in str(safe)


def test_private_screen_diagnostic_collects_failed_and_control_aggregates_separately():
    recovery = _module()
    code = inspect.getsource(recovery._discover_verified_matches)
    assert "_safe_visible_screen_signals(page)" in code
    assert 'control_screen_signal_counts[signal] += 1' in code
    assert 'failed_screen_signal_counts[signal] += 1' in code
    assert 'exc.code == "title_selector_unavailable"' in code
    assert "record.snapshot.canonical_document_sha256" in code
    surface = inspect.getsource(recovery._safe_visible_screen_signals)
    for forbidden in (".click(", ".fill(", ".goto(", ".content(", ".screenshot(", "requests.post(", "print("):
        assert forbidden not in surface


def test_official_list_proof_requires_account_and_exact_title_before_edit_navigation(monkeypatch):
    recovery = _module()
    events = []
    class Button:
        def count(self): return 1
        def evaluate(self, script):
            assert "closest('a[href]')" in script
            events.append("read_explicit_edit_href")
            return "/notes/prior-verified-draft/edit"
        def click(self, **kwargs):
            raise AssertionError("no click in ambiguous recovery")
    class Page:
        url = "https://note.com/"
        def set_default_timeout(self, _): pass
        def goto(self, url, **kwargs):
            if url == "https://note.com/notes":
                events.append("list_navigation")
            else:
                assert url == "https://note.com/notes/prior-verified-draft/edit"
                events.append("explicit_href_navigation")
            self.url = url
        def wait_for_timeout(self, _): pass
        def get_by_role(self, role, name, exact):
            assert role == "button" and name == "PRIVATE TITLEを編集" and exact
            return Button()
        def close(self): events.append("close")
    page = Page()
    class Context:
        def new_page(self): return page
    def check_account(p):
        assert p is page
        events.append("account_verified")
    monkeypatch.setattr(recovery.cloud, "_assert_expected_note_account", check_account)
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda p: False)
    monkeypatch.setattr(recovery.draft_audit, "_title_value", lambda _: "PRIVATE TITLE")
    monkeypatch.setattr(recovery.draft_audit, "_audit_current_page", lambda *args: {"title_match": True})
    monkeypatch.setattr(recovery, "_current_canonical_sha256", lambda _: "c" * 64)
    record = type("Record", (), {"snapshot": type("S", (), {"canonical_document_sha256": "c" * 64})()})()
    signals = recovery._probe_official_article_list(
        Context(), {"title": "PRIVATE TITLE", "manuscript": "hidden"}, record,
        ["https://note.com/notes/prior-verified-draft/edit"],
    )
    assert signals == {
        "account_proven", "list_open", "title_button_unique",
        "editor_route_verified", "editor_in_history", "editor_title_equal",
        "body_eyecatch_equal", "canonical_equal",
    }
    assert events == [
        "account_verified", "list_navigation", "read_explicit_edit_href",
        "explicit_href_navigation", "close",
    ]
    assert "PRIVATE TITLE" not in str(signals)
    assert "prior-verified-draft" not in str(signals)


def test_official_list_proof_zero_title_is_not_draft_absence(monkeypatch):
    recovery = _module()
    class Page:
        url = ""
        def set_default_timeout(self, _): pass
        def goto(self, url, **kwargs): self.url = url
        def wait_for_timeout(self, _): pass
        def get_by_role(self, *_args, **_kwargs):
            return type("B", (), {"count": lambda self: 0})()
        def close(self): pass
    monkeypatch.setattr(recovery.cloud, "_assert_expected_note_account", lambda p: None)
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda p: False)
    result = recovery._probe_official_article_list(
        type("C", (), {"new_page": lambda self: Page()})(),
        {"title": "secret", "manuscript": "secret"}, object(), [],
    )
    assert result == {"account_proven", "list_open", "title_button_not_visible", "list_scan_unavailable", "list_draft_view_open", "list_draft_title_not_visible", "list_draft_structure_unavailable"}
    assert "draft_absent" not in str(result)


def test_official_list_probe_fail_closed_when_account_not_proven(monkeypatch):
    recovery = _module()
    class Page:
        def set_default_timeout(self, _): pass
        def goto(self, *_args, **_kwargs): raise AssertionError("no list navigation without ownership proof")
        def close(self): pass
    def unauthorized(_):
        raise RuntimeError("private auth token and account")
    monkeypatch.setattr(recovery.cloud, "_assert_expected_note_account", unauthorized)
    result = recovery._probe_official_article_list(
        type("C", (), {"new_page": lambda self: Page()})(),
        {"title": "private", "manuscript": "private"}, object(), [],
    )
    assert result == {"account_unverified"}
    assert "private" not in str(result)


def test_official_list_proof_rejects_ambiguous_exact_title_without_click(monkeypatch):
    recovery = _module()
    class Button:
        def count(self): return 2
        def click(self, **kwargs): raise AssertionError("must not click ambiguous entries")
    class Page:
        url = ""
        def set_default_timeout(self, _): pass
        def goto(self, url, **kwargs): self.url = url
        def wait_for_timeout(self, _): pass
        def get_by_role(self, *_args, **_kwargs): return Button()
        def close(self): pass
    monkeypatch.setattr(recovery.cloud, "_assert_expected_note_account", lambda p: None)
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda p: False)
    result = recovery._probe_official_article_list(
        type("C", (), {"new_page": lambda self: Page()})(),
        {"title": "secret", "manuscript": "secret"}, object(), [],
    )
    assert result == {"account_proven", "list_open", "title_button_ambiguous"}


def test_official_list_projection_is_fixed_allowlist_only():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "official_list_proof_counts": {
            "account_proven": 1, "canonical_equal": 1,
            "draft_id": "secret private ID",
            "user_email": "private@example.com",
            "manuscript": "private body",
        }
    })
    assert set(safe["official_list_proof_counts"]) == set(recovery.OFFICIAL_LIST_CODES)
    assert safe["official_list_proof_counts"]["account_proven"] == 1
    assert "private" not in str(safe)
    assert "secret" not in str(safe)


def test_official_list_probe_is_diagnostic_and_does_not_authorize_recovery():
    recovery = _module()
    code = inspect.getsource(recovery._discover_verified_matches)
    assert "_probe_official_article_list(context, article, record, candidates)" in code
    assert "record.snapshot.canonical_document_sha256" in code
    assert "_safe_visible_screen_signals(page)" in code
    assert "matches.append(" in code
    probe = inspect.getsource(recovery._probe_official_article_list)
    for forbidden in ("_set_title(", "_set_body(", ".click(", ".fill(", "keyboard.", ".upload(", "mark_draft_created(", "requests.post(", ".screenshot("):
        assert forbidden not in probe
    assert "No list-only evidence can authorize recovery" in probe


def test_official_list_without_explicit_edit_href_does_not_click_or_invent_route(monkeypatch):
    recovery = _module()
    events = []
    class Button:
        def count(self): return 1
        def evaluate(self, _):
            events.append("inspect_href")
            return ""
        def click(self, **kwargs):
            raise AssertionError("no clicking existing title button")
    class Page:
        url = ""
        def set_default_timeout(self, _): pass
        def goto(self, url, **kwargs):
            assert url == "https://note.com/notes"
            events.append("official_list")
            self.url = url
        def wait_for_timeout(self, _): pass
        def get_by_role(self, *_args, **_kwargs): return Button()
        def close(self): events.append("close")
    monkeypatch.setattr(recovery.cloud, "_assert_expected_note_account", lambda _: events.append("account"))
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda _: False)
    result = recovery._probe_official_article_list(
        type("C", (), {"new_page": lambda self: Page()})(),
        {"title": "private", "manuscript": "private"}, object(), [],
    )
    assert result == {
        "account_proven", "list_open", "title_button_unique", "editor_route_unverified",
    }
    assert events == ["account", "official_list", "inspect_href", "close"]


def test_bounded_list_scan_scrolling_discovers_exact_title_without_click(monkeypatch):
    recovery = _module()
    calls = []
    class Button:
        def count(self):
            return int("scroll" in calls)
    class Page:
        def get_by_role(self, role, name, exact):
            assert role == "button" and exact and name == "secretを編集"
            return Button()
        def evaluate(self, script, *args):
            if "querySelectorAll" in script:
                return 0  # only a bounded fixed code leaves the private browser
            if "window.scrollBy" in script:
                calls.append("scroll")
                return 1
            if "getAttribute('href')" in script:
                raise AssertionError("do not paginate after title found")
            raise AssertionError("unexpected probe")
        def wait_for_timeout(self, n):
            assert n <= 1000
    codes = recovery._bounded_official_list_scan(Page(), "secret")
    assert "list_scroll_attempted" in codes
    assert "list_title_found_after_scroll" in codes
    assert "list_pagination_followed" not in codes
    assert len(calls) == 1
    assert "secret" not in str(codes)


def test_bounded_list_scan_detects_filters_and_requires_explicit_same_origin_page_link():
    recovery = _module()
    class Page:
        url = "https://note.com/notes"
        def __init__(self): self.scrolls = 0; self.navigated = []
        def get_by_role(self, role, name, exact):
            return type("B", (), {"count": lambda self: 0})()
        def evaluate(self, script, *args):
            if "return item ? item.getAttribute('href')" in script:
                return "/notes?page=2" if not self.navigated else ""
            if "window.scrollBy" in script:
                self.scrolls += 1
                return 0
            if "querySelectorAll" in script:
                return 1 | 2 | 4
            raise AssertionError("unexpected evaluation")
        def wait_for_timeout(self, _): pass
        def goto(self, url, **kwargs):
            self.navigated.append(url); self.url=url
    page=Page()
    codes=recovery._bounded_official_list_scan(page,"secret")
    assert "list_draft_filter_visible" in codes
    assert "list_more_control_visible" in codes
    assert "list_pagination_visible" in codes
    assert "list_pagination_followed" in codes
    assert "list_scroll_no_motion" in codes
    assert "list_scan_limit_reached" in codes
    assert page.navigated == ["https://note.com/notes?page=2"]
    assert page.scrolls <= 12


def test_bounded_list_scan_never_navigates_to_external_or_malformed_pagination():
    recovery=_module()
    class Page:
        url="https://note.com/notes"
        def __init__(self, href):self.href=href;self.visits=[]
        def get_by_role(self,*args,**kwargs):
            return type("B", (), {"count":lambda self:0})()
        def evaluate(self,script,*args):
            if "return item ? item.getAttribute('href')" in script:return self.href
            if "window.scrollBy" in script:return 0
            if "querySelectorAll" in script:return 0
        def wait_for_timeout(self,_):pass
        def goto(self, url, **kwargs):
            self.visits.append(url)
            raise AssertionError("must not leave official article list")
    for href in ("https://evil.example/notes?page=2",
                 "https://note.com/notes/new?page=2",
                 "https://note.com/notes?page=2&token=secret",
                 "https://note.com/notes?page=two",
                 "javascript:alert(1)", "//evil.example/notes?page=2"):
        p=Page(href)
        codes=recovery._bounded_official_list_scan(p,"private")
        assert not p.visits
        assert "list_pagination_followed" not in codes
        assert "private" not in str(codes)


def test_bounded_scan_counters_are_fixed_codes_and_not_recovery_authority():
    recovery=_module()
    safe=recovery.safe_recovery_projection({
       "official_list_scan_counts": {"list_title_found_after_scroll": 1,
           "private_draft_id": "secret", "raw_html": "manuscript"},
    })
    assert set(safe["official_list_scan_counts"]) == set(recovery.OFFICIAL_LIST_SCAN_CODES)
    assert safe["official_list_scan_counts"]["list_title_found_after_scroll"] == 1
    assert "secret" not in str(safe) and "manuscript" not in str(safe)
    source=inspect.getsource(recovery._bounded_official_list_scan)
    for forbidden in (".click(", ".fill(", ".screenshot(", ".content(", "requests.post("):
        assert forbidden not in source
    main=inspect.getsource(recovery._discover_verified_matches)
    assert "official_list_scan_counts" in main
    assert "matches.append(" in main



def test_official_list_layout_counters_are_fixed_read_only_codes():
    recovery = _module()
    expected = {
        "list_root_scrollable", "list_nested_scrollable",
        "list_main_populated", "list_any_edit_control",
        "list_loading_visible", "list_scroll_overflow_hidden",
    }
    assert expected.issubset(set(recovery.OFFICIAL_LIST_SCAN_CODES))
    class Button:
        def count(self): return 0
    class Page:
        url = "https://note.com/notes"
        def __init__(self): self.scrolls = 0; self.navigation = []
        def get_by_role(self, role, name, exact):
            assert role == "button" and exact and name == "sensitiveを編集"
            return Button()
        def evaluate(self, script, *args):
            if "querySelectorAll" in script:
                return 16 | 32 | 64 | 128 | 256 | 512
            if "window.scrollBy" in script:
                self.scrolls += 1
                return 0
            if "return item ? item.getAttribute('href')" in script:
                return ""
            raise AssertionError("unexpected read-only probe")
        def wait_for_timeout(self, _): pass
        def goto(self, url, **kwargs):
            self.navigation.append(url)
            raise AssertionError("no navigation without explicit safe next-page anchor")
    page = Page()
    codes = recovery._bounded_official_list_scan(page, "sensitive")
    assert expected.issubset(codes)
    assert "list_scan_limit_reached" in codes
    assert "sensitive" not in str(codes)
    assert page.scrolls <= 4 and not page.navigation

    safe = recovery.safe_recovery_projection({
        "official_list_scan_counts": {
            "list_nested_scrollable": 1,
            "private_id": "secret",
            "rendered_text": "private manuscript",
        }
    })
    counts = safe["official_list_scan_counts"]
    assert set(counts) == set(recovery.OFFICIAL_LIST_SCAN_CODES)
    assert counts["list_nested_scrollable"] == 1
    for forbidden in ("secret", "manuscript", "private_id", "rendered_text"):
        assert forbidden not in str(safe)


def test_official_list_layout_invalid_mask_fails_closed_without_recovery_authority():
    recovery = _module()
    class Button:
        def count(self): return 0
    class Page:
        def get_by_role(self, *_args, **_kwargs): return Button()
        def evaluate(self, script, *args):
            if "querySelectorAll" in script: return 1 << 10
            raise AssertionError("layout mask invalid: no followup operations")
    codes = recovery._bounded_official_list_scan(Page(), "private")
    assert codes == {"list_scan_unavailable"}
    assert "list_title_found_after_scroll" not in codes

    source = inspect.getsource(recovery._bounded_official_list_scan)
    for forbidden in (".click(", ".fill(", ".screenshot(", ".content(", "requests.post("):
        assert forbidden not in source



def test_same_account_note_api_get_response_is_bounded_and_private():
    import json
    recovery = _module()
    class Request:
        method = "GET"
    class Response:
        request = Request()
        status = 200
        headers = {"content-type": "application/json", "content-length": "160"}
        def __init__(self, url, payload):
            self.url = url
            self.payload = payload
            self.body_calls = 0
        def body(self):
            self.body_calls += 1
            return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
    response = Response(
        "https://editor.note.com/api/v3/articles?limit=20&private=opaque",
        {"data": [{"title": "other", "id": "private-id"},
                  {"title": "Terra private draft", "id": "target-id", "status": "draft"}]},
    )
    flags = recovery._safe_note_api_response_signals(response, "Terra private draft")
    assert flags == {
        "api_get_observed", "api_json_readable", "api_target_title_seen",
        "api_path_article_hint", "api_root_object", "api_title_field_seen",
        "api_nested_collection_seen",
    }
    assert response.body_calls == 1
    for secret in ("target-id", "private-id", "Terra private draft", "opaque"):
        assert secret not in str(flags)
    assert flags.issubset(recovery.OFFICIAL_LIST_SCAN_CODES)


def test_note_api_observation_rejects_untrusted_hosts_mutating_requests_and_non_api_routes():
    import json
    recovery = _module()
    class Response:
        status = 200
        headers = {"content-type": "application/json"}
        def __init__(self, url, method):
            self.url = url
            self.request = type("Request", (), {"method": method})()
        def body(self):
            raise AssertionError("must never inspect a disallowed response")
    for url, method in (
        ("https://evil.example/api/v3/notes", "GET"),
        ("https://note.com.evil.example/api/v3/notes", "GET"),
        ("http://editor.note.com/api/v3/notes", "GET"),
        ("https://editor.note.com/api/v3/notes", "POST"),
        ("https://editor.note.com/api/v3/notes", "DELETE"),
        ("https://note.com/notes", "GET"),
        ("https://editor.note.com/private", "GET"),
        ("https://note.com:8080/api/v3/notes", "GET"),
    ):
        assert recovery._safe_note_api_response_signals(
            Response(url, method), "Terra private draft"
        ) == set()


def test_note_api_observation_caps_payload_and_never_proves_draft_lifecycle():
    recovery = _module()
    class Request:
        method = "GET"
    class Response:
        request = Request()
        status = 200
        url = "https://editor.note.com/api/v2/notes"
        def __init__(self, headers, data=b""):
            self.headers = headers
            self.data = data
        def body(self):
            return self.data
    oversized = Response(
        {"content-type": "application/json", "content-length": "10485760"}
    )
    assert recovery._safe_note_api_response_signals(
        oversized, "private"
    ) == {"api_get_observed", "api_path_article_hint", "api_response_oversize"}
    unreadable = Response(
        {"content-type": "application/json"}, b"invalid JSON"
    )
    assert recovery._safe_note_api_response_signals(
        unreadable, "private"
    ) == {"api_get_observed", "api_path_article_hint", "api_json_unreadable"}
    not_json = Response({"content-type": "text/html"})
    assert recovery._safe_note_api_response_signals(
        not_json, "private"
    ) == {"api_get_observed", "api_path_article_hint"}
    source = inspect.getsource(recovery._probe_official_article_list)
    assert 'page.on("response"' in source
    assert "api_target_title_seen" not in inspect.getsource(
        recovery.require_unique_recovery_match
    )
    for token in (".click(", ".fill(", ".screenshot(", "requests.post("):
        assert token not in inspect.getsource(recovery._safe_note_api_response_signals)


def test_note_api_evidence_projection_rejects_ids_titles_and_unknown_codes():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "official_list_scan_counts": {
            "api_get_observed": 1,
            "api_target_title_seen": 1,
            "private_id": "opaque",
            "raw_body": "private manuscript",
            "actual_api_url": "https://editor.note.com/api/secret",
        }
    })
    counts = safe["official_list_scan_counts"]
    assert counts["api_get_observed"] == 1
    assert counts["api_target_title_seen"] == 1
    assert set(counts) == set(recovery.OFFICIAL_LIST_SCAN_CODES)
    assert "private manuscript" not in str(safe)
    assert "opaque" not in str(safe)
    assert "api/secret" not in str(safe)


def test_api_response_codes_classify_http_failure_without_reading_private_bodies():
    recovery = _module()
    class R:
        request = type("Req", (), {"method": "GET"})()
        url = "https://editor.note.com/api/v3/articles"
        headers = {"content-type": "application/json"}
        def __init__(self, status): self.status = status
        def body(self): raise AssertionError("non-success body must not be read")
    expectations = {
        401: "api_http_auth_denied",
        403: "api_http_auth_denied",
        404: "api_http_not_found",
        429: "api_http_rate_limited",
        503: "api_http_server_error",
        302: "api_http_other_non_success",
    }
    for status, reason in expectations.items():
        flags = recovery._safe_note_api_response_signals(R(status), "secret")
        assert flags == {
            "api_get_observed", "api_path_article_hint",
            "api_http_non_success", reason,
        }
        assert "secret" not in str(flags)


def test_api_response_classifies_structure_without_private_values():
    import json
    recovery = _module()
    class R:
        request = type("Req", (), {"method": "GET"})()
        status = 200
        headers = {"content-type": "application/json"}
        def __init__(self, url, payload):
            self.url = url
            self.payload = payload
        def body(self): return json.dumps(self.payload).encode("utf-8")
    examples = (
        ("https://editor.note.com/api/v3/profile",
         {"profile": {"display_name": "secret"}}, {
            "api_get_observed", "api_path_account_hint",
            "api_json_readable", "api_root_object",
         }),
        ("https://editor.note.com/api/v3/articles",
         {"data": [], "pagination": {"has_next": False}}, {
            "api_get_observed", "api_path_article_hint",
            "api_json_readable", "api_root_object",
            "api_empty_collection_seen", "api_pagination_hint",
         }),
        ("https://editor.note.com/api/v3/anything",
         [{"title": "other draft", "id": "private-1"}], {
            "api_get_observed", "api_path_other",
            "api_json_readable", "api_root_array",
            "api_title_field_seen", "api_nested_collection_seen",
         }),
    )
    for url, payload, expected in examples:
        flags = recovery._safe_note_api_response_signals(R(url, payload), "Terra")
        assert flags == expected
        for raw in ("secret", "other draft", "private-1"):
            assert raw not in str(flags)


def test_api_response_observation_checks_capture_limit_before_body_decode():
    recovery = _module()
    source = inspect.getsource(recovery._probe_official_article_list)
    assert 'if api_seen[0] >= _MAX_NOTE_API_RESPONSES:' in source
    assert source.index('if api_seen[0] >= _MAX_NOTE_API_RESPONSES:') < source.index(
        'signals = _safe_note_api_response_signals('
    )
    assert "api_target_title_seen" not in inspect.getsource(recovery.require_unique_recovery_match)
    assert "api_target_title_seen" not in inspect.getsource(recovery.run)


def test_api_diagnostics_projection_remains_opaque_and_allowlisted():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "official_list_scan_counts": {
            "api_http_auth_denied": 1,
            "api_json_readable": 1,
            "api_pagination_hint": 1,
            "private_draft_id": "secret-uuid",
            "api_path": "/api/v3/articles/private-uuid",
            "body": "confidential text",
        },
    })
    counts = safe["official_list_scan_counts"]
    assert counts["api_http_auth_denied"] == 1
    assert counts["api_pagination_hint"] == 1
    assert set(counts) == set(recovery.OFFICIAL_LIST_SCAN_CODES)
    for raw in ("secret-uuid", "private-uuid", "confidential text"):
        assert raw not in str(safe)



def test_draft_view_probe_only_uses_bounded_same_origin_readonly_url(monkeypatch):
    recovery = _module()
    events = []
    class Button:
        def count(self): return 1
        def click(self, **_):
            raise AssertionError("must not click controls in uncertain recovery")
    class Page:
        url = "https://note.com/notes"
        def goto(self, url, **kwargs):
            assert url == "https://note.com/notes?kind=draft"
            assert kwargs["wait_until"] == "domcontentloaded"
            events.append("read_only_draft_view_get")
            self.url = url
        def wait_for_timeout(self, timeout):
            assert timeout <= 1500
        def evaluate(self, script, *args):
            assert "querySelectorAll" in script
            return 1 | 2 | 4 | 8
        def get_by_role(self, role, name, exact):
            assert role == "button" and name == "secretを編集" and exact is True
            return Button()
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda _: False)
    codes = recovery._bounded_draft_view_probe(Page(), "secret")
    assert codes == {
        "list_draft_view_open", "list_draft_title_unique",
        "list_self_articles_nav_visible", "list_draft_filter_nav_visible",
        "list_draft_filter_selected", "list_draft_any_edit_control",
    }
    assert events == ["read_only_draft_view_get"]
    assert "secret" not in str(codes)


def test_draft_view_probe_rejects_redirect_and_logout_without_inspecting_title(monkeypatch):
    recovery = _module()
    class Page:
        def __init__(self, redirect): self.url = ""
        def goto(self, url, **kwargs): self.url = self.redirect
        def wait_for_timeout(self, _): pass
        def evaluate(self, *_): raise AssertionError("redirected view cannot be trusted")
        def get_by_role(self, *_args, **_kwargs):
            raise AssertionError("redirected view cannot be trusted")
    for bad in (
        "https://evil.example/notes?kind=draft",
        "https://note.com/notes",
        "https://note.com/notes?kind=all",
        "http://note.com/notes?kind=draft",
        "https://note.com/notes?kind=draft&token=secret",
        "https://note.com/notes/new?kind=draft",
    ):
        page=Page(bad);page.redirect=bad
        assert recovery._bounded_draft_view_probe(page,"secret") == {"list_draft_route_unverified"}
    p=Page("https://note.com/notes?kind=draft")
    p.redirect="https://note.com/notes?kind=draft"
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda _: True)
    assert recovery._bounded_draft_view_probe(p, "secret") == {"list_draft_route_unverified"}


def test_draft_view_probe_zero_buttons_is_not_proof_of_absence(monkeypatch):
    recovery = _module()
    class Page:
        url = "https://note.com/notes"
        def goto(self, url, **kwargs): self.url = url
        def wait_for_timeout(self, _): pass
        def evaluate(self, *_): return 0
        def get_by_role(self, *_args, **_kwargs):
            return type("Button", (), {"count": lambda self: 0})()
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out", lambda _: False)
    result = recovery._bounded_draft_view_probe(Page(), "private")
    assert result == {"list_draft_view_open", "list_draft_title_not_visible"}
    assert "draft_absent" not in str(result)
    source = inspect.getsource(recovery._bounded_draft_view_probe)
    for forbidden in (".click(", ".fill(", ".screenshot(", ".content(", "requests.post(", "/api/"):
        assert forbidden not in source


def test_draft_view_probe_fixed_code_projection_and_account_gate():
    recovery = _module()
    safe = recovery.safe_recovery_projection({
        "official_list_scan_counts": {
            "list_draft_view_open": 1,
            "list_draft_title_unique": 1,
            "list_draft_any_edit_control": 1,
            "draft_private_id": "secret-id",
            "private_title": "secret title",
        }
    })
    counts = safe["official_list_scan_counts"]
    assert set(counts) == set(recovery.OFFICIAL_LIST_SCAN_CODES)
    assert counts["list_draft_view_open"] == 1
    assert "secret-id" not in str(safe)
    assert "secret title" not in str(safe)
    source = inspect.getsource(recovery._probe_official_article_list)
    assert source.index('codes.add("account_proven")') < source.index('_bounded_draft_view_probe(')
    assert "title_button_not_visible" in source
    assert "list_draft_view_open" in source



def test_owner_draft_view_extended_dom_mask_is_allowlisted_and_private(monkeypatch):
    """Only fixed booleans, never article identifiers, DOM or private text."""
    recovery = _module()
    mapping = {
        16: "list_owner_nav_anchor",
        32: "list_owner_nav_button",
        64: "list_owner_nav_note_href",
        128: "list_title_exact_anchor",
        256: "list_title_exact_plain_text",
        512: "list_existing_edit_href",
        1024: "list_article_card_present",
        2048: "list_profile_menu_trigger",
        4096: "list_main_content_populated",
        8192: "list_empty_or_error_notice",
        16384: "list_loading_placeholder",
        32768: "list_embedded_frame",
    }
    class Button:
        def count(self): return 0
    class Page:
        url="https://note.com/notes"
        def __init__(self, mask): self.mask=mask;self.visits=[]
        def goto(self, url, **kwargs):
            assert url == "https://note.com/notes?kind=draft"
            self.url=url
            self.visits.append(url)
        def wait_for_timeout(self, n): assert n <= 1500
        def evaluate(self, script, *args):
            assert "querySelectorAll" in script
            assert len(args) == 1 and args[0] == "PRIVATE TERRA TITLE"
            return self.mask
        def get_by_role(self, role, name, exact):
            assert (role, name, exact) == ("button", "PRIVATE TERRA TITLEを編集", True)
            return Button()
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out",lambda _: False)
    for bit, code in mapping.items():
        p=Page(bit)
        evidence=recovery._bounded_draft_view_probe(p,"PRIVATE TERRA TITLE")
        assert evidence == {
            "list_draft_view_open", "list_draft_title_not_visible", code
        }
        assert p.visits == ["https://note.com/notes?kind=draft"]
        assert "PRIVATE" not in str(evidence)
    expected=set(mapping.values())
    assert expected.issubset(set(recovery.OFFICIAL_LIST_SCAN_CODES))
    safe=recovery.safe_recovery_projection({
        "official_list_scan_counts": {
            **{code:1 for code in expected},
            "actual_dom": "<private>secret manuscript</private>",
            "private_note_id": "nsecret",
        }
    })
    assert set(safe["official_list_scan_counts"]) == set(recovery.OFFICIAL_LIST_SCAN_CODES)
    assert "secret" not in str(safe)


def test_owner_draft_view_mask_invalid_and_oversize_fail_closed(monkeypatch):
    recovery = _module()
    class Page:
        url="https://note.com/notes"
        def goto(self, url, **kwargs): self.url=url
        def wait_for_timeout(self, _): pass
        def __init__(self, mask): self.mask=mask
        def evaluate(self, *_args): return self.mask
        def get_by_role(self, *_args, **_kwargs):
            return type("Button", (), {"count": lambda self: 0})()
    monkeypatch.setattr(recovery.draft_audit.note_base, "_looks_logged_out",lambda _: False)
    for value in (True, None, 65536, -1, "private", 2.5):
        result = recovery._bounded_draft_view_probe(Page(value), "secret")
        assert result == {
            "list_draft_view_open",
            "list_draft_structure_unavailable",
            "list_draft_title_not_visible",
        }
    source = inspect.getsource(recovery._bounded_draft_view_probe)
    assert "document.querySelectorAll" in source
    assert "getBoundingClientRect" in source
    assert "location.origin" in source
    assert "api/" not in source
    for forbidden in (".click(", ".fill(", ".screenshot(", ".content(", "requests.post(", "console.log("):
        assert forbidden not in source



def test_owner_menu_navigation_follows_only_exact_verified_link_after_account_proof(monkeypatch):
    recovery = _module()
    events = []
    class Link:
        def count(self): return 1
        def get_attribute(self, key): assert key=="href";return "/notes"
        def is_visible(self): return True
    class Page:
        url = "https://note.com/settings/profile"
        def get_by_role(self, role, name, exact):
            assert (role,name,exact)==("link","自分の記事",True)
            return Link()
        def goto(self, url, **kwargs):
            assert url=="https://note.com/notes"
            assert kwargs["wait_until"]=="domcontentloaded"
            events.append("navigate_verified_link")
            self.url=url
        def wait_for_timeout(self, ms):assert ms<=1500
        def evaluate(self, script, *args):
            assert len(args)==1 and args[0]=="private title"
            return 1|2|4|8
    monkeypatch.setattr(recovery.draft_audit.note_base,"_looks_logged_out",lambda _: False)
    evidence = recovery._safe_owner_articles_menu_route(Page(),"private title")
    assert evidence == {
        "menu_link_exact", "menu_route_open", "menu_route_main_populated",
        "menu_route_article_card_present", "menu_route_edit_control_present",
        "menu_route_title_visible",
    }
    assert events==["navigate_verified_link"]
    assert "private title" not in str(evidence)


def test_owner_menu_navigation_opens_only_unique_semantic_menu_trigger(monkeypatch):
    recovery = _module()
    events=[]
    class Link:
        def __init__(self, page):self.page=page
        def count(self):return 1 if self.page.menu_open else 0
        def is_visible(self):return self.page.menu_open
        def get_attribute(self, name):assert name=="href";return "/notes?kind=draft"
    class Trigger:
        def get_attribute(self, key):assert key=="aria-label";return "アカウントメニュー"
        def is_visible(self):return True
        def click(self, **kwargs):
            events.append("open_pure_menu")
            self.page.menu_open=True
    class Triggers:
        def __init__(self,page):self.page=page
        def count(self):return 1
        def nth(self,i):
            assert i==0
            t=Trigger();t.page=self.page;return t
    class Page:
        url="https://note.com/settings/profile"
        menu_open=False
        def get_by_role(self, *_args,**_kwargs):return Link(self)
        def locator(self, sel):
            assert sel=='button[aria-haspopup="menu"]:visible'
            return Triggers(self)
        def goto(self,url,**kwargs):
            assert url=="https://note.com/notes?kind=draft"
            events.append("navigate_verified_link")
            self.url=url
        def wait_for_timeout(self,_):pass
        def evaluate(self, script, *args):return 0
    monkeypatch.setattr(recovery.draft_audit.note_base,"_looks_logged_out",lambda _: False)
    evidence=recovery._safe_owner_articles_menu_route(Page(),"secret")
    assert evidence=={
        "menu_trigger_unique","menu_opened","menu_link_exact","menu_route_open",
    }
    assert events==["open_pure_menu","navigate_verified_link"]


def test_owner_menu_navigation_rejects_bad_routes_and_ambiguous_link(monkeypatch):
    recovery=_module()
    monkeypatch.setattr(recovery.draft_audit.note_base,"_looks_logged_out",lambda _: False)
    class Link:
        def __init__(self, href, count=1):self.href=href;self.number=count
        def count(self):return self.number
        def is_visible(self):return True
        def get_attribute(self, name):return self.href
    class Page:
        url="https://note.com/settings/profile"
        def __init__(self, href, count=1):self.href=href;self.number=count
        def get_by_role(self,*_args,**_kwargs):return Link(self.href,self.number)
        def goto(self,*_args,**_kwargs):raise AssertionError("must not navigate")
        def evaluate(self,*_args):raise AssertionError("must not inspect")
    for href in (
        "https://evil.example/notes", "//evil.example/notes",
        "https://note.com.evil.example/notes", "http://note.com/notes",
        "https://note.com/notes/new", "/notes?status=draft",
        "/notes?kind=draft&private=secret", "/notes#secret",
        "javascript:alert('bad')",
    ):
        assert recovery._safe_owner_articles_menu_route(Page(href),"secret")=={
            "menu_link_rejected"
        }
    assert recovery._safe_owner_articles_menu_route(Page("/notes",count=2),"secret")=={
        "menu_link_ambiguous"
    }


def test_owner_menu_navigation_fails_closed_without_valid_account_setting_route(monkeypatch):
    recovery=_module()
    class Page:
        url="https://evil.example/settings/profile"
        def get_by_role(self,*_args,**_kwargs):raise AssertionError("no link scan")
    assert recovery._safe_owner_articles_menu_route(Page(),"private")=={
        "menu_origin_unverified"
    }


def test_owner_menu_navigation_never_mutates_editor_or_leaks_private_fields():
    import inspect
    recovery=_module()
    source=inspect.getsource(recovery._safe_owner_articles_menu_route)
    assert "cloud.PROFILE_SETTINGS_URL" in source
    assert "get_by_role" in source
    assert "aria-haspopup" in source
    for forbidden in (
        "requests.post(", ".fill(", ".upload(", ".screenshot(", 
        "mark_draft_created(", "create_draft(", ".set_input_files(", "page.content(",
    ):
        assert forbidden not in source
    safe=recovery.safe_recovery_projection({"official_list_scan_counts":{
        "menu_route_open":1,"menu_link_rejected":1,
        "real_article_id":"nprivate","article_body":"confidential"
    }})
    assert safe["official_list_scan_counts"]["menu_route_open"]==1
    assert safe["official_list_scan_counts"]["menu_link_rejected"]==1
    assert "nprivate" not in str(safe)
    assert "confidential" not in str(safe)
    probe=inspect.getsource(recovery._probe_official_article_list)
    assert probe.index('codes.add("account_proven")')<probe.index("_safe_owner_articles_menu_route(")
