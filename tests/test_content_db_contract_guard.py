import unittest

import content_db_contract_guard as guard


class ContentDbContractGuardTests(unittest.TestCase):
    @staticmethod
    def _select(*names):
        return {
            "type": "select",
            "select": {"options": [{"name": name} for name in names]},
        }

    def _complete(self):
        return {
            guard.p.PROP_SOURCE: self._select(*sorted(guard.SOURCE_VALUES)),
            guard.p.PROP_STATUS: self._select(guard.p.STATUS_STOCKED, guard.p.STATUS_DEEP_DIVE),
            guard.p.PROP_CONTENT_STATUS: self._select(*sorted(guard.CONTENT_STATUS_VALUES)),
            guard.p.PROP_ARTICLE_STATUS: self._select(*sorted(guard.ARTICLE_STATUS_VALUES)),
            guard.p.PROP_SUBSCRIPTION_VISIBILITY: self._select(*sorted(guard.VISIBILITY_VALUES)),
            guard.p.PROP_DECISION: self._select(*sorted(guard.p.ALLOWED_DECISIONS)),
            guard.p.PROP_GROUNDING_STATUS: self._select(*sorted(guard.GROUNDING_VALUES)),
        }

    def test_missing_wait_fails(self):
        properties = self._complete()
        properties[guard.p.PROP_DECISION] = self._select("NOW", "TRY", "WATCH", "AVOID")
        with self.assertRaisesRegex(ValueError, "WAIT"):
            guard.validate_enum_contracts(properties)

    def test_missing_url_search_fails(self):
        properties = self._complete()
        properties[guard.p.PROP_GROUNDING_STATUS] = self._select(
            guard.p.GROUNDING_METADATA_ONLY,
            guard.p.GROUNDING_SOURCE_NATIVE,
            guard.p.GROUNDING_URL_CONTEXT,
            guard.p.GROUNDING_FAILED,
        )
        with self.assertRaisesRegex(ValueError, "URL \\+ Search"):
            guard.validate_enum_contracts(properties)

    def test_complete_contract_passes(self):
        guard.validate_enum_contracts(self._complete())


if __name__ == "__main__":
    unittest.main()
