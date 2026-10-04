from pathlib import Path
import tempfile

import member_customer_surface_contract as contract


def test_p0b_creation_recovery_is_explicitly_non_member_operational_module():
    assert "note_delivery_creation_recovery.py" in contract.NON_MEMBER_MODULES


def test_member_surface_guard_still_rejects_unknown_python_module():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for spec in contract.SURFACES.values():
            for key in ("owner", "audit"):
                path = root / spec[key]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
        (root / "totally_new_unclassified_surface.py").write_text(
            "def render(): return 'unexpected'\n",
            encoding="utf-8",
        )
        failures = contract.validate_repository(root)
        assert any(
            "unclassified member/customer module: totally_new_unclassified_surface.py" in item
            for item in failures
        )
