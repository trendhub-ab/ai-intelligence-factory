import unittest
from unittest import mock

import member_presentation_body_sync as body
import member_ux_body_fast as fast
import member_ux_guard as guard


class EfficientBodyMigrationTests(unittest.TestCase):
    def _state(self):
        return {
            "sync_id": "github:example/tool",
            "name": "example/tool",
            "status": "TEST",
            "score": 78,
            "readiness": "中",
            "confidence": "高",
            "next_action": "小さく試して確認する。",
            "plain_summary": "AI業務を支援するツールです。",
            "topic": "最近の更新を確認する。",
            "judgment_reason": "実務検証の価値がある。",
            "main_risk": "運用条件の確認が必要。",
            "best_for": "小規模検証。",
            "avoid_for": "即時全面導入。",
            "change_reason": "",
            "evidence": "https://example.com",
            "primary_url": "https://example.com",
            "related_article": "",
        }

    def test_label_only_patch_does_not_touch_children(self):
        state = self._state()
        legacy = {"id": "legacy", "type": "callout"}
        response = mock.Mock(status_code=200, text="")
        with mock.patch.object(body, "_request", return_value=response) as request, \
             mock.patch.object(body, "_delete_block") as delete, \
             mock.patch.object(body, "_create_auto_callout") as create:
            body._auto_label = lambda _state: guard.VISIBLE_CALLOUT_LABEL
            fast._rename_generated_callout(legacy, state)
        request.assert_called_once()
        delete.assert_not_called()
        create.assert_not_called()
        payload = request.call_args.kwargs["json_payload"]
        label = payload["callout"]["rich_text"][0]["text"]["content"]
        self.assertEqual(guard.VISIBLE_CALLOUT_LABEL, label)

    def test_generated_only_rebuild_deletes_parents_not_children(self):
        state = self._state()
        generated = [
            {"id": "a", "type": "callout"},
            {"id": "b", "type": "callout"},
        ]
        with mock.patch.object(body, "_delete_block") as delete, \
             mock.patch.object(body, "_create_auto_callout") as create:
            duplicates = fast._rebuild_generated_only_page("page", generated, state)
        self.assertEqual([mock.call("a"), mock.call("b")], delete.call_args_list)
        create.assert_called_once_with("page", state)
        self.assertEqual(1, duplicates)


    def test_generated_only_rebuild_keeps_old_body_when_new_creation_fails(self):
        state = self._state()
        generated = [{"id": "old", "type": "callout"}]
        with mock.patch.object(
            body, "_create_auto_callout", side_effect=RuntimeError("Notion timeout")
        ) as create, mock.patch.object(body, "_delete_block") as delete:
            with self.assertRaisesRegex(RuntimeError, "Notion timeout"):
                fast._rebuild_generated_only_page("page", generated, state)

        create.assert_called_once()
        delete.assert_not_called()

    def test_generated_only_rebuild_verifies_new_body_before_deleting_old(self):
        state = self._state()
        generated = [
            {"id": "old-a", "type": "callout"},
            {"id": "old-b", "type": "callout"},
        ]
        events = []

        def create(page_id, current):
            events.append("create")
            return "new-callout"

        def children(block_id):
            self.assertEqual("new-callout", block_id)
            events.append("verify")
            return body._build_children(state)

        def delete(block_id):
            events.append(f"delete:{block_id}")

        with mock.patch.object(body, "_create_auto_callout", side_effect=create), \
             mock.patch.object(body, "_children", side_effect=children), \
             mock.patch.object(body, "_delete_block", side_effect=delete):
            duplicates = fast._rebuild_generated_only_page("page", generated, state)

        self.assertEqual(
            ["create", "verify", "delete:old-a", "delete:old-b"],
            events,
        )
        self.assertEqual(1, duplicates)

    def test_empty_same_label_orphan_requires_explicit_recovery(self):
        state = self._state()
        orphan = {
            "id": "orphan",
            "type": "callout",
            "callout": {"rich_text": body._rich_text(guard.VISIBLE_CALLOUT_LABEL)},
        }
        cache = {"orphan": []}
        with mock.patch.object(body, "_replace_auto_callout") as replace:
            self.assertIsNone(
                fast._recover_empty_visible_orphan(
                    [orphan], [], state, cache, enabled=False
                )
            )
            replace.assert_not_called()

            recovered = fast._recover_empty_visible_orphan(
                [orphan], [], state, cache, enabled=True
            )

        self.assertEqual("orphan", recovered["id"])
        replace.assert_called_once_with(orphan, state)

    def test_empty_orphan_recovery_fails_closed_on_multiple_candidates(self):
        state = self._state()
        roots = [
            {
                "id": name,
                "type": "callout",
                "callout": {"rich_text": body._rich_text(guard.VISIBLE_CALLOUT_LABEL)},
            }
            for name in ("orphan-a", "orphan-b")
        ]
        cache = {"orphan-a": [], "orphan-b": []}
        with mock.patch.object(body, "_replace_auto_callout") as replace:
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                fast._recover_empty_visible_orphan(
                    roots, [], state, cache, enabled=True
                )
        replace.assert_not_called()


    def test_partial_generated_body_is_not_considered_unchanged(self):
        state = self._state()
        full = body._build_children(state)
        self.assertTrue(body._body_matches(full, state))
        self.assertFalse(body._body_matches(full[:-1], state))


if __name__ == "__main__":
    unittest.main()
