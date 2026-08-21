"""Legacy Internal Notion DB -> Technology Intelligence DB migration.

Safety defaults:
- DRY RUN unless --apply is explicitly supplied.
- Reads the existing Internal Pipeline DB only; never patches/archives/deletes it.
- Never copies legacy Decision Score or Decision into Adoption Score/Status.
- Canonical Entity ID exact/grouped migration only; no fuzzy-title merge.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import requests

import decision_intelligence as di

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "").strip()  # existing Internal DB read token
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "").strip()
NOTION_DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "").strip()


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _query_url() -> str:
    if NOTION_DATA_SOURCE_ID:
        return f"https://api.notion.com/v1/data_sources/{NOTION_DATA_SOURCE_ID}/query"
    return f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"


def _plain(prop: dict) -> str:
    items = prop.get("title") or prop.get("rich_text") or []
    return "".join(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "" for x in items).strip()


def _select(prop: dict) -> str:
    return ((prop or {}).get("select") or {}).get("name") or ""


def _date(prop: dict) -> str | None:
    return ((prop or {}).get("date") or {}).get("start")


def _fetch_all_internal_pages() -> list[dict]:
    if not NOTION_API_KEY or not (NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID):
        raise ValueError("Internal DB read requires NOTION_API_KEY + NOTION_DATA_SOURCE_ID/DATABASE_ID")
    rows: list[dict] = []
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        res = requests.post(_query_url(), json=payload, headers=_headers(), timeout=15)
        res.raise_for_status()
        data = res.json()
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return rows


def _page_to_seed(page: dict) -> tuple[dict, di.EntityResolution]:
    props = page.get("properties", {})
    name = _plain(props.get("Name", {})) or "Legacy Technology"
    url = (props.get("URL", {}) or {}).get("url") or ""
    source = _select(props.get("Source", {})) or "Unknown"
    evidence_text = _plain(props.get("Evidence URLs", {}))
    evidence_urls = [x.strip() for x in evidence_text.splitlines() if x.strip()]
    repo = {
        "source": source,
        "nameWithOwner": name,
        "url": url,
        "primaryUrl": url,
        "sourceDetails": {"related_links": evidence_urls},
    }
    resolution = di.resolve_canonical_entity_id(repo, {"primary_url": url, "evidence_documents": [{"url": x} for x in evidence_urls]})
    seed = {
        "internal_page_id": page.get("id"),
        "name": name,
        "url": url,
        "source": source,
        "sources": [source],
        "evidence_urls": evidence_urls,
        "first_seen": page.get("created_time") or _date(props.get("Analyzed At", {})) or _date(props.get("Published At", {})),
        "published_at": _date(props.get("Published At", {})),
        "analyzed_at": _date(props.get("Analyzed At", {})),
        "pipeline_status": _select(props.get("Status", {})),
        "content_status": _select(props.get("Content Status", {})),
        "article_status": _select(props.get("Article Status", {})),
        "screening_score": (props.get("Screening Score", {}) or {}).get("number"),
        "screening_reason": _plain(props.get("Screening Reason", {})),
        "source_summary": _plain(props.get("Source Summary", {})),
    }
    return seed, resolution


def _merge_seed_rows(rows: list[tuple[dict, di.EntityResolution]]) -> list[tuple[dict, di.EntityResolution]]:
    grouped: dict[str, list[tuple[dict, di.EntityResolution]]] = {}
    for seed, resolution in rows:
        grouped.setdefault(resolution.entity_id, []).append((seed, resolution))

    merged: list[tuple[dict, di.EntityResolution]] = []
    for entity_id, group in grouped.items():
        # Latest analyzed/current state wins descriptive fields; earliest timestamp becomes First Seen.
        def sort_key(item):
            seed, _ = item
            return seed.get("analyzed_at") or seed.get("first_seen") or ""
        group_sorted = sorted(group, key=sort_key)
        latest, resolution = group_sorted[-1]
        out = dict(latest)
        out["sources"] = list(dict.fromkeys(
            source for seed, _ in group_sorted for source in (seed.get("sources") or []) if source
        ))
        out["evidence_urls"] = list(dict.fromkeys(
            url for seed, _ in group_sorted for url in (seed.get("evidence_urls") or []) if url
        ))
        first_candidates = [seed.get("first_seen") for seed, _ in group_sorted if seed.get("first_seen")]
        out["first_seen"] = min(first_candidates) if first_candidates else latest.get("first_seen")
        # Union aliases from every exact-resolved legacy row. No fuzzy matching.
        aliases = tuple(dict.fromkeys(alias for _, res in group_sorted for alias in res.aliases))
        resolution = di.EntityResolution(resolution.entity_id, resolution.status, resolution.primary_url, aliases, resolution.reason)
        merged.append((out, resolution))
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually create legacy seed records. Default is dry-run.")
    parser.add_argument("--output", default="decision_intelligence_migration_plan.json")
    args = parser.parse_args()

    if not di.ENABLE_DECISION_INTELLIGENCE_DB:
        raise ValueError("Set ENABLE_DECISION_INTELLIGENCE_DB=true and configure TEST DB IDs before migration")
    di.preflight_decision_intelligence_schema()
    pages = _fetch_all_internal_pages()
    converted = [_page_to_seed(page) for page in pages]
    merged = _merge_seed_rows(converted)
    migrated_at = datetime.now(timezone.utc).isoformat()

    plan = []
    created = 0
    skipped_existing = 0
    errors = []
    for seed, resolution in merged:
        row = {
            "entity_id": resolution.entity_id,
            "resolution_status": resolution.status,
            "name": seed.get("name"),
            "primary_url": resolution.primary_url,
            "legacy_rows_merged": sum(1 for s, r in converted if r.entity_id == resolution.entity_id),
            "action": "DRY_RUN_CREATE",
        }
        try:
            existing = di.get_technology_record_by_entity_id(resolution.entity_id)
            if existing:
                row["action"] = "SKIP_EXISTING"
                skipped_existing += 1
            elif args.apply:
                page_id = di.create_legacy_seed(seed, resolution, migrated_at)
                row["action"] = "CREATED"
                row["technology_page_id"] = page_id
                created += 1
        except Exception as exc:
            row["action"] = "ERROR"
            row["error"] = str(exc)
            errors.append(str(exc))
        plan.append(row)

    result = {
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "internal_pages": len(pages),
        "canonical_entities": len(merged),
        "created": created,
        "skipped_existing": skipped_existing,
        "errors": len(errors),
        "records": plan,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
