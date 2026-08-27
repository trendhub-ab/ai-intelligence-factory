"""Phase 0.6 runner for the isolated X Intelligence Layer.

Consumes already-produced Factory records or the latest local observed_history
screening snapshot and writes review-only X draft artifacts.

Safety invariants:
- no Gemini calls;
- no X API calls;
- no Notion writes;
- no article-pipeline imports;
- no automatic posting.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .generator import build_x_post, save_pending_post
from .selector import select_x_candidates


SUPPORTED_SUFFIXES = {".json", ".jsonl", ".ndjson", ".csv"}


def _normalize_container(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("items", "records", "candidates", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
        return [dict(payload)]
    return []


def load_records(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported input format: {suffix or '<none>'}")
    if not source.exists():
        raise FileNotFoundError(source)

    if suffix == ".json":
        return _normalize_container(json.loads(source.read_text(encoding="utf-8-sig")))

    if suffix in {".jsonl", ".ndjson"}:
        records: list[dict[str, Any]] = []
        for line_no, raw in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError(f"line {line_no} is not a JSON object")
            records.append(dict(value))
        return records

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def find_latest_screening_snapshot(observed_history_dir: str | Path = "observed_history") -> Path:
    """Return the latest locally available Factory screening snapshot."""

    directory = Path(observed_history_dir)
    if not directory.exists():
        raise FileNotFoundError(directory)
    snapshots = sorted(directory.glob("screening_*.json"))
    if not snapshots:
        raise FileNotFoundError(f"no screening_*.json snapshots in {directory}")
    return snapshots[-1]


def load_latest_observed_history(observed_history_dir: str | Path = "observed_history") -> tuple[Path, list[dict[str, Any]]]:
    path = find_latest_screening_snapshot(observed_history_dir)
    return path, load_records(path)


def _slug(index: int, item: Mapping[str, Any]) -> str:
    value = str(item.get("Name") or item.get("name") or item.get("Title") or item.get("title") or "candidate")
    compact = "-".join(value.split())[:48].strip("-") or "candidate"
    return f"{index:02d}-{compact}"


def generate_batch(
    records: Iterable[Mapping[str, Any]],
    *,
    output_dir: str | Path = "artifacts/x_posts/pending",
    max_items: int = 5,
    min_screening_score: float = 55,
    min_decision_score: float = 60,
    max_chars: int = 280,
    input_path: str | None = None,
) -> dict[str, Any]:
    source_records = [dict(record) for record in records]
    selected = select_x_candidates(
        source_records,
        min_screening_score=min_screening_score,
        min_decision_score=min_decision_score,
        max_items=max_items,
    )

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    drafts: list[dict[str, Any]] = []

    for index, item in enumerate(selected, start=1):
        draft = build_x_post(item, max_chars=max_chars)
        stem = _slug(index, item)
        json_path, md_path = save_pending_post(draft, output_dir=target, stem=stem)
        drafts.append(
            {
                "rank": index,
                "name": item.get("Name") or item.get("name") or item.get("Title") or item.get("title") or "",
                "source": item.get("Source") or item.get("source") or "",
                "x_candidate_score": item.get("x_candidate_score"),
                "screening_score": item.get("x_screening_score"),
                "decision_score": item.get("x_decision_score"),
                "primary_url": draft["primary_url"],
                "characters": draft["characters"],
                "json_artifact": json_path.name,
                "markdown_artifact": md_path.name,
            }
        )

    manifest = {
        "status": "X Batch Pending Review",
        "input_path": input_path,
        "input_records": len(source_records),
        "selected_records": len(selected),
        "generated_drafts": len(drafts),
        "max_items": max_items,
        "min_screening_score": min_screening_score,
        "min_decision_score": min_decision_score,
        "max_characters": max_chars,
        "gemini_calls": 0,
        "x_api_calls": 0,
        "auto_posted": False,
        "drafts": drafts,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def generate_from_latest_observed_history(
    *,
    observed_history_dir: str | Path = "observed_history",
    output_dir: str | Path = "artifacts/x_posts/pending",
    max_items: int = 5,
    min_screening_score: float = 55,
    min_decision_score: float = 60,
    max_chars: int = 280,
) -> dict[str, Any]:
    path, records = load_latest_observed_history(observed_history_dir)
    return generate_batch(
        records,
        output_dir=output_dir,
        max_items=max_items,
        min_screening_score=min_screening_score,
        min_decision_score=min_decision_score,
        max_chars=max_chars,
        input_path=str(path),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate review-only X drafts from Factory outputs")
    parser.add_argument("input", nargs="?", help="JSON, JSONL/NDJSON, or CSV export")
    parser.add_argument("--latest-observed-history", action="store_true")
    parser.add_argument("--observed-history-dir", default="observed_history")
    parser.add_argument("--output-dir", default="artifacts/x_posts/pending")
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--min-screening-score", type=float, default=55)
    parser.add_argument("--min-decision-score", type=float, default=60)
    parser.add_argument("--max-chars", type=int, default=280)
    args = parser.parse_args(argv)

    if args.latest_observed_history:
        if args.input:
            parser.error("input and --latest-observed-history are mutually exclusive")
        manifest = generate_from_latest_observed_history(
            observed_history_dir=args.observed_history_dir,
            output_dir=args.output_dir,
            max_items=args.max_items,
            min_screening_score=args.min_screening_score,
            min_decision_score=args.min_decision_score,
            max_chars=args.max_chars,
        )
    else:
        if not args.input:
            parser.error("input is required unless --latest-observed-history is used")
        records = load_records(args.input)
        manifest = generate_batch(
            records,
            output_dir=args.output_dir,
            max_items=args.max_items,
            min_screening_score=args.min_screening_score,
            min_decision_score=args.min_decision_score,
            max_chars=args.max_chars,
            input_path=str(args.input),
        )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
