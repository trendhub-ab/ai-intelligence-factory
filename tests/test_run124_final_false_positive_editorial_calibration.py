import os
import sys
import types
import unittest
from pathlib import Path

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")
try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception): pass
    class Client:
        def __init__(self, **_kwargs): self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

import pipeline


class Run124FinalCalibrationTests(unittest.TestCase):
    def test_one_request_one_response_protocol_shape_is_not_numeric_claim(self):
        draft = "従来の単純な1リクエスト・1レスポンスでは、長時間処理の途中制御に対応しにくい。"
        failures = pipeline._find_unsupported_numeric_claims(draft, "The protocol uses a request-response interaction model.")
        self.assertFalse(any("1リクエスト" in item for item in failures), failures)

    def test_request_rate_claim_remains_guarded(self):
        draft = "上限は毎秒1リクエスト・1レスポンスである。"
        failures = pipeline._find_unsupported_numeric_claims(draft, "Official documentation describes request-response messaging but gives no rate limit.")
        self.assertTrue(any("1リクエスト" in item for item in failures), failures)

    def test_request_count_without_paired_response_remains_guarded(self):
        draft = "処理回数は1リクエスト。"
        failures = pipeline._find_unsupported_numeric_claims(draft, "Official documentation describes requests.")
        self.assertTrue(any("1リクエスト" in item for item in failures), failures)

    def test_wimse_full_name_is_supported_when_acronym_is_in_primary_source(self):
        draft = "ロードマップでは、IETFのWIMSE（Workload Identity in Multi-System Environments）作業部会などの標準化団体と連携する方針が明記されている。"
        source = "The roadmap says the project will coordinate with IETF OAuth and WIMSE working groups."
        failures = pipeline._find_source_boundary_violations(draft, source, repo_name="modelcontextprotocol")
        self.assertFalse(any("Multi-System Environments" in item for item in failures), failures)

    def test_unrelated_multi_system_product_is_still_blocked(self):
        draft = "導入ではAcme Multi-System Environmentsを標準で採用する。"
        source = "The roadmap mentions WIMSE and OAuth."
        failures = pipeline._find_source_boundary_violations(draft, source, repo_name="modelcontextprotocol")
        self.assertTrue(failures, failures)

    def test_real_esp32_style_register_stack_is_reviewed(self):
        article = """### 再現性を先に固める
ファームウェア開発の再現性を担保する第一歩は、公式環境を固定することだ。

### 実機接続を分離する
シリアルポートをネットワーク化する工夫が、AIエージェント運用でも鍵となる。

### 制約
非常に魅力的なワークフローに見えるが、明確な留意点がある。実務では限定環境から始めるのが妥当な判断と言えます。"""
        signals = pipeline._ai_style_composite_signals(article)
        self.assertTrue(signals["editorial_register_dense"], signals)
        self.assertTrue(signals["editorial_register_companion"], signals)
        self.assertTrue(signals["high"], signals)

    def test_kobo_style_promotional_close_plus_evaluation_is_reviewed(self):
        article = """### 使いどころ
Sidekickの存在は示唆的です。非常に魅力的なプロジェクトで、明確なユースケースがあります。

### 制約
対応端末は限られています。まず手元の端末で試すのが一番の近道です。

### 次にすること
小さな検証で開発体験の面白さを確かめてみてはいかがでしょうか。"""
        signals = pipeline._ai_style_composite_signals(article)
        self.assertTrue(signals["editorial_register_dense"], signals)
        self.assertTrue(signals["editorial_register_companion"], signals)
        self.assertTrue(signals["high"], signals)

    def test_natural_copy_with_one_evaluation_and_direct_close_is_not_reviewed(self):
        article = """### まず試すなら
この変更で興味深いのは、既存設定を残したまま差分を見られることだ。私は検証環境だけで試す。

### 止めどき
ログが増えすぎるなら採用しない。チームへ広げるのは、運用負荷を一週間見てからでいい。"""
        signals = pipeline._ai_style_composite_signals(article)
        self.assertFalse(signals["editorial_register_dense"], signals)
        self.assertFalse(signals["high"], signals)

    def test_run124_adds_no_provider_call_site(self):
        root = Path(pipeline.__file__).resolve().parent
        py = (root / "pipeline.py").read_text(encoding="utf-8")
        self.assertEqual(7, py.count("_generate_via_chat("))
        self.assertEqual(1, py.count("genai.Client("))


if __name__ == "__main__":
    unittest.main()
