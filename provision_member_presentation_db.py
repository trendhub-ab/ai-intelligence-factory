#!/usr/bin/env python3
"""Resolve the one canonical paid-member presentation database.

Run220 removes the old "search by title, then auto-create" ambiguity from the
normal member sync path. Run221 additionally separates the customer-facing
member home from the physical API host that must retain Notion-integration
access. Production must write only to the canonical database and must verify
that the database remains under the API-accessible host page.

The member home exposes linked views of the canonical data source. Moving the
physical database under the member home without explicitly sharing that parent
with the GitHub Actions Notion integration can revoke API readability; therefore
normal Production fails closed on a physical-host mismatch.

A bootstrap search/create path remains available only when an operator
explicitly clears both canonical IDs *and* sets MEMBER_PRESENTATION_ALLOW_CREATE
true. Production pins both IDs and keeps that switch false.

Resolved IDs are written to GITHUB_ENV for the following workflow steps.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

import decision_intelligence
from member_presentation_identity import (
    ALLOW_CREATE_DEFAULT,
    API_HOST_PAGE_ID as DEFAULT_API_HOST_PAGE_ID,
    CANONICAL_DATABASE_ID as DEFAULT_CANONICAL_DATABASE_ID,
    CANONICAL_DATA_SOURCE_ID as DEFAULT_CANONICAL_DATA_SOURCE_ID,
    DEFAULT_TITLE,
)

TITLE = os.environ.get("MEMBER_PRESENTATION_DB_TITLE", DEFAULT_TITLE).strip()
DESCRIPTION = "会員向けの判断専用DB。内部Factory項目を分離し、日本語の判断情報だけを表示します。"
CANONICAL_DATABASE_ID = os.environ.get(
    "MEMBER_PRESENTATION_CANONICAL_DATABASE_ID",
    DEFAULT_CANONICAL_DATABASE_ID,
).strip()
CANONICAL_DATA_SOURCE_ID = os.environ.get(
    "MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID",
    DEFAULT_CANONICAL_DATA_SOURCE_ID,
).strip()
API_HOST_PAGE_ID = os.environ.get(
    "MEMBER_PRESENTATION_API_HOST_PAGE_ID",
    DEFAULT_API_HOST_PAGE_ID,
).strip()
ALLOW_CREATE = os.environ.get("MEMBER_PRESENTATION_ALLOW_CREATE", ALLOW_CREATE_DEFAULT).strip().lower() in {
    "1", "true", "yes", "on"
}
PARENT_PAGE_ID = os.environ.get(
    "MEMBER_PRESENTATION_PARENT_PAGE_ID",
    API_HOST_PAGE_ID,
).strip()


def _headers() -> dict[str, str]:
    return decision_intelligence._headers()


def _text(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}]


def _select_options(items: list[tuple[str, str]]) -> dict[str, Any]:
    return {"select": {"options": [{"name": name, "color": color} for name, color in items]}}


def _multi_options(items: list[tuple[str, str]]) -> dict[str, Any]:
    return {"multi_select": {"options": [{"name": name, "color": color} for name, color in items]}}


def _properties_schema() -> dict[str, Any]:
    return {
        "AI・技術名": {"title": {}},
        "これは何？": {"rich_text": {}},
        "判断": _select_options([
            ("ADOPT", "green"), ("TEST", "blue"), ("WATCH", "yellow"), ("AVOID", "red")
        ]),
        "判断スコア": {"number": {}},
        "判断理由": {"rich_text": {}},
        "今回の話題": {"rich_text": {}},
        "次にやること": {"rich_text": {}},
        "主なリスク": {"rich_text": {}},
        "向いている用途": {"rich_text": {}},
        "向いていない用途": {"rich_text": {}},
        "根拠の確かさ": _select_options([("高", "green"), ("中", "yellow"), ("低", "red")]),
        "実用度": _select_options([("高", "green"), ("中", "yellow"), ("低", "red")]),
        "分野": _select_options([
            ("AIモデル", "purple"), ("エージェント", "blue"), ("開発ツール", "green"),
            ("基盤", "gray"), ("データ", "yellow"), ("セキュリティ", "red"),
            ("マルチモーダル", "pink"), ("製品・サービス", "orange"), ("その他", "default"),
        ]),
        "分類": _select_options([("実務判断", "green"), ("Deep Tech", "purple"), ("参考資料", "gray")]),
        "評価の変化": {"number": {}},
        "評価が変わった理由": {"rich_text": {}},
        "重要変化日": {"date": {}},
        "最終確認日": {"date": {}},
        "見つけた日": {"date": {}},
        "一次情報": {"rich_text": {}},
        "関連記事": {"url": {}},
        "公式ページ": {"url": {}},
        "情報源": _multi_options([
            ("GitHub", "default"), ("HackerNews", "orange"), ("ArXiv", "red"),
            ("ProductHunt", "blue"), ("Unknown", "gray")
        ]),
        "注目順位": {"number": {}},
        "今月の重要変化": {"checkbox": {}},
        "同期ID": {"rich_text": {}},
    }


def _plain_title(obj: dict[str, Any]) -> str:
    title = obj.get("title") or []
    return "".join(
        str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "")
        for x in title
    ).strip()


def _candidate_ids(item: dict[str, Any]) -> tuple[str, str] | None:
    ds_id = str(item.get("id") or "").strip()
    parent = item.get("parent") or {}
    db_id = str(parent.get("database_id") or "").strip()
    if ds_id and db_id:
        return db_id, ds_id
    if not ds_id:
        return None
    detail = requests.get(
        f"https://api.notion.com/v1/data_sources/{ds_id}",
        headers=_headers(),
        timeout=20,
    )
    detail.raise_for_status()
    db_id = str((detail.json().get("parent") or {}).get("database_id") or "").strip()
    return (db_id, ds_id) if db_id else None


def _verify_api_host() -> None:
    if not API_HOST_PAGE_ID:
        raise RuntimeError("MEMBER_PRESENTATION_API_HOST_PAGE_ID is required in normal operation")
    detail = requests.get(
        f"https://api.notion.com/v1/databases/{CANONICAL_DATABASE_ID}",
        headers=_headers(),
        timeout=20,
    )
    if detail.status_code != 200:
        raise RuntimeError(
            "Canonical member presentation database is not readable while verifying its API host "
            f"(HTTP {detail.status_code})."
        )
    parent = detail.json().get("parent") or {}
    parent_type = str(parent.get("type") or "").strip()
    if parent_type != "page_id":
        raise RuntimeError(
            "Canonical member presentation database has unexpected parent type "
            f"{parent_type!r} (expected 'page_id'); it may have been moved to workspace root or another database."
        )
    actual_host = str(parent.get("page_id") or "").strip()
    if actual_host != API_HOST_PAGE_ID:
        raise RuntimeError(
            "Canonical member presentation physical host mismatch: "
            f"expected page={API_HOST_PAGE_ID!r}, actual page={actual_host!r}. "
            "Keep the physical DB under the API-accessible host and expose it to members with linked views."
        )


def _resolve_canonical() -> tuple[str, str] | None:
    """Return the pinned canonical DB only when IDs, title and API host verify."""
    if bool(CANONICAL_DATABASE_ID) != bool(CANONICAL_DATA_SOURCE_ID):
        raise RuntimeError(
            "Canonical member presentation IDs are incomplete; database and data source IDs must be set together."
        )
    if not CANONICAL_DATABASE_ID:
        return None

    detail = requests.get(
        f"https://api.notion.com/v1/data_sources/{CANONICAL_DATA_SOURCE_ID}",
        headers=_headers(),
        timeout=20,
    )
    if detail.status_code != 200:
        raise RuntimeError(
            "Canonical member presentation data source is not readable; refusing to create or select another DB "
            f"(HTTP {detail.status_code})."
        )
    obj = detail.json()
    parent_db = str((obj.get("parent") or {}).get("database_id") or "").strip()
    if parent_db != CANONICAL_DATABASE_ID:
        raise RuntimeError(
            "Canonical member presentation ID mismatch: "
            f"configured database={CANONICAL_DATABASE_ID!r} data_source_parent={parent_db!r}."
        )
    actual_title = _plain_title(obj)
    if not actual_title:
        raise RuntimeError(
            "Canonical member presentation title could not be read from the API response; refusing to treat this as a match."
        )
    if actual_title != TITLE:
        raise RuntimeError(
            f"Canonical member presentation title mismatch: expected {TITLE!r}, got {actual_title!r}."
        )
    _verify_api_host()
    return CANONICAL_DATABASE_ID, CANONICAL_DATA_SOURCE_ID


def _search_existing() -> tuple[str, str] | None:
    """Explicit bootstrap-only exact-title lookup."""
    res = requests.post(
        "https://api.notion.com/v1/search",
        headers=_headers(),
        json={"query": TITLE, "page_size": 100},
        timeout=20,
    )
    res.raise_for_status()
    matches: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in res.json().get("results") or []:
        if item.get("object") != "data_source" or _plain_title(item) != TITLE:
            continue
        ids = _candidate_ids(item)
        if ids and ids not in seen:
            seen.add(ids)
            matches.append(ids)
    if len(matches) > 1:
        raise RuntimeError(
            f"Ambiguous member presentation DB title {TITLE!r}: found {len(matches)} exact matches."
        )
    return matches[0] if matches else None


def _create() -> tuple[str, str]:
    if not ALLOW_CREATE:
        raise RuntimeError(
            "Automatic member presentation DB creation is disabled. Configure the canonical IDs instead."
        )
    if not PARENT_PAGE_ID:
        raise ValueError("MEMBER_PRESENTATION_PARENT_PAGE_ID is required for an internal Notion integration")
    host = requests.get(
        f"https://api.notion.com/v1/pages/{PARENT_PAGE_ID}",
        headers=_headers(),
        timeout=20,
    )
    if host.status_code != 200:
        raise RuntimeError(f"Member presentation parent is not API-accessible: HTTP {host.status_code}")
    payload = {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
        "title": _text(TITLE),
        "description": _text(DESCRIPTION),
        "is_inline": False,
        "initial_data_source": {"properties": _properties_schema()},
        "icon": {"type": "emoji", "emoji": "🧭"},
    }
    res = requests.post(
        "https://api.notion.com/v1/databases",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Member presentation DB create failed: HTTP {res.status_code} {res.text[:1000]}")
    obj = res.json()
    db_id = str(obj.get("id") or "").strip()
    data_sources = obj.get("data_sources") or []
    ds_id = str((data_sources[0] if data_sources else {}).get("id") or "").strip()
    if not ds_id and db_id:
        detail = requests.get(
            f"https://api.notion.com/v1/databases/{db_id}",
            headers=_headers(),
            timeout=20,
        )
        detail.raise_for_status()
        sources = detail.json().get("data_sources") or []
        ds_id = str((sources[0] if sources else {}).get("id") or "").strip()
    if not db_id or not ds_id:
        raise RuntimeError(
            f"Member presentation DB created but IDs were incomplete: database={db_id!r} data_source={ds_id!r}"
        )
    return db_id, ds_id


def _write_env(db_id: str, ds_id: str) -> None:
    env_path = os.environ.get("GITHUB_ENV", "").strip()
    if not env_path:
        return
    with Path(env_path).open("a", encoding="utf-8") as fp:
        fp.write(f"NOTION_MEMBER_PRESENTATION_DATABASE_ID={db_id}\n")
        fp.write(f"NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID={ds_id}\n")


def provision() -> dict[str, Any]:
    if not decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")

    canonical = _resolve_canonical()
    if canonical:
        db_id, ds_id = canonical
        created = False
    else:
        if not ALLOW_CREATE:
            raise RuntimeError(
                "Canonical member presentation IDs are required in normal operation; "
                "title search and DB creation are disabled unless bootstrap is explicitly enabled."
            )
        existing = _search_existing()
        if existing:
            db_id, ds_id = existing
            created = False
        else:
            db_id, ds_id = _create()
            created = True

    _write_env(db_id, ds_id)
    return {
        "created": created,
        "database_id": db_id,
        "data_source_id": ds_id,
        "canonical": bool(canonical),
        "api_host_page_id": API_HOST_PAGE_ID if canonical else PARENT_PAGE_ID,
        "auto_create_enabled": ALLOW_CREATE,
    }


def main() -> None:
    print(provision())


if __name__ == "__main__":
    main()
