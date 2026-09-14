from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .url_resolution import (
    canonicalize_url,
    is_internal_x_url,
    is_primary_source_candidate,
    is_unresolved_short_url,
)


class FactoryAdapterContractError(ValueError):
    """Raised when the X discovery queue itself violates the dry-run boundary."""


def _safe_canonicalize(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        return canonicalize_url(value)
    except (TypeError, ValueError):
        return None


def _nonempty_string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _validate_root(queue: Mapping[str, Any]) -> Sequence[object]:
    required = {
        "schema_version": 1,
        "queue_type": "x_primary_source_resolution",
        "source_platform": "x",
        "evidence_status": "discovery_only",
        "factory_write": False,
        "evidence_promoted": False,
    }
    for key, expected in required.items():
        if queue.get(key) != expected:
            raise FactoryAdapterContractError(
                f"invalid queue contract: {key} must be {expected!r}"
            )

    items = queue.get("items")
    if not isinstance(items, list):
        raise FactoryAdapterContractError("invalid queue contract: items must be a list")

    item_count = queue.get("item_count")
    if (
        not isinstance(item_count, int)
        or isinstance(item_count, bool)
        or item_count != len(items)
    ):
        raise FactoryAdapterContractError(
            "invalid queue contract: item_count must equal len(items)"
        )
    return items


def _item_rejection_reason(item: object) -> tuple[Optional[str], Optional[str]]:
    if not isinstance(item, Mapping):
        return None, "invalid_item"

    canonical = _safe_canonicalize(item.get("canonical_url"))
    if not canonical:
        return None, "invalid_canonical_url"
    if is_internal_x_url(canonical):
        return canonical, "x_target_url"
    if is_unresolved_short_url(canonical):
        return canonical, "unresolved_short_url"
    if not is_primary_source_candidate(canonical):
        return canonical, "non_primary_source_candidate"

    if item.get("source_platform") != "x":
        return canonical, "invalid_source_platform"
    if item.get("source_role") != "discovery_signal":
        return canonical, "invalid_source_role"
    if item.get("resolution_status") != "candidate_needs_primary_verification":
        return canonical, "invalid_resolution_status"
    if item.get("evidence_status") != "discovery_only":
        return canonical, "invalid_evidence_status"
    if item.get("is_evidence") is not False:
        return canonical, "evidence_promotion_attempt"
    if item.get("factory_write") is not False:
        return canonical, "factory_write_attempt"

    mention_count = item.get("mention_count")
    if (
        not isinstance(mention_count, int)
        or isinstance(mention_count, bool)
        or mention_count < 1
    ):
        return canonical, "invalid_mention_count"

    if not _nonempty_string_list(item.get("authors")):
        return canonical, "invalid_authors"
    if not _nonempty_string_list(item.get("x_post_ids")):
        return canonical, "invalid_x_post_ids"
    if not _nonempty_string_list(item.get("x_post_urls")):
        return canonical, "invalid_x_post_urls"

    for post_url in item["x_post_urls"]:
        normalized_post_url = _safe_canonicalize(post_url)
        if not normalized_post_url or not is_internal_x_url(normalized_post_url):
            return canonical, "invalid_x_post_urls"

    return canonical, None


def adapt_primary_resolution_queue(queue: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate an X discovery queue without calling or writing to Factory.

    The adapter is intentionally inert. It can only emit validated discovery
    candidates for later primary-source verification; it never executes
    screening and never promotes evidence.
    """
    if not isinstance(queue, Mapping):
        raise FactoryAdapterContractError("queue must be a JSON object")

    items = _validate_root(queue)
    accepted = []
    rejections = []
    seen_urls = set()

    for index, item in enumerate(items):
        canonical, reason = _item_rejection_reason(item)
        if reason is None and canonical in seen_urls:
            reason = "duplicate_primary_url"

        if reason is not None:
            raw_url = item.get("canonical_url") if isinstance(item, Mapping) else None
            rejections.append(
                {
                    "index": index,
                    "canonical_url": canonical or (raw_url if isinstance(raw_url, str) else None),
                    "reason": reason,
                }
            )
            continue

        assert canonical is not None
        seen_urls.add(canonical)
        adapted = dict(item)
        adapted["canonical_url"] = canonical
        adapted["factory_write"] = False
        adapted["is_evidence"] = False
        adapted["screening_executed"] = False
        adapted["evidence_promoted"] = False
        accepted.append(adapted)

    return {
        "schema_version": 1,
        "adapter_type": "x_discovery_factory_dry_run",
        "mode": "dry_run",
        "source_queue_type": "x_primary_source_resolution",
        "source_platform": "x",
        "source_role": "discovery_signal",
        "evidence_status": "discovery_only",
        "factory_write": False,
        "screening_executed": False,
        "evidence_promoted": False,
        "source_item_count": len(items),
        "accepted_count": len(accepted),
        "rejected_count": len(rejections),
        "items": accepted,
        "rejections": rejections,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed dry-run adapter from X discovery to Factory"
    )
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        queue = json.loads(args.queue.read_text(encoding="utf-8"))
        preview = adapt_primary_resolution_queue(queue)
    except (OSError, json.JSONDecodeError, FactoryAdapterContractError) as exc:
        print(f"factory adapter rejected queue: {exc}", file=sys.stderr)
        return 2

    _write_json(args.output, preview)
    print(json.dumps(preview, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
