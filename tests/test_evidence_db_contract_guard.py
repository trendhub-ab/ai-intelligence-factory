import unittest

import evidence_db_contract_guard as guard


class EvidenceDbContractGuardTests(unittest.TestCase):
    @staticmethod
    def _health(*names):
        return {
            "type": "select",
            "select": {"options": [{"name": name} for name in names]},
        }

    def test_missing_health_value_fails(self):
        properties = {
            "ソース状態": self._health(
                "VERIFIED", "COSMETIC_CHANGE", "MOVED", "MATERIAL_CHANGE", "MISSING"
            )
        }
        with self.assertRaisesRegex(ValueError, "FETCH_ERROR"):
            guard.validate_health_options(properties)

    def test_complete_health_contract_passes(self):
        properties = {"ソース状態": self._health(*sorted(guard.el.HEALTH_VALUES))}
        guard.validate_health_options(properties)


if __name__ == "__main__":
    unittest.main()
