from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from v2_semantic_screening import validate_gold_dataset


ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "benchmarks" / "v2_semantic_gold_v1.json"
CLI = ROOT / "benchmarks" / "v2_semantic_gold_benchmark"


def test_offline_cli_scores_exact_gold_predictions_without_provider_access(tmp_path):
    payload = json.loads(GOLD.read_text(encoding="utf-8"))
    rows = validate_gold_dataset(payload)
    predictions = {row["case_id"]: row["gold"] for row in rows}
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps({"predictions": predictions}), encoding="utf-8")
    output_path = tmp_path / "report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--gold",
            str(GOLD),
            "--predictions",
            str(predictions_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={},
    )

    assert completed.returncode == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["sample_count"] == len(rows)
    assert report["exact_match_accuracy"] == 1.0
    assert report["macro"]["precision"] == 1.0
    assert report["macro"]["recall"] == 1.0
    assert report["macro"]["f1"] == 1.0
    assert "GEMINI" not in output_path.read_text(encoding="utf-8")


def test_offline_cli_fails_closed_on_prediction_contract_error(tmp_path):
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps({"predictions": {}}), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(CLI), "--gold", str(GOLD), "--predictions", str(predictions_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={},
    )

    assert completed.returncode == 2
    assert "prediction_case_ids_invalid" in completed.stderr


def test_offline_cli_rejects_duplicate_json_prediction_case_keys(tmp_path):
    payload = json.loads(GOLD.read_text(encoding="utf-8"))
    rows = validate_gold_dataset(payload)
    predictions = {row["case_id"]: row["gold"] for row in rows}
    first_id = rows[0]["case_id"]
    duplicate = {**predictions[first_id], "ai_relevant": not predictions[first_id]["ai_relevant"]}
    serialized = json.dumps(predictions, ensure_ascii=False)
    serialized = serialized[:-1] + ", " + json.dumps(first_id) + ": " + json.dumps(duplicate) + "}"
    predictions_path = tmp_path / "duplicate_predictions.json"
    predictions_path.write_text('{"predictions": ' + serialized + "}", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(CLI), "--gold", str(GOLD), "--predictions", str(predictions_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={},
    )

    assert completed.returncode == 2
    assert "benchmark_json_duplicate_key" in completed.stderr
