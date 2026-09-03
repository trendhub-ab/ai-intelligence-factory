from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
RUN217 = ROOT / "docs" / "reference" / "RUN217_ZERO_API_MONETIZATION_READINESS.md"
RUN218 = ROOT / "docs" / "reference" / "RUN218_MEMBER_UX_RECONCILIATION.md"
RUN220 = ROOT / "docs" / "reference" / "RUN220_MEMBER_DB_CANONICAL_CUTOVER.md"

CANONICAL_HOME_ID = "3c5479ff-dca9-8103-bff0-f2d5f408d35f"
SUPERSEDED_HOME_ID = "3d0479ff-dca9-819e-9da0-c951225de6b3"
CURRENT_DB_ID = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
CURRENT_DS_ID = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"
PRE_RUN220_DB_ID = "d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1"
PRE_RUN220_DS_ID = "d1461b6f-0940-4bf9-803a-6686a37c4ba2"
LEGACY_DS_ID = "ec2ac2b3-89b6-4242-89b9-e94060826fca"


class Run218MemberUxReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = README.read_text(encoding="utf-8")
        cls.spec = SPEC.read_text(encoding="utf-8")
        cls.run217 = RUN217.read_text(encoding="utf-8")
        cls.run218 = RUN218.read_text(encoding="utf-8")
        cls.run220 = RUN220.read_text(encoding="utf-8")

    def test_run218_remains_navigation_ui_baseline_and_run220_owns_destination(self):
        self.assertIn("paid member navigation/UI baseline:** Run218", self.readme)
        self.assertIn("Paid Member Navigation/UI Baseline: **Run218", self.spec)
        self.assertIn("current paid-member navigation/UI contract", self.run218)
        self.assertIn("database destination superseded by Run220", self.run218)
        self.assertIn("paid member DB destination baseline:** Run220", self.readme)
        self.assertIn("Paid Member Database Destination Baseline: **Run220", self.spec)

    def test_exact_canonical_home_is_locked_across_current_docs(self):
        for text in (self.readme, self.spec, self.run218, self.run220):
            with self.subTest(source=text[:40]):
                self.assertIn(CANONICAL_HOME_ID, text)
                self.assertIn("AI Decision Intelligence｜会員ホーム", text)

    def test_old_run217_home_cannot_be_mistaken_for_current_home(self):
        self.assertIn(SUPERSEDED_HOME_ID, self.run217)
        self.assertIn(SUPERSEDED_HOME_ID, self.run218)
        self.assertIn("【旧・統合済み】", self.run217)
        self.assertIn("must never be used", self.run218)

    def test_pc_first_mobile_secondary_contract_is_explicit(self):
        for marker in (
            "PC is the primary member experience",
            "Mobile/simple views are secondary fallback surfaces only",
            "スマホ用｜全件リスト",
        ):
            self.assertIn(marker, self.run218)
        self.assertIn("PC-first", self.readme)
        self.assertIn("PC-first", self.spec)

    def test_top3_is_live_not_hard_coded_cards(self):
        self.assertIn("注目順位 <= 3", self.run218)
        self.assertIn("must not depend on manually written fixed cards", self.run218)
        self.assertIn("live Top3", self.readme)
        self.assertIn("live Top3", self.spec)

    def test_empty_important_change_surface_is_reconciled_without_mutating_source_semantics(self):
        self.assertIn("ABS(評価の変化) >= 20", self.run218)
        self.assertIn("presentation-only fallback", self.run218)
        self.assertIn("does not modify the monthly checkbox", self.run218)
        self.assertIn("blank table", self.run218)
        self.assertIn("重要変化", self.spec)

    def test_customer_hierarchy_and_current_database_are_locked_to_run220(self):
        for value in (CURRENT_DB_ID, CURRENT_DS_ID):
            with self.subTest(value=value):
                self.assertIn(value, self.run218)
                self.assertIn(value, self.run220)
                self.assertIn(value, self.readme)
                self.assertIn(value, self.spec)
        self.assertIn("AI Decision Intelligence｜会員ホーム → AI・技術一覧｜判断DB", self.run218)
        self.assertIn("mlflow/mlflow", self.run218)

    def test_pre_run220_database_is_historical_not_current(self):
        for value in (PRE_RUN220_DB_ID, PRE_RUN220_DS_ID):
            with self.subTest(value=value):
                self.assertIn(value, self.run218)
                self.assertIn(value, self.run220)
                self.assertIn(value, self.readme)
                self.assertIn(value, self.spec)
        self.assertIn("旧版・使用禁止", self.run220)

    def test_legacy_database_remains_forbidden(self):
        self.assertIn(LEGACY_DS_ID, self.run218)
        self.assertIn(LEGACY_DS_ID, self.run220)
        self.assertIn("旧版・使用禁止", self.run220)
        self.assertIn("旧版・使用禁止", self.readme)
        self.assertIn("旧版・使用禁止", self.spec)

    def test_run218_and_run220_have_no_model_or_daily_activation_path(self):
        self.assertIn("Gemini/model requests used for this run: **0**", self.run218)
        self.assertIn("Gemini/model requests used for this run: **0**", self.run220)
        self.assertIn("does not:\n- call Gemini or any model API", self.run218)
        self.assertIn("Daily remains PAUSED", self.run218)
        for forbidden in ("GEMINI_API_KEY", "google.generativeai", "generate_content("):
            self.assertNotIn(forbidden, self.run218)
            self.assertNotIn(forbidden, self.run220)


if __name__ == "__main__":
    unittest.main()
