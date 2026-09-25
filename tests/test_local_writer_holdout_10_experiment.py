import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "experiments" / "local_writer_holdout_10_20260926"
WRITER_PATH = ROOT / "experiments" / "local_writer_five_article_20260926" / "local_writer_v3.py"
FROZEN_GIT_BLOB_SHA = "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return hashlib.sha1(payload).hexdigest()


def test_stage3_holdout_protocol_is_frozen_before_measurement():
    selection = json.loads((HOLDOUT / "selection.json").read_text(encoding="utf-8"))
    assert selection["article_body_used_for_selection"] is False
    assert selection["writer_frozen_commit"] == "4b139edfd3fdb845723b850e80039b1c28f05e59"
    assert selection["writer_blob_sha"] == FROZEN_GIT_BLOB_SHA
    assert _git_blob_sha(WRITER_PATH) == FROZEN_GIT_BLOB_SHA
    assert len(selection["articles"]) == 10
    assert len({row["notion_url"] for row in selection["articles"]}) == 10
    assert len({row["canonical_entity_id"] for row in selection["articles"]}) == 10
    assert all(row["source"] != "ProductHunt" for row in selection["articles"])
    counts = {}
    for row in selection["articles"]:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    assert counts.get("GitHub") == 2
    assert counts.get("ArXiv") == 2
    assert counts.get("OfficialVendor") == 2
    assert counts.get("HackerNews") == 4


def test_stage3_blind_holdout_measures_frozen_v3_without_provider_or_gate_changes():
    code = r"""
import hashlib
import importlib.util
import json
import re
import socket
from pathlib import Path

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network forbidden in Stage 3 Local Writer holdout")
)

root = Path.cwd()
holdout = root / "experiments" / "local_writer_holdout_10_20260926"
writer_path = root / "experiments" / "local_writer_five_article_20260926" / "local_writer_v3.py"

data = writer_path.read_bytes()
git_blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
assert git_blob == "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"

spec = importlib.util.spec_from_file_location("local_writer_v3_frozen_holdout", writer_path)
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
selection = json.loads((holdout / "selection.json").read_text(encoding="utf-8"))

import pipeline
import production_pipeline
import reader_quality_precision
import run283_numeric_evidence_equivalence
import run284_reader_recovery_precision

production_pipeline.install_runtime_layers(pipeline)
production_pipeline.install_run349_score_narrative_negation_precision(pipeline)
run283_numeric_evidence_equivalence.install(pipeline)
reader_quality_precision.install(pipeline)
run284_reader_recovery_precision.install(pipeline)

results = []
peers = []
for snapshot in selection["articles"]:
    parsed = writer.to_pipeline_parsed(snapshot)
    article = parsed["note_draft"]
    context = writer.source_context(snapshot)

    fact = pipeline.validate_fact_gate(
        parsed,
        snapshot["name"],
        source_context=context,
        source=snapshot["source"],
        evidence_metadata={},
        source_info=None,
        freshness={},
    )
    editorial = pipeline.validate_editorial_gate(parsed, snapshot["name"])
    publication = pipeline.validate_publication_readiness_gate(
        parsed,
        source_context=context,
        source_info={"sufficient": True},
    )
    human = pipeline.validate_human_appeal_gate(parsed, peers)
    signals = pipeline._reader_experience_signals(article)
    cross = pipeline._cross_article_naturalness_signals(article, peers)

    all_pass = bool(
        fact[0]
        and editorial[0]
        and publication[0] == "PASS"
        and human[0] == "ACCEPTABLE"
    )
    results.append({
        "case_id": snapshot["case_id"],
        "name": snapshot["name"],
        "source": snapshot["source"],
        "prior_article_status": snapshot["prior_article_status"],
        "selection_hash": snapshot["selection_hash"],
        "layout": writer._layout_id(snapshot),
        "visible_chars": len("".join(article.split())),
        "fact": fact,
        "editorial": editorial,
        "publication": publication,
        "human": human,
        "cross": cross,
        "reader": {
            "accessibility": signals.get("accessibility"),
            "decision_accessibility": signals.get("decision_accessibility"),
            "opening_non_engineer_access": signals.get("opening_non_engineer_access"),
            "plain_language_bridge": signals.get("plain_language_bridge"),
            "jargon_translation": signals.get("jargon_translation"),
            "non_engineer_core_clarity": signals.get("non_engineer_core_clarity"),
            "information_budget": signals.get("information_budget"),
            "reader_enjoyment": signals.get("reader_enjoyment"),
            "unexplained_jargon": signals.get("unexplained_jargon"),
            "technical_terms_per_1000_chars": signals.get("technical_terms_per_1000_chars"),
            "jargon_dense_paragraph_count": signals.get("jargon_dense_paragraph_count"),
        },
        "all_pass": all_pass,
    })
    peers.append({
        "name": snapshot["name"],
        "sequence": pipeline._style_sequence(article),
        "opening_shingles": tuple(
            pipeline._sentence_shingles(pipeline._article_opening_excerpt(article, 520), 5)
        ),
        "heading_count": len(re.findall(r"^#{2,3}\s+.+$", article, re.MULTILINE)),
        "rhetorical_phrases": tuple(sorted(pipeline._rhetorical_template_phrases(article))),
    })

summary = {
    "count": len(results),
    "pass_count": sum(1 for row in results if row["all_pass"]),
    "pass_rate": sum(1 for row in results if row["all_pass"]) / len(results),
    "by_source": {},
    "results": results,
}
for source in sorted({row["source"] for row in results}):
    source_rows = [row for row in results if row["source"] == source]
    summary["by_source"][source] = {
        "count": len(source_rows),
        "pass_count": sum(1 for row in source_rows if row["all_pass"]),
    }

assert len(results) == 10
assert summary["pass_count"] == 10, "STAGE3_HOLDOUT_RESULT::" + json.dumps(
    summary, ensure_ascii=False, sort_keys=True
)
"""
    env = dict(
        os.environ,
        SYNTHETIC_REGRESSION_MODE="true",
        GEMINI_API_KEY="",
        GH_PAT="",
        NOTION_API_KEY="",
        GEMINI_PERSISTENT_DAILY_COUNTER="false",
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
