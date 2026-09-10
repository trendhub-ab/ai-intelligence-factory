from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class XDiscoveryProvider(ABC):
    name = "unknown"
    external_calls = 0
    skipped_pinned = 0
    provider_errors: List[Dict[str, str]] = []

    @abstractmethod
    def fetch(self, *, max_records: int) -> List[Dict[str, Any]]:
        raise NotImplementedError


class FixtureProvider(XDiscoveryProvider):
    name = "fixture"

    def __init__(self, fixture_path: Path):
        self.fixture_path = Path(fixture_path)
        self.external_calls = 0
        self.skipped_pinned = 0
        self.provider_errors = []
        self.raw_items: List[Dict[str, Any]] = []
        self.requested_profile_count = 0
        self.profile_rows_read = 0
        self.empty_profile_count = 0
        self.profiles_with_posts: Set[str] = set()

    def fetch(self, *, max_records: int) -> List[Dict[str, Any]]:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("items", payload.get("data", []))
        if not isinstance(payload, list):
            raise ValueError("fixture must contain a JSON array or an object with items/data")
        self.raw_items = [dict(item) for item in payload if isinstance(item, Mapping)]
        return self.raw_items[:max_records]


class ApifyProvider(XDiscoveryProvider):
    name = "apify"

    def __init__(
        self,
        *,
        token: str,
        actor_id: str,
        actor_input: Optional[Mapping[str, Any]] = None,
        timeout_seconds: int = 120,
        max_total_charge_usd: float = 0.25,
    ):
        if not token.strip():
            raise ValueError("APIFY_TOKEN is required for live Apify runs")
        if not actor_id.strip():
            raise ValueError("APIFY_ACTOR_ID is required for live Apify runs")
        if not 1 <= int(timeout_seconds) <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        if not 0 < float(max_total_charge_usd) <= 1.0:
            raise ValueError("max_total_charge_usd must be > 0 and <= 1.0 for this PoC")
        self.token = token.strip()
        self.actor_id = actor_id.strip()
        self.actor_input = dict(actor_input or {})
        self.timeout_seconds = int(timeout_seconds)
        self.max_total_charge_usd = float(max_total_charge_usd)
        self.external_calls = 0
        self.skipped_pinned = 0
        self.provider_errors: List[Dict[str, str]] = []
        self.raw_items: List[Dict[str, Any]] = []
        self.requested_profile_count = self._count_requested_profiles()
        self.profile_rows_read = 0
        self.empty_profile_count = 0
        self.profiles_with_posts: Set[str] = set()

    def _count_requested_profiles(self) -> int:
        handles = self.actor_input.get("handles")
        start_urls = self.actor_input.get("startUrls")
        handle_count = len(handles) if isinstance(handles, list) else 0
        url_count = len(start_urls) if isinstance(start_urls, list) else 0
        return handle_count + url_count

    @staticmethod
    def _row_handle(row: Mapping[str, Any]) -> str:
        value = (
            row.get("handle")
            or row.get("userName")
            or row.get("username")
            or row.get("authorHandle")
            or row.get("authorUserName")
        )
        return str(value or "unknown").lstrip("@")

    def _record_error(self, row: Mapping[str, Any]) -> None:
        diagnostic = {
            "handle": self._row_handle(row),
            "error": str(row.get("error") or "unknown_error"),
        }
        description = row.get("errorDescription") or row.get("error_description")
        if description:
            diagnostic["description"] = str(description)
        for source_key, target_key in (
            ("oldestVisiblePostAt", "oldest_visible_post_at"),
            ("oldestVisibleAt", "oldest_visible_at"),
            ("windowStart", "window_start"),
        ):
            value = row.get(source_key)
            if value is not None and value != "":
                diagnostic[target_key] = str(value)
        self.provider_errors.append(diagnostic)

    def _accept_post(self, row: Mapping[str, Any], accepted: List[Dict[str, Any]]) -> None:
        post = dict(row)
        if bool(post.get("isPinned") or post.get("is_pinned")):
            self.skipped_pinned += 1
            return
        accepted.append(post)

    def _flatten_profile_rows(self, payload: List[Dict[str, Any]], *, max_records: int) -> List[Dict[str, Any]]:
        accepted: List[Dict[str, Any]] = []
        for row in payload:
            if row.get("error"):
                self._record_error(row)
                continue

            self.profile_rows_read += 1
            handle = self._row_handle(row)
            posts = row.get("posts")
            if not isinstance(posts, list) or not posts:
                self.empty_profile_count += 1
                continue

            added_for_profile = 0
            for item in posts:
                if not isinstance(item, Mapping):
                    continue
                post = dict(item)
                post.setdefault("authorUserName", handle)
                before = len(accepted)
                self._accept_post(post, accepted)
                if len(accepted) > before:
                    added_for_profile += 1
                if len(accepted) >= max_records:
                    break
            if added_for_profile:
                self.profiles_with_posts.add(handle)
            elif posts:
                self.empty_profile_count += 1
            if len(accepted) >= max_records:
                break
        return accepted

    @staticmethod
    def _safe_http_error(exc: HTTPError) -> RuntimeError:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        body = " ".join(body.split())[:2000]
        message = f"Apify HTTP {exc.code}: {exc.reason}"
        if body:
            message += f"; response={body}"
        return RuntimeError(message)

    def _request(self, actor_input: Mapping[str, Any], *, paid_item_cap: int, charge_cap_usd: float) -> List[Dict[str, Any]]:
        actor = quote(self.actor_id, safe="~")
        query = urlencode(
            {
                "timeout": self.timeout_seconds,
                "maxItems": int(paid_item_cap),
                "maxTotalChargeUsd": float(charge_cap_usd),
                "clean": "true",
                "format": "json",
            }
        )
        endpoint = f"https://api.apify.com/v2/actors/{actor}/run-sync-get-dataset-items?{query}"
        body = json.dumps(dict(actor_input), ensure_ascii=False).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "ai-intelligence-factory-x-discovery/0.6",
            },
            method="POST",
        )
        self.external_calls += 1
        try:
            with urlopen(request, timeout=self.timeout_seconds + 15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise self._safe_http_error(exc) from exc

        if isinstance(payload, dict):
            payload = payload.get("items", payload.get("data", []))
        if not isinstance(payload, list):
            raise ValueError("Apify Actor response must be a JSON array or contain items/data")
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    def _fetch_isolated_profiles(self, base_input: Mapping[str, Any]) -> List[Dict[str, Any]]:
        handles = base_input.get("handles")
        if not isinstance(handles, list) or not handles:
            raise ValueError("isolateProfiles requires a non-empty handles array")
        if len(handles) > 100:
            raise ValueError("isolateProfiles supports at most 100 handles per PoC run")

        per_call_charge_cap = self.max_total_charge_usd / len(handles)
        if per_call_charge_cap <= 0:
            raise ValueError("invalid per-profile charge cap")

        rows: List[Dict[str, Any]] = []
        for raw_handle in handles:
            handle = str(raw_handle).strip().lstrip("@")
            if not handle:
                self.provider_errors.append({"handle": "unknown", "error": "bad_input"})
                continue
            one_input = dict(base_input)
            one_input["handles"] = [handle]
            try:
                rows.extend(self._request(one_input, paid_item_cap=1, charge_cap_usd=per_call_charge_cap))
            except RuntimeError as exc:
                # One malformed/unreadable profile must never poison the rest of the watchlist.
                self.provider_errors.append(
                    {
                        "handle": handle,
                        "error": "actor_run_failed",
                        "description": str(exc)[:2000],
                    }
                )
        return rows

    def fetch(self, *, max_records: int) -> List[Dict[str, Any]]:
        if not 1 <= int(max_records) <= 100:
            raise ValueError("live Apify max_records must be between 1 and 100")

        actor_input = dict(self.actor_input)
        isolate_profiles = bool(actor_input.pop("isolateProfiles", False))
        output_format = str(actor_input.get("outputFormat") or "posts").lower()

        if isolate_profiles:
            if output_format != "profile":
                raise ValueError("isolateProfiles requires outputFormat=profile")
            payload_rows = self._fetch_isolated_profiles(actor_input)
        else:
            paid_item_cap = int(max_records)
            if output_format == "profile" and self.requested_profile_count:
                paid_item_cap = min(int(max_records), self.requested_profile_count)
            payload_rows = self._request(
                actor_input,
                paid_item_cap=paid_item_cap,
                charge_cap_usd=self.max_total_charge_usd,
            )

        self.raw_items = payload_rows
        if output_format == "profile":
            return self._flatten_profile_rows(self.raw_items, max_records=int(max_records))

        accepted: List[Dict[str, Any]] = []
        for row in self.raw_items:
            if row.get("error"):
                self._record_error(row)
                continue
            self._accept_post(row, accepted)
            if len(accepted) >= int(max_records):
                break
        return accepted
