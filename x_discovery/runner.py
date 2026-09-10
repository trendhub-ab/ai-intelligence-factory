from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .dedupe import cluster_candidates, dedupe_signals, load_seen_ids, save_seen_ids
from .handoff import build_primary_resolution_queue
from .normalize import normalize_post
from .providers import ApifyProvider, FixtureProvider, XDiscoveryProvider
from .url_resolution import (
    OfficialShortenerResolver,
    TcoRedirectResolver,
    enrich_record_with_shorteners,
)

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
    resolve_tco: bool = False,
    resolve_official_shorteners: bool = False,
) -> Dict[str, Any]:
    if not 1 <= int(max_records) <= 100:
        raise ValueError("max_records must be between 1 and 100")

    output_dir = Path(output_dir)
    provider_raw = provider.fetch(max_records=int(max_records))
    tco_resolver = TcoRedirectResolver() if resolve_tco else None
    official_resolver = OfficialShortenerResolver() if resolve_official_shorteners else None
    resolvers = [item for item in (tco_resolver, official_resolver) if item is not None]
    raw = [
        enrich_record_with_shorteners(record, resolvers) if resolvers else dict(record)
        for record in provider_raw
    ]
    signals = [
        normalize_post(record, provider=provider.name, discovered_at=discovered_at)
        for record in raw
    ]
    seen = load_seen_ids(Path(seen_ids_path)) if seen_ids_path else set()
    fresh, duplicate_count, all_seen = dedupe_signals(signals, seen)
    candidates = cluster_candidates(fresh)
    primary_candidate_count = sum(1 for item in candidates if item.primary_source_candidate)
    primary_candidate_rate = round(primary_candidate_count / len(candidates), 4) if candidates else 0.0
    primary_resolution_queue = build_primary_resolution_queue(candidates)

    provider_errors = list(getattr(provider, "provider_errors", []) or [])
    skipped_pinned = int(getattr(provider, "skipped_pinned", 0) or 0)
    requested_profiles = int(getattr(provider, "requested_profile_count", 0) or 0)
    profile_rows_read = int(getattr(provider, "profile_rows_read", 0) or 0)
    empty_profiles = int(getattr(provider, "empty_profile_count", 0) or 0)
    profiles_with_posts = sorted(str(value) for value in (getattr(provider, "profiles_with_posts", set()) or set()))
    provider_raw_items = list(getattr(provider, "raw_items", []) or [])

    def resolver_stats(resolver: Any) -> Dict[str, int]:
        if resolver is None:
            return {
                "calls": 0,
                "network_requests": 0,
                "successes": 0,
                "internal_resolutions": 0,
                "unresolved_chains": 0,
                "failures": 0,
            }
        return {
            "calls": int(resolver.calls),
            "network_requests": int(resolver.network_requests),
            "successes": int(resolver.successes),
            "internal_resolutions": int(resolver.internal_resolutions),
            "unresolved_chains": int(resolver.unresolved_chains),
            "failures": int(resolver.failures),
        }

    tco = resolver_stats(tco_resolver)
    official = resolver_stats(official_resolver)

    _write_json(output_dir / "raw_posts.json", raw)
    _write_json(output_dir / "normalized_signals.json", [item.to_dict() for item in fresh])
    _write_json(output_dir / "discovery_candidates.json", [item.to_dict() for item in candidates])
    _write_json(output_dir / "primary_resolution_queue.json", primary_resolution_queue)
    if provider_raw_items:
        _write_json(output_dir / "provider_raw_items.json", provider_raw_items)
    _write_json(
        output_dir / "provider_diagnostics.json",
        {
            "provider": provider.name,
            "requested_profile_count": requested_profiles,
            "profile_rows_read": profile_rows_read,
            "profiles_with_posts_count": len(profiles_with_posts),
            "profiles_with_posts": profiles_with_posts,
            "empty_profile_count": empty_profiles,
            "provider_error_count": len(provider_errors),
            "provider_errors": provider_errors,
            "skipped_pinned_count": skipped_pinned,
            "tco_resolution_enabled": bool(resolve_tco),
            "tco_resolution_calls": tco["calls"],
            "tco_resolution_network_requests": tco["network_requests"],
            "tco_resolution_successes": tco["successes"],
            "tco_internal_resolutions": tco["internal_resolutions"],
            "tco_unresolved_chains": tco["unresolved_chains"],
            "tco_resolution_failures": tco["failures"],
            "official_shortener_resolution_enabled": bool(resolve_official_shorteners),
            "official_shortener_calls": official["calls"],
            "official_shortener_network_requests": official["network_requests"],
            "official_shortener_successes": official["successes"],
            "official_shortener_unresolved_chains": official["unresolved_chains"],
            "official_shortener_failures": official["failures"],
            "primary_candidate_count": primary_candidate_count,
            "primary_candidate_rate": primary_candidate_rate,
            "primary_resolution_queue_count": int(primary_resolution_queue["item_count"]),
        },
    )

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
        "primary_candidate_count": primary_candidate_count,
        "primary_candidate_rate": primary_candidate_rate,
        "primary_resolution_queue_count": int(primary_resolution_queue["item_count"]),
        "external_url_count": sum(len(item.external_urls) for item in fresh),
        "requested_profile_count": requested_profiles,
        "profile_rows_read": profile_rows_read,
        "profiles_with_posts_count": len(profiles_with_posts),
        "empty_profile_count": empty_profiles,
        "provider_error_count": len(provider_errors),
        "skipped_pinned_count": skipped_pinned,
        "tco_resolution_enabled": bool(resolve_tco),
        "tco_resolution_calls": tco["calls"],
        "tco_resolution_network_requests": tco["network_requests"],
        "tco_resolution_successes": tco["successes"],
        "tco_internal_resolutions": tco["internal_resolutions"],
        "tco_unresolved_chains": tco["unresolved_chains"],
        "tco_resolution_failures": tco["failures"],
        "official_shortener_resolution_enabled": bool(resolve_official_shorteners),
        "official_shortener_calls": official["calls"],
        "official_shortener_network_requests": official["network_requests"],
        "official_shortener_successes": official["successes"],
        "official_shortener_unresolved_chains": official["unresolved_chains"],
        "official_shortener_failures": official["failures"],
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
    parser.add_argument("--resolve-tco", action="store_true")
    parser.add_argument("--resolve-official-shorteners", action="store_true")
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
        resolve_tco=args.resolve_tco,
        resolve_official_shorteners=args.resolve_official_shorteners,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
