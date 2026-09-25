import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "local_writer_one_article_20260926"
WRITER_PATH = EXP / "local_writer.py"
SNAPSHOT_PATH = EXP / "snapshot.json"
RESULT_PATH = EXP / "result_article.md"


def _load_writer():
    spec = importlib.util.spec_from_file_location("local_writer_one_article_experiment", WRITER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot():
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_local_writer_is_stdlib_only_and_has_no_io_surface():
    tree = ast.parse(WRITER_PATH.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    assert roots <= {"__future__", "re", "typing"}

    source = WRITER_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "requests.",
        "httpx.",
        "socket.",
        "urllib.",
        "genai.",
        "openai.",
        "NOTION_API",
        "note.com",
        "subprocess.",
    ):
        assert forbidden not in source


def test_existing_article_body_is_not_an_allowed_input():
    writer = _load_writer()
    snapshot = _snapshot()
    writer.validate_snapshot(snapshot)

    for key in ("note_draft", "existing_article", "article_body"):
        contaminated = dict(snapshot)
        contaminated[key] = "pre-existing prose must never be reused"
        with pytest.raises(writer.SnapshotError):
            writer.validate_snapshot(contaminated)


def test_checked_in_article_is_exact_deterministic_output():
    writer = _load_writer()
    snapshot = _snapshot()
    expected = RESULT_PATH.read_text(encoding="utf-8")
    assert writer.render_article(snapshot) == expected
    assert writer.render_article(snapshot) == writer.render_article(snapshot)


def test_article_keeps_structured_evidence_decision_and_action_without_new_numbers():
    writer = _load_writer()
    snapshot = _snapshot()
    article = writer.render_article(snapshot)
    context = writer.source_context(snapshot)

    for key in (
        "source_summary",
        "what",
        "why_important",
        "primary_risk",
        "best_for",
        "avoid_for",
        "decision_reason",
        "action",
    ):
        assert snapshot[key] in article

    assert "TRY" not in writer.render_body(snapshot)
    assert "限定的に試す" in article
    for url in snapshot["evidence_urls"]:
        assert url in article

    number_pattern = r"\d[\d,]*(?:\.\d+)?"
    article_numbers = set(re.findall(number_pattern, article))
    context_numbers = set(re.findall(number_pattern, context))
    assert article_numbers <= context_numbers


def test_article_has_note_length_and_readable_sectioning():
    writer = _load_writer()
    body = writer.render_body(_snapshot())
    visible_chars = len(re.sub(r"\s+", "", body))
    headings = re.findall(r"^##\s+.+$", body, re.MULTILINE)
    assert visible_chars >= 1200
    assert len(headings) >= 3
    assert "### Sources / Evidence" in body


def test_existing_core_gates_accept_local_writer_output_without_network_or_provider():
    code = r"""
import importlib.util
import json
import socket
from pathlib import Path

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network access forbidden in Local Writer gate validation")
)

root = Path.cwd()
exp = root / "experiments" / "local_writer_one_article_20260926"
spec = importlib.util.spec_from_file_location("local_writer_gate_check", exp / "local_writer.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
snapshot = json.loads((exp / "snapshot.json").read_text(encoding="utf-8"))

import pipeline

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
    parsed,
    source_context=context,
    source_info={"sufficient": True},
)
human = pipeline.validate_human_appeal_gate(parsed, [])

assert fact[0], fact
assert editorial[0], editorial
assert publication[0] == "PASS", publication
assert human[0] == "ACCEPTABLE", human
print(json.dumps({
    "fact": fact,
    "editorial": editorial,
    "publication": publication,
    "human": human,
}, ensure_ascii=False))
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
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"publication": ["PASS", []]' in result.stdout
    assert '"human": ["ACCEPTABLE", []]' in result.stdout
