import unittest

import run156_decision_review_import as run156


class TestRun156DecisionDensity(unittest.TestCase):
    def _row(self):
        return {
            "name": "example/repo",
            "decision_context": {
                "plain_summary": "これは特定の業務で使うAI基盤で、入力を処理して結果を業務システムへ返します。単なるカテゴリ名ではなく、どの処理を担うのかと導入時の位置づけを具体的に説明しています。",
                "topic_trigger": "現在も公式一次情報が更新されており、本番導入候補として運用条件と制約を確認する価値があるため今回取り上げます。",
            },
            "review": {
                "adoption_status": "TEST",
                "production_readiness": "HIGH",
                "main_risk": "本番では権限、入力データ、依存サービス、障害時の復旧を設計し、自社環境の負荷と品質で検証しないと期待した効果が出ない可能性があります。",
                "best_for": "複数の工程をAIで処理しながら、実行状態と結果を自社の業務システムへ安全に接続したいチームに向いています。",
                "avoid_for": "単純な一回の生成だけで十分で、状態管理や外部連携を持たない小規模用途では、追加の運用基盤が過剰になる可能性があります。",
                "short_rationale": "公式一次情報で主要機能と運用方法を確認でき、対象業務との適合性も明確です。一方で運用設計が必要なため、実データで品質と負荷を検証したうえで採用する判断が妥当です。",
            },
        }

    def test_rich_decision_context_passes(self):
        self.assertEqual([], run156.validate_decision_density(self._row()))

    def test_category_only_plain_summary_fails(self):
        row = self._row()
        row["decision_context"]["plain_summary"] = "画像・音声・動画AI技術。"
        failures = run156.validate_decision_density(row)
        self.assertTrue(any("plain_summary" in f for f in failures))

    def test_run153_malformed_best_for_fails(self):
        row = self._row()
        row["review"]["best_for"] = "音声認識ことを自社のAI導入・開発・運用で具体的に必要としているチーム。"
        failures = run156.validate_decision_density(row)
        self.assertTrue(any("best_for" in f for f in failures))

    def test_generic_short_rationale_fails(self):
        row = self._row()
        row["review"]["short_rationale"] = "公式一次情報で主用途を確認でき、導入候補として比較する価値がある。"
        failures = run156.validate_decision_density(row)
        self.assertTrue(any("short_rationale" in f for f in failures))

    def test_explicit_archived_project_cannot_be_adopted(self):
        row = self._row()
        row["review"]["adoption_status"] = "ADOPT"
        row["decision_context"]["topic_trigger"] = (
            "公式一次情報でこのリポジトリはArchivedと明示されており、新規の本番基盤として継続保守を期待できないため、現在の採用可否を再評価します。"
        )
        failures = run156.validate_decision_density(row)
        self.assertTrue(any("lifecycle contradiction" in f for f in failures))

    def test_explicit_maintenance_project_cannot_be_high_readiness(self):
        row = self._row()
        row["review"]["adoption_status"] = "AVOID"
        row["review"]["production_readiness"] = "HIGH"
        row["decision_context"]["topic_trigger"] = (
            "公式READMEでmaintenance modeと明示され、新規機能より既存利用者の保守が中心となっているため、現在の採用可否を再評価します。"
        )
        failures = run156.validate_decision_density(row)
        self.assertTrue(any("HIGH production_readiness" in f for f in failures))

    def test_explicit_archived_project_can_be_avoid_low(self):
        row = self._row()
        row["review"]["adoption_status"] = "AVOID"
        row["review"]["production_readiness"] = "LOW"
        row["decision_context"]["topic_trigger"] = (
            "公式一次情報でこのリポジトリはArchivedと明示されており、新規採用ではなく既存資産の移行判断として今回取り上げます。"
        )
        self.assertEqual([], run156.validate_decision_density(row))


if __name__ == "__main__":
    unittest.main()
