from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .dedupe import cluster_candidates, dedupe_signals, load_seen_ids, save_seen_ids
from .normalize import normalize_post
from .providers import ApifyProvider, FixtureProvider, XDiscoveryProvider

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_FIXTURE = _PACKAGE_DIR / "fixtures" / "sample_posts.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_ingestion(
    provider: XDiscoveryProvider,
    *,
    output_dir: Path,
    max_records: int = 20,
    seen_ids_path: Optional[Path] = None,
    discovered_at: Optional[str] = None,
) -> Dict[str, Any]:
    if not 1 <= int(max_records) <= 100:
        raise ValueError("max_records must be between 1 and 100")

    output_dir = Path(output_dir)
    raw = provider.fetch(max_records=int(max_records))
    signals = [
        normalize_post(record, provider=provider.name, discovered_at=discovered_at)
        for record in raw
    ]
    seen = load_seen_ids(Path(seen_ids_path)) if seen_ids_path else set()
    fresh, duplicate_count, all_seen = dedupe_signals(signals, seen)
    candidates = cluster_candidates(fresh)

    _write_json(output_dir / "raw_posts.json", raw)
    _write_json(output_dir / "normalized_signals.json", [item.to_dict() for item in fresh])
    _write_json(output_dir / "discovery_candidates.json", [item.to_dict() for item in candidates])

    if seen_ids_path:
        save_seen_ids(Path(seen_ids_path), all_seen)

    manifest = {
        "schema_version": 1,
        "source_platform": "x",
        "provider": provider.name,
        "input_count": len(raw),
        "new_signal_count": len(fresh),
        "duplicate_count": duplicate_count,
        "candidate_count": len(candidates),
        "external_url_count": sum(len(item.external_urls) for item in fresh),
        "factory_write": False,
        "evidence_promoted": False,
        "evidence_status": "discovery_only",
        "x_official_api_calls": 0,
        "external_provider_calls": int(getattr(provider, "external_calls", 0)),
        "max_records": int(max_records),
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _load_actor_input(raw: str) -> Mapping[str, Any]:
    raw = (raw or "{}").strip()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Apify Actor input must be a JSON object")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Isolated X discovery ingestion PoC")
    parser.add_argument("--provider", choices=("fixture", "apify"), default="fixture")
    parser.add_argument("--fixture", type=Path, default=_DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seen-ids", type=Path)
    parser.add_argument("--max-records", type=int, default=20)
    parser.add_argument("--apify-actor-id", default=os.getenv("APIFY_ACTOR_ID", ""))
    parser.add_argument("--apify-input-json", default=os.getenv("APIFY_INPUT_JSON", "{}"))
    parser.add_argument(
        "--apify-max-charge-usd",
        type=float,
        default=float(os.getenv("APIFY_MAX_CHARGE_USD", "0.25")),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.provider == "fixture":
        provider: XDiscoveryProvider = FixtureProvider(args.fixture)
    else:
        provider = ApifyProvider(
            token=os.getenv("APIFY_TOKEN", ""),
            actor_id=args.apify_actor_id,
            actor_input=_load_actor_input(args.apify_input_json),
            max_total_charge_usd=args.apify_max_charge_usd,
        )

    manifest = run_ingestion(
        provider,
        output_dir=args.output_dir,
        max_records=args.max_records,
        seen_ids_path=args.seen_ids,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
