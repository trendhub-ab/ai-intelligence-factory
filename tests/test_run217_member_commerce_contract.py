from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
RUN217 = ROOT / "docs" / "reference" / "RUN217_ZERO_API_MONETIZATION_READINESS.md"
RUN218 = ROOT / "docs" / "reference" / "RUN218_MEMBER_UX_RECONCILIATION.md"

CANONICAL_MEMBER_HOME_ID = "3c5479ff-dca9-8103-bff0-f2d5f408d35f"
SUPERSEDED_RUN217_HOME_ID = "3d0479ff-dca9-819e-9da0-c951225de6b3"
CURRENT_DB_ID = "d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1"
CURRENT_DATA_SOURCE_ID = "d1461b6f-0940-4bf9-803a-6686a37c4ba2"
LEGACY_DB_ID = "9430d2a5-b9ce-423a-b76e-d9214f3f6204"
LEGACY_DATA_SOURCE_ID = "ec2ac2b3-89b6-4242-89b9-e94060826fca"


class Run217MemberCommerceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = README.read_text(encoding="utf-8")
        cls.spec = SPEC.read_text(encoding="utf-8")
        cls.run217 = RUN217.read_text(encoding="utf-8")
        cls.run218 = RUN218.read_text(encoding="utf-8")

    def test_functional_and_member_copy_baselines_are_not_relabelled(self):
        self.assertIn("Current functional baseline:** Run209", self.readme)
        self.assertIn("Current paid member UX baseline:** Run215", self.readme)
        self.assertIn("現行Functional Baseline: **Run209", self.spec)
        self.assertIn("Paid Member UX Baseline: **Run215", self.spec)

    def test_run217_remains_commerce_readiness_history_but_navigation_is_superseded(self):
        self.assertIn("paid member commerce/onboarding baseline:** Run217", self.readme)
        self.assertIn("Paid Member Commerce/Onboarding Baseline: **Run217", self.spec)
        self.assertIn("superseded by Run218", self.run217)
        self.assertIn("Run218", self.run217)

    def test_current_canonical_home_is_the_preexisting_decision_intelligence_home(self):
        for text in (self.readme, self.spec, self.run217, self.run218):
            with self.subTest(source=text[:30]):
                self.assertIn(CANONICAL_MEMBER_HOME_ID, text)
                self.assertIn("AI Decision Intelligence｜会員ホーム", text)

    def test_run217_created_home_is_explicitly_superseded_not_current(self):
        self.assertIn(SUPERSEDED_RUN217_HOME_ID, self.run217)
        self.assertIn("【旧・統合済み】AI Intelligence｜会員ホーム", self.run217)
        self.assertIn(SUPERSEDED_RUN217_HOME_ID, self.run218)
        self.assertIn("superseded", self.run218)

    def test_current_db_ids_match_current_navigation_contract(self):
        for value in (CURRENT_DB_ID, CURRENT_DATA_SOURCE_ID):
            with self.subTest(value=value):
                self.assertIn(value, self.readme)
                self.assertIn(value, self.spec)
                self.assertIn(value, self.run217)
                self.assertIn(value, self.run218)

    def test_legacy_database_is_explicitly_forbidden_for_onboarding(self):
        self.assertIn(LEGACY_DB_ID, self.run217)
        self.assertIn(LEGACY_DATA_SOURCE_ID, self.readme)
        self.assertIn(LEGACY_DATA_SOURCE_ID, self.spec)
        self.assertIn("旧版・使用禁止", self.readme)
        self.assertIn("旧版・使用禁止", self.spec)
        self.assertIn("Do not invite members to it", self.run217)

    def test_digest_delivery_cannot_be_silently_dropped(self):
        self.assertIn("会員限定Digest｜2026年9月 初回版", self.run217)
        self.assertIn("Do not silently advertise Digest while delivering none", self.run217)
        self.assertIn("Digest自動生成が停止中でも", self.spec)

    def test_run217_and_run218_do_not_resume_daily_or_claim_model_generation(self):
        self.assertIn("**Daily:** PAUSED", self.readme)
        self.assertIn("**Daily workflowはPAUSED。**", self.spec)
        self.assertIn("Gemini/model requests used for this run: **0**", self.run217)
        self.assertIn("Gemini/model requests used for this run: **0**", self.run218)
        self.assertIn("does not:\n- call Gemini or any model API", self.run218)


if __name__ == "__main__":
    unittest.main()
