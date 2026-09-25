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
DEV = ROOT / "experiments" / "publication_canonicalizer_dev_20260926"
WRITER_PATH = ROOT / "experiments" / "local_writer_five_article_20260926" / "local_writer_v3.py"
FROZEN_WRITER_BLOB = "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return hashlib.sha1(payload).hexdigest()


def test_stage4_devset_does_not_reuse_stage3_holdout():
    dev = json.loads((DEV / "devset.json").read_text(encoding="utf-8"))
    holdout = json.loads(
        (ROOT / "experiments" / "local_writer_holdout_10_20260926" / "selection.json").read_text(encoding="utf-8")
    )
    assert dev["stage3_holdout_reused"] is False
    assert len(dev["articles"]) == 8
    dev_urls = {row["notion_url"] for row in dev["articles"]}
    holdout_urls = {row["notion_url"] for row in holdout["articles"]}
    assert dev_urls.isdisjoint(holdout_urls)
    assert _git_blob_sha(WRITER_PATH) == FROZEN_WRITER_BLOB


def test_stage4_frozen_v3_development_baseline():
    code = r"""
import hashlib
import importlib.util
import json
import re
import socket
from pathlib import Path

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network forbidden in Stage 4 canonicalizer development")
)

root = Path.cwd()
dev = root / "experiments" / "publication_canonicalizer_dev_20260926"
writer_path = root / "experiments" / "local_writer_five_article_20260926" / "local_writer_v3.py"

data = writer_path.read_bytes()
git_blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
assert git_blob == "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"

spec = importlib.util.spec_from_file_location("local_writer_v3_stage4_baseline", writer_path)
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
selection = json.loads((dev / "devset.json").read_text(encoding="utf-8"))

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
        fact[0] and editorial[0] and publication[0] == "PASS" and human[0] == "ACCEPTABLE"
    )
    results.append({
        "case_id": snapshot["case_id"],
        "name": snapshot["name"],
        "source": snapshot["source"],
        "fact": fact,
        "editorial": editorial,
        "publication": publication,
        "human": human,
        "reader": {
            "accessibility": signals.get("accessibility"),
            "decision_accessibility": signals.get("decision_accessibility"),
            "jargon_translation": signals.get("jargon_translation"),
            "non_engineer_core_clarity": signals.get("non_engineer_core_clarity"),
            "information_budget": signals.get("information_budget"),
            "reader_enjoyment": signals.get("reader_enjoyment"),
            "unexplained_jargon": signals.get("unexplained_jargon"),
        },
        "cross": cross,
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
    "results": results,
}
assert len(results) == 8
assert summary["pass_count"] == 8, "STAGE4_DEV_BASELINE::" + json.dumps(
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
