from __future__ import annotations

import json
from pathlib import Path

from v2_semantic_screening import SEMANTIC_FIELDS, validate_gold_dataset


GOLD_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "v2_semantic_gold_v1.json"


def test_committed_gold_dataset_is_balanced_regression_corpus():
    payload = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    rows = validate_gold_dataset(payload)

    assert payload["benchmark_version"] == "v1"
    assert len(rows) >= 16
    assert len({row["case_id"] for row in rows}) == len(rows)

    for field in SEMANTIC_FIELDS:
        values = {row["gold"][field] for row in rows}
        assert values == {False, True}

    assert any(not any(row["gold"].values()) for row in rows)
    assert any(0 < sum(row["gold"].values()) < len(SEMANTIC_FIELDS) for row in rows)
