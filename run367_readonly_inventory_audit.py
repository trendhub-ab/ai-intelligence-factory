"""Offline audit of Notion MCP snapshots. Never grants Ready or writes to Notion.

MCP Markdown omits code captions and may normalize bytes. Surface/Reader failures
are actionable, but clean text cannot prove the persisted Publication Contract,
Fact/Evidence decisions or image quality. No synthetic evidence is manufactured.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
from unittest.mock import patch


@contextmanager
def offline_runtime():
    def blocked(*args, **kwargs):
        raise RuntimeError("Run367 forbids network/provider calls")
    with patch.dict(os.environ, {"SYNTHETIC_REGRESSION_MODE": "true"}), \
         patch("socket.socket.connect", blocked), patch("socket.create_connection", blocked), \
         patch("requests.sessions.Session.request", blocked):
        import pipeline
        import production_pipeline
        production_pipeline.install_runtime_layers(pipeline)
        yield pipeline


def classify(issues, source_supported, complete=False):
    if not source_supported:
        return "unsupported"
    if not complete:
        return "evidence_insufficient"
    if issues:
        return "gate_failed"
    return "surface_clean_but_unproven"


def audit_snapshot(snapshot, pipeline):
    from publication_source_contract import ACTIVE_PUBLIC_SOURCES
    from reader_value_review_bridge import _material_reader_value_issues
    from run248_first_real_publish_quality_calibration import extra_reader_value_issues
    import run249_final_publication_surface_gate as surface

    row = {"url": snapshot["url"], "classification": "evidence_insufficient"}
    response = snapshot["result"]
    if response.get("isError"):
        return {**row, "reason": "fetch_error"}
    data = json.loads(response["content"][0]["text"])
    text = data.get("text", "")
    prop = re.search(r"<properties>\n(.*?)\n</properties>", text, re.S)
    if not prop:
        return {**row, "reason": "properties_missing"}
    props = json.loads(prop.group(1))
    row.update(title=props.get("note記事タイトル") or data.get("title"), source=props.get("情報源"))
    supported = row["source"] in ACTIVE_PUBLIC_SOURCES
    content = re.search(r"<content>\n(.*?)\n</content>", text, re.S)
    bodies = re.findall(r"^```markdown\n(.*?)\n```", content.group(1) if content else "", re.S | re.M)
    complete = bool(len(bodies) == 1 and not data.get("truncated") and not data.get("unknown_block_count")
                    and not data.get("unknown_block_ids"))
    issues = []
    if complete:
        manuscript = bodies[0]
        # Partition existing projection; do not rebuild, polish or repair any text.
        body = manuscript
        if "### 元情報\n" in body:
            prefix, rest = body.split("### 元情報\n", 1)
            boundary = re.search(r"\n\n(?=[^-\n])", rest)
            if not boundary:
                complete = False
            else:
                body = rest[boundary.end():]
        else:
            body = re.sub(r"^# [^\n]+\n+", "", body)
        body = re.split(r"\n(?:---\n+)?### Sources / Evidence\b", body, maxsplit=1)[0]
        if complete:
            signals = pipeline._reader_experience_signals(body)
            issues += _material_reader_value_issues(pipeline, body)
            issues += extra_reader_value_issues(signals)
            title_issue = surface._unbalanced_japanese_quote_issue(row["title"] or "")
            if title_issue:
                issues.append(title_issue)
            issues += surface._extra_japanese_surface_failures(manuscript)
            row["reader_signals"] = signals
        row["fetched_manuscript_sha256"] = hashlib.sha256(manuscript.encode()).hexdigest()
        row["fetched_manuscript_chars"] = len(manuscript)
    row.update(classification=classify(issues, supported, complete), issues=sorted(set(issues)),
               extraction_complete=complete, eyecatch_present=bool(props.get("アイキャッチ")),
               proof_missing=["raw_block_caption_and_byte_identity", "current_full_gate_receipt",
                              "source_evidence_envelope", "eyecatch_quality_receipt"])
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    snapshots = json.loads(args.snapshot.read_text())
    if len(snapshots) != 38 or len({r["url"] for r in snapshots}) != 38:
        raise ValueError("Run367 requires exactly 38 distinct remaining pages")
    with offline_runtime() as pipeline:
        rows = [audit_snapshot(s, pipeline) for s in snapshots]
    counts = Counter(r["classification"] for r in rows)
    report = {"run": "Run367", "scope": "read-only partial current Reader/surface audit",
              "remaining": 38, "additional_rescuable": 0, "counts": dict(counts),
              "writes": 0, "model_calls": 0, "google_api_calls": 0,
              "full_gate_proven": False, "rows": rows}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
