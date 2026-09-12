import unittest

from comment_write_contract import (
    CommentWriteRequest,
    WriteDecision,
    WriteMode,
    apply_authorized_blank_fills,
    build_production_property_mutation,
    decide_comment_write,
)


class CommentWriteContractTests(unittest.TestCase):
    def test_existing_non_empty_value_is_preserved_exactly(self):
        original = "  既存の具体的な判断理由。改変禁止。  "
        result = decide_comment_write(
            CommentWriteRequest(
                property_name="判断理由",
                existing_value=original,
                candidate_value="新しい生成文",
                owner_allowed=True,
                provider="groq",
                mode=WriteMode.PRODUCTION,
            )
        )
        self.assertEqual(WriteDecision.PRESERVE, result.decision)
        self.assertEqual(original, result.value)
        self.assertFalse(result.production_write_allowed)

    def test_owned_blank_property_can_be_filled(self):
        result = decide_comment_write(
            CommentWriteRequest(
                property_name="主リスク",
                existing_value="   ",
                candidate_value="導入前に互換性を確認する必要がある。",
                owner_allowed=True,
                provider="current-provider",
                locked_provider="current-provider",
            )
        )
        self.assertEqual(WriteDecision.BLANK_FILL, result.decision)
        self.assertTrue(result.production_write_allowed)

    def test_blank_fill_without_ownership_is_blocked(self):
        result = decide_comment_write(
            CommentWriteRequest(
                property_name="向いている用途",
                existing_value="",
                candidate_value="小規模な検証。",
                owner_allowed=False,
            )
        )
        self.assertEqual(WriteDecision.BLOCKED, result.decision)

    def test_shadow_output_never_enters_production_mutation(self):
        result = decide_comment_write(
            CommentWriteRequest(
                property_name="判断理由",
                existing_value="",
                candidate_value="Shadow candidate",
                owner_allowed=True,
                provider="groq",
                mode=WriteMode.SHADOW,
            )
        )
        payload = build_production_property_mutation({"判断理由": result})
        self.assertEqual(WriteDecision.SHADOW, result.decision)
        self.assertEqual({}, payload)

    def test_product_review_provider_mismatch_is_blocked(self):
        result = decide_comment_write(
            CommentWriteRequest(
                property_name="Product Review Comment",
                existing_value="",
                candidate_value="candidate",
                owner_allowed=True,
                provider="groq",
                locked_provider="gemini",
            )
        )
        self.assertEqual(WriteDecision.BLOCKED, result.decision)
        self.assertEqual("provider_lock_mismatch", result.reason)

    def test_provider_promotion_requires_quality_and_explicit_approval(self):
        for quality, approved in ((False, False), (True, False), (False, True)):
            with self.subTest(quality=quality, approved=approved):
                result = decide_comment_write(
                    CommentWriteRequest(
                        property_name="判断理由",
                        existing_value="",
                        candidate_value="candidate",
                        owner_allowed=True,
                        provider="groq",
                        provider_promotion_requested=True,
                        quality_gate_passed=quality,
                        promotion_approved=approved,
                    )
                )
                self.assertEqual(WriteDecision.BLOCKED, result.decision)

        promoted = decide_comment_write(
            CommentWriteRequest(
                property_name="判断理由",
                existing_value="",
                candidate_value="candidate",
                owner_allowed=True,
                provider="groq",
                provider_promotion_requested=True,
                quality_gate_passed=True,
                promotion_approved=True,
            )
        )
        self.assertEqual(WriteDecision.BLANK_FILL, promoted.decision)

    def test_promotion_still_cannot_rewrite_historical_value(self):
        original = "短いが具体的な既存コメント。"
        result = decide_comment_write(
            CommentWriteRequest(
                property_name="主リスク",
                existing_value=original,
                candidate_value="long replacement",
                owner_allowed=True,
                provider="groq",
                provider_promotion_requested=True,
                quality_gate_passed=True,
                promotion_approved=True,
            )
        )
        self.assertEqual(WriteDecision.PRESERVE, result.decision)
        self.assertEqual(original, result.value)

    def test_mutation_contains_only_blank_fill(self):
        fill = decide_comment_write(
            CommentWriteRequest("主リスク", "", "risk", True)
        )
        preserve = decide_comment_write(
            CommentWriteRequest("判断理由", "keep", "replace", True)
        )
        shadow = decide_comment_write(
            CommentWriteRequest(
                "向いている用途", "", "candidate", True, mode=WriteMode.SHADOW
            )
        )
        blocked = decide_comment_write(
            CommentWriteRequest("向いていない用途", "", "candidate", False)
        )
        payload = build_production_property_mutation(
            {
                "主リスク": fill,
                "判断理由": preserve,
                "向いている用途": shadow,
                "向いていない用途": blocked,
            }
        )
        self.assertEqual({"主リスク": "risk"}, payload)

    def test_blank_fill_migration_is_idempotent(self):
        original = {"主リスク": "", "判断理由": "既存値"}
        first_result = decide_comment_write(
            CommentWriteRequest("主リスク", original["主リスク"], "risk", True)
        )
        after_first = apply_authorized_blank_fills(
            original, {"主リスク": first_result}
        )

        second_result = decide_comment_write(
            CommentWriteRequest(
                "主リスク", after_first["主リスク"], "different candidate", True
            )
        )
        after_second = apply_authorized_blank_fills(
            after_first, {"主リスク": second_result}
        )

        self.assertEqual("risk", after_first["主リスク"])
        self.assertEqual(WriteDecision.PRESERVE, second_result.decision)
        self.assertEqual(after_first, after_second)

    def test_blank_candidate_is_blocked(self):
        result = decide_comment_write(
            CommentWriteRequest("主リスク", "", "  ", True)
        )
        self.assertEqual(WriteDecision.BLOCKED, result.decision)
        self.assertEqual({}, build_production_property_mutation({"主リスク": result}))


if __name__ == "__main__":
    unittest.main()
