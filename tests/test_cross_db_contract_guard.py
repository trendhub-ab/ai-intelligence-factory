import unittest

import cross_db_contract_guard as guard


class EnumContractTests(unittest.TestCase):
    @staticmethod
    def _select(*names):
        return {
            "type": "select",
            "select": {"options": [{"name": name} for name in names]},
        }

    @staticmethod
    def _multi(*names):
        return {
            "type": "multi_select",
            "multi_select": {"options": [{"name": name} for name in names]},
        }

    def test_history_previous_status_requires_avoid(self):
        properties = {
            "前回採用判断": self._select("ADOPT", "TEST", "WATCH"),
        }
        with self.assertRaisesRegex(ValueError, "AVOID"):
            guard.validate_enum_contracts(
                properties,
                {"前回採用判断": {"ADOPT", "TEST", "WATCH", "AVOID"}},
                "Decision History DB",
            )

    def test_confidence_requires_low(self):
        properties = {
            "根拠信頼度": self._select("HIGH", "MEDIUM"),
        }
        with self.assertRaisesRegex(ValueError, "LOW"):
            guard.validate_enum_contracts(
                properties,
                {"根拠信頼度": {"HIGH", "MEDIUM", "LOW"}},
                "Decision History DB",
            )

    def test_subscriber_source_requires_unknown(self):
        properties = {
            "情報源（内部）": self._multi("GitHub", "HackerNews", "ArXiv", "ProductHunt"),
        }
        with self.assertRaisesRegex(ValueError, "Unknown"):
            guard.validate_enum_contracts(
                properties,
                {"情報源（内部）": guard.SOURCE_OPTIONS},
                "Subscriber Technology DB",
            )

    def test_complete_enum_contract_passes(self):
        properties = {
            "判断": self._select("ADOPT", "TEST", "WATCH", "AVOID"),
        }
        self.assertEqual(
            {},
            guard.validate_enum_contracts(
                properties,
                {"判断": {"ADOPT", "TEST", "WATCH", "AVOID"}},
                "example",
            ),
        )


class MemberContractTests(unittest.TestCase):
    def _state(self, **overrides):
        state = {
            "sync_id": "github:example/tool",
            "name": "example/tool",
            "plain_summary": "何をする技術かを短く説明する。",
            "status": "TEST",
            "score": 72,
            "judgment_reason": "本番利用前に再現確認が必要だから。",
            "topic": "新しいリリースで実務条件が変わった。",
            "next_action": "小さな検証環境で試す。",
            "evidence": "https://example.com/source",
            "confidence": "中",
            "readiness": "中",
            "category": "開発ツール",
            "classification": "実務判断",
        }
        state.update(overrides)
        return state

    def test_member_summary_may_not_be_blank(self):
        with self.assertRaisesRegex(ValueError, "plain_summary"):
            guard.validate_member_states([self._state(plain_summary="")])

    def test_member_topic_and_action_may_not_be_blank(self):
        with self.assertRaisesRegex(ValueError, "next_action"):
            guard.validate_member_states([self._state(topic="", next_action="")])

    def test_duplicate_sync_id_fails(self):
        with self.assertRaisesRegex(ValueError, "duplicates"):
            guard.validate_member_states([self._state(), self._state(name="second")])

    def test_deep_tech_optional_risk_fields_do_not_fail(self):
        state = self._state(classification="Deep Tech")
        state.update({"main_risk": "", "best_for": "", "avoid_for": ""})
        result = guard.validate_member_states([state])
        self.assertEqual(0, result["missing_core_fields"])


if __name__ == "__main__":
    unittest.main()
