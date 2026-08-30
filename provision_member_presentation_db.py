#!/usr/bin/env python3
"""Resolve or create the API-owned clean member presentation database.

The Factory uses an internal Notion integration. Internal integrations cannot
create workspace-level private databases, so the database is initially created
under an API-accessible host page. The member UI uses linked views, so this
physical host is not part of the member navigation. A separate UI connector may
move the database later if the API connection retains access after the move.

Resolved IDs are written to GITHUB_ENV so the following workflow step can sync
without hard-coded destination IDs.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

import decision_intelligence

TITLE = os.environ.get("MEMBER_PRESENTATION_DB_TITLE", "AI・技術一覧｜判断DB").strip()
DESCRIPTION = "会員向けの判断専用DB。内部Factory項目を分離し、日本語の判断情報だけを表示します。"
PARENT_PAGE_ID = os.environ.get(
    "MEMBER_PRESENTATION_PARENT_PAGE_ID",
    "3c5479ff-dca9-8178-867c-d9249a3ff5c8",
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


def _search_existing() -> tuple[str, str] | None:
    res = requests.post(
        "https://api.notion.com/v1/search",
        headers=_headers(),
        json={"query": TITLE, "page_size": 100},
        timeout=20,
    )
    res.raise_for_status()
    for item in res.json().get("results") or []:
        if item.get("object") != "data_source" or _plain_title(item) != TITLE:
            continue
        ds_id = str(item.get("id") or "").strip()
        parent = item.get("parent") or {}
        db_id = str(parent.get("database_id") or "").strip()
        if ds_id and db_id:
            return db_id, ds_id
        if ds_id:
            detail = requests.get(
                f"https://api.notion.com/v1/data_sources/{ds_id}",
                headers=_headers(),
                timeout=20,
            )
            detail.raise_for_status()
            db_id = str((detail.json().get("parent") or {}).get("database_id") or "").strip()
            if db_id:
                return db_id, ds_id
    return None


def _create() -> tuple[str, str]:
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
    existing = _search_existing()
    created = existing is None
    db_id, ds_id = existing or _create()
    verify = requests.get(
        f"https://api.notion.com/v1/data_sources/{ds_id}",
        headers=_headers(),
        timeout=20,
    )
    if verify.status_code != 200:
        raise RuntimeError(
            f"Member presentation data source is not readable after provision: {verify.status_code}"
        )
    _write_env(db_id, ds_id)
    return {"created": created, "database_id": db_id, "data_source_id": ds_id}


def main() -> None:
    print(provision())


if __name__ == "__main__":
    main()
