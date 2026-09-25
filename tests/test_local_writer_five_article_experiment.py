import ast
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXP2 = ROOT / "experiments" / "local_writer_five_article_20260926"


def _probe(writer_relpath: str, expected_pass_count: int) -> subprocess.CompletedProcess[str]:
    code = f"""
import importlib.util
import json
import re
import socket
from pathlib import Path

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network forbidden in second Local Writer experiment")
)

root = Path.cwd()
exp2 = root / "experiments" / "local_writer_five_article_20260926"
writer_path = root / {writer_relpath!r}

spec = importlib.util.spec_from_file_location("local_writer_probe", writer_path)
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
        evidence_metadata={{}},
        source_info=None,
        freshness={{}},
    )
    editorial = pipeline.validate_editorial_gate(parsed, snapshot["name"])
    publication = pipeline.validate_publication_readiness_gate(
        parsed, source_context=context, source_info={{"sufficient": True}}
    )
    human = pipeline.validate_human_appeal_gate(parsed, peers)

    article = parsed["note_draft"]
    all_pass = bool(
        fact[0]
        and editorial[0]
        and publication[0] == "PASS"
        and human[0] == "ACCEPTABLE"
    )
    results.append({{
        "case_id": snapshot["case_id"],
        "source": snapshot["source"],
        "prior_article_status": snapshot["prior_article_status"],
        "visible_chars": len(re.sub(r"\\s+", "", article)),
        "heading_count": len(re.findall(r"^#{{2,3}}\\s+.+$", article, re.MULTILINE)),
        "fact": fact,
        "editorial": editorial,
        "publication": publication,
        "human": human,
        "all_pass": all_pass,
    }})
    peers.append({{
        "name": snapshot["name"],
        "sequence": pipeline._style_sequence(article),
        "opening_shingles": tuple(
            pipeline._sentence_shingles(pipeline._article_opening_excerpt(article, 520), 5)
        ),
        "heading_count": len(re.findall(r"^#{{2,3}}\\s+.+$", article, re.MULTILINE)),
        "rhetorical_phrases": tuple(sorted(pipeline._rhetorical_template_phrases(article))),
    }})

summary = {{
    "count": len(results),
    "pass_count": sum(1 for row in results if row["all_pass"]),
    "pass_rate": sum(1 for row in results if row["all_pass"]) / len(results),
    "results": results,
}}
print("LOCAL_WRITER_BATCH_RESULT=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))
assert summary["pass_count"] == {expected_pass_count}, (
    "LOCAL_WRITER_BATCH_RESULT=" + json.dumps(summary, ensure_ascii=False, sort_keys=True)
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
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )


def test_v1_baseline_is_reproduced_and_safety_gates_still_pass():
    result = _probe(
        "experiments/local_writer_one_article_20260926/local_writer.py",
        expected_pass_count=0,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LOCAL_WRITER_BATCH_RESULT=" in result.stdout
    payload = json.loads(result.stdout.split("LOCAL_WRITER_BATCH_RESULT=", 1)[1].splitlines()[0])
    assert len(payload["results"]) == 5
    assert all(row["fact"][0] for row in payload["results"])
    assert all(row["editorial"][0] for row in payload["results"])
    assert all(row["publication"][0] == "PASS" for row in payload["results"])


def test_v2_targets_five_of_five_through_production_reader_value_stack():
    result = _probe(
        "experiments/local_writer_five_article_20260926/local_writer_v2.py",
        expected_pass_count=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_v2_is_provider_free_and_existing_prose_cannot_enter():
    path = EXP2 / "local_writer_v2.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    assert roots <= {"__future__", "hashlib", "re", "typing"}

    source = path.read_text(encoding="utf-8")
    for forbidden in ("requests.", "httpx.", "socket.", "genai.", "openai.", "NOTION_API", "note.com"):
        assert forbidden not in source
    for body_key in (
        '"article"', '"article_body"', '"clean_manuscript"',
        '"existing_article"', '"note_draft"', '"previous_article"',
    ):
        assert body_key in source
