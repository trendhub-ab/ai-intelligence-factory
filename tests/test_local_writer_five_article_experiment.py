import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXP1 = ROOT / "experiments" / "local_writer_one_article_20260926"
EXP2 = ROOT / "experiments" / "local_writer_five_article_20260926"


def test_second_experiment_baseline_probe_runs_without_provider_or_network():
    code = r"""
import importlib.util
import json
import socket
from pathlib import Path

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network forbidden in second Local Writer experiment")
)

root = Path.cwd()
exp1 = root / "experiments" / "local_writer_one_article_20260926"
exp2 = root / "experiments" / "local_writer_five_article_20260926"

spec = importlib.util.spec_from_file_location("local_writer_v1_baseline", exp1 / "local_writer.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
batch = json.loads((exp2 / "snapshots.json").read_text(encoding="utf-8"))

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
for snapshot in batch["articles"]:
    parsed = writer.to_pipeline_parsed(snapshot)
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
        parsed, source_context=context, source_info={"sufficient": True}
    )
    human = pipeline.validate_human_appeal_gate(parsed, peers)

    all_pass = bool(
        fact[0]
        and editorial[0]
        and publication[0] == "PASS"
        and human[0] == "ACCEPTABLE"
    )
    article = parsed["note_draft"]
    visible_chars = len("".join(article.split()))
    results.append({
        "case_id": snapshot["case_id"],
        "source": snapshot["source"],
        "prior_article_status": snapshot["prior_article_status"],
        "visible_chars": visible_chars,
        "fact": fact,
        "editorial": editorial,
        "publication": publication,
        "human": human,
        "all_pass": all_pass,
    })
    peers.append({
        "name": snapshot["name"],
        "sequence": pipeline._style_sequence(article),
        "opening_shingles": tuple(pipeline._sentence_shingles(pipeline._article_opening_excerpt(article, 520), 5)),
        "heading_count": len(__import__("re").findall(r"^#{2,3}\s+.+$", article, __import__("re").MULTILINE)),
        "rhetorical_phrases": tuple(sorted(pipeline._rhetorical_template_phrases(article))),
    })

summary = {
    "count": len(results),
    "pass_count": sum(1 for x in results if x["all_pass"]),
    "pass_rate": sum(1 for x in results if x["all_pass"]) / len(results),
    "results": results,
}
print("LOCAL_WRITER_BATCH_BASELINE_JSON=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))
assert len(results) == 5
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
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LOCAL_WRITER_BATCH_BASELINE_JSON=" in result.stdout


def test_second_experiment_v2_reaches_five_of_five_without_provider_or_gate_changes():
    code = r"""
import importlib.util
import json
import re
import socket
from pathlib import Path

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network forbidden in second Local Writer v2 experiment")
)

root = Path.cwd()
exp2 = root / "experiments" / "local_writer_five_article_20260926"

spec = importlib.util.spec_from_file_location("local_writer_v2", exp2 / "local_writer_v2.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
batch = json.loads((exp2 / "snapshots.json").read_text(encoding="utf-8"))

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
for snapshot in batch["articles"]:
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
        parsed, source_context=context, source_info={"sufficient": True}
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
        "source": snapshot["source"],
        "prior_article_status": snapshot["prior_article_status"],
        "layout": writer._layout_id(snapshot),
        "visible_chars": len("".join(article.split())),
        "fact": fact,
        "editorial": editorial,
        "publication": publication,
        "human": human,
        "cross": cross,
        "reader": {
            "accessibility": signals.get("accessibility"),
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
        "opening_shingles": tuple(pipeline._sentence_shingles(pipeline._article_opening_excerpt(article, 520), 5)),
        "heading_count": len(re.findall(r"^#{2,3}\s+.+$", article, re.MULTILINE)),
        "rhetorical_phrases": tuple(sorted(pipeline._rhetorical_template_phrases(article))),
    })

summary = {
    "count": len(results),
    "pass_count": sum(1 for x in results if x["all_pass"]),
    "pass_rate": sum(1 for x in results if x["all_pass"]) / len(results),
    "results": results,
}
assert summary["pass_count"] == 5, "V2_RESULT::" + json.dumps(summary, ensure_ascii=False, sort_keys=True)
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
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
