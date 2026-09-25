import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CANON_PATH = ROOT / "experiments" / "publication_canonicalizer_dev_20260926" / "publication_canonicalizer_v4.py"
WRITER_PATH = ROOT / "experiments" / "local_writer_five_article_20260926" / "local_writer_v3.py"
STAGE4 = ROOT / "experiments" / "publication_canonicalizer_dev_20260926" / "devset.json"
STAGE5 = ROOT / "experiments" / "canonicalizer_writer_holdout_4_20260926" / "selection.json"
WRITER_BLOB = "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def test_v4_keeps_frozen_writer_and_stage5_is_not_validation():
    stage5 = json.loads(STAGE5.read_text(encoding="utf-8"))
    assert _git_blob_sha(WRITER_PATH) == WRITER_BLOB
    assert stage5["snapshot_repair"]["quality_measurement_valid"] is False
    assert len(stage5["articles"]) == 4


def test_v4_multiplier_scope_contract_and_development_regressions():
    code = r"""
import importlib.util
import json
import re
import socket
from pathlib import Path

socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network forbidden in Stage 6 Canonicalizer v4 freeze")
)

root = Path.cwd()
canon_path = root / "experiments" / "publication_canonicalizer_dev_20260926" / "publication_canonicalizer_v4.py"
writer_path = root / "experiments" / "local_writer_five_article_20260926" / "local_writer_v3.py"
stage4_path = root / "experiments" / "publication_canonicalizer_dev_20260926" / "devset.json"
stage5_path = root / "experiments" / "canonicalizer_writer_holdout_4_20260926" / "selection.json"

cspec = importlib.util.spec_from_file_location("publication_canonicalizer_v4", canon_path)
canon = importlib.util.module_from_spec(cspec)
cspec.loader.exec_module(canon)
wspec = importlib.util.spec_from_file_location("local_writer_v3_stage6", writer_path)
writer = importlib.util.module_from_spec(wspec)
wspec.loader.exec_module(writer)

stage4 = json.loads(stage4_path.read_text(encoding="utf-8"))["articles"]
stage5 = json.loads(stage5_path.read_text(encoding="utf-8"))["articles"]
failed = next(row for row in stage5 if row["name"].startswith("Auto-research with codex"))

fixed = canon.canonicalize_snapshot(failed)
fixed2 = canon.canonicalize_snapshot(failed)
fixed_twice = canon.canonicalize_snapshot(fixed)

assert fixed == fixed2
assert fixed_twice == fixed
assert fixed["publication_canonicalizer_version"] == "stage6-v4"
assert fixed["canonical_entity_id"] == failed["canonical_entity_id"]
assert fixed["decision"] == failed["decision"]
assert fixed["decision_score"] == failed["decision_score"]
assert fixed["evidence_urls"] == failed["evidence_urls"]
assert "232x Faster（一次情報で示された特定条件下の目安）" in fixed["name"]
assert "実際の改善幅は処理内容・条件・実行環境によって変わります。" in fixed["primary_risk"]

before_numbers = canon._numeric_lexemes("\n".join(
    str(failed.get(key) or "") for key in ("name",) + canon.PUBLICATION_TEXT_FIELDS
))
after_numbers = canon._numeric_lexemes("\n".join(
    str(fixed.get(key) or "") for key in ("name",) + canon.PUBLICATION_TEXT_FIELDS
))
assert before_numbers == after_numbers
assert "232" in after_numbers

# A multiplier with no benchmark/expectation/example modality must stay untouched.
control = dict(failed)
control["name"] = "Control 7x Faster Kernel"
control["source_summary"] = "A neutral project description with implementation notes only."
control["what"] = "A kernel implementation."
control["why_important"] = "It is a technical artifact."
control["decision_reason"] = "The available description is limited."
control["action"] = "Inspect the implementation."
control["primary_risk"] = "Generalization is unknown."
control["best_for"] = "Kernel developers."
control["avoid_for"] = "Teams without kernel work."
control_fixed = canon.canonicalize_snapshot(control)
assert "7x Faster（一次情報で示された特定条件下の目安）" not in control_fixed["name"]


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


def evaluate(rows):
    results = []
    peers = []
    for original in rows:
        snapshot = canon.canonicalize_snapshot(original)
        parsed = writer.to_pipeline_parsed(snapshot)
        article = parsed["note_draft"]
        context = writer.source_context(original)

        fact = pipeline.validate_fact_gate(
            parsed,
            original["name"],
            source_context=context,
            source=original["source"],
            evidence_metadata={},
            source_info=None,
            freshness={},
        )
        editorial = pipeline.validate_editorial_gate(parsed, original["name"])
        publication = pipeline.validate_publication_readiness_gate(
            parsed,
            source_context=context,
            source_info={"sufficient": True},
        )
        human = pipeline.validate_human_appeal_gate(parsed, peers)
        all_pass = bool(
            fact[0] and editorial[0] and publication[0] == "PASS" and human[0] == "ACCEPTABLE"
        )
        results.append({
            "name": original["name"],
            "source": original["source"],
            "fact": fact,
            "editorial": editorial,
            "publication": publication,
            "human": human,
            "all_pass": all_pass,
        })
        peers.append({
            "name": original["name"],
            "sequence": pipeline._style_sequence(article),
            "opening_shingles": tuple(
                pipeline._sentence_shingles(pipeline._article_opening_excerpt(article, 520), 5)
            ),
            "heading_count": len(re.findall(r"^#{2,3}\s+.+$", article, re.MULTILINE)),
            "rhetorical_phrases": tuple(sorted(pipeline._rhetorical_template_phrases(article))),
        })
    return results


stage4_results = evaluate(stage4)
stage5_results = evaluate(stage5)

summary = {
    "stage4": {
        "count": len(stage4_results),
        "pass_count": sum(1 for row in stage4_results if row["all_pass"]),
        "results": stage4_results,
    },
    "stage5_contaminated_development_regression": {
        "count": len(stage5_results),
        "pass_count": sum(1 for row in stage5_results if row["all_pass"]),
        "results": stage5_results,
    },
}
assert summary["stage4"]["pass_count"] == 8, "STAGE6_V4_DEV_REGRESSION::" + json.dumps(
    summary, ensure_ascii=False, sort_keys=True
)
assert summary["stage5_contaminated_development_regression"]["pass_count"] == 4, (
    "STAGE6_V4_DEV_REGRESSION::" + json.dumps(summary, ensure_ascii=False, sort_keys=True)
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
