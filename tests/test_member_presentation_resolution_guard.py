import unittest
from unittest.mock import Mock, patch

import provision_member_presentation_db as provision
import cross_db_contract_guard as contracts


class MemberPresentationResolutionGuardTests(unittest.TestCase):
    def test_new_member_db_schema_passes_current_source_contract(self):
        properties = provision._properties_schema()
        # Notion adds `type` to the schema returned after provisioning.
        returned_properties = {
            name: {"type": next(iter(prop)), **prop}
            for name, prop in properties.items()
        }
        contracts.validate_enum_contracts(
            returned_properties, contracts.MEMBER_ENUM_CONTRACTS, "new Member DB"
        )
        source_options = properties["情報源"]["multi_select"]["options"]
        self.assertEqual(
            [(option["name"], option["color"]) for option in source_options[:5]],
            [("GitHub", "default"), ("HackerNews", "orange"), ("ArXiv", "red"),
             ("ProductHunt", "blue"), ("Unknown", "gray")],
        )

    @staticmethod
    def _search_response(items):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"results": items}
        return response

    @staticmethod
    def _item(ds_id, db_id, title=None):
        title = title or provision.TITLE
        return {
            "object": "data_source",
            "id": ds_id,
            "parent": {"database_id": db_id},
            "title": [{"plain_text": title}],
        }

    @patch.object(provision.requests, "post")
    def test_exact_single_match_is_selected(self, post):
        post.return_value = self._search_response([
            self._item("ds-current", "db-current"),
            self._item("ds-old", "db-old", title="【旧・使用停止】AI・技術一覧｜判断DB"),
        ])
        self.assertEqual(("db-current", "ds-current"), provision._search_existing())

    @patch.object(provision.requests, "post")
    def test_duplicate_exact_titles_fail_closed(self, post):
        post.return_value = self._search_response([
            self._item("ds-a", "db-a"),
            self._item("ds-b", "db-b"),
        ])
        with self.assertRaisesRegex(RuntimeError, "Ambiguous member presentation DB title"):
            provision._search_existing()

    @patch.object(provision.requests, "post")
    def test_no_exact_match_returns_none(self, post):
        post.return_value = self._search_response([
            self._item("ds-old", "db-old", title="【旧・使用停止】AI・技術一覧｜判断DB"),
        ])
        self.assertIsNone(provision._search_existing())


if __name__ == "__main__":
    unittest.main()
