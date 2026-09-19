#!/usr/bin/env python3
"""Exact zero-model repair of two already-published legacy AIIF note articles.

Targets:
- RubyGems incident article: remove unsupported motive/internal-state claims and keep attribution bounded.
- GenAI sophistication article: remove ROI and causal overclaims, using the already-corrected
  Content Intelligence manuscript wording.

Safety:
- hard-bound to two exact note IDs and exact public URLs;
- no Gemini/model calls and no Production pipeline;
- never opens /new and never creates another note;
- does not change eyecatches, tags, magazines, memberships, or any other note;
- accepts only the expected legacy or already-staged corrected surface;
- publishes changes via the observed published-note update route: 公開に進む -> 更新する;
- verifies the live public URL after each update.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run190_note_persistent_cloud as cloud

CONFIRM_TOKEN = "REPAIR_TWO_PUBLIC_LEGACY_ARTICLES"
RESULT_ENV = "PUBLIC_LEGACY_REPAIR_RESULT_FILE"
ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Target:
    key: str
    note_id: str
    old_title: str
    new_title: str
    manuscript_path: Path
    legacy_markers: tuple[str, ...]
    current_markers: tuple[str, ...]

    @property
    def public_url(self) -> str:
        return f"https://note.com/trendhub_biz/n/{self.note_id}"

    @property
    def editor_url(self) -> str:
        return f"https://editor.note.com/notes/{self.note_id}/edit/"

    @property
    def publish_url(self) -> str:
        return f"https://editor.note.com/notes/{self.note_id}/publish/"


TARGETS = (
    Target(
        key="rubygems",
        note_id="nbad7b7a478d3",
        old_title="AIが勝手に他社サーバーを突破した？OpenAIエージェントが起こしたRubyGems騒動から考える権限管理の境界線",
        new_title="AIが勝手に他社サーバーを突破した？OpenAIエージェントが起こしたRubyGems騒動から考える権限管理の境界線。",
        manuscript_path=ROOT / "repairs" / "public_legacy_quality_20260919" / "rubygems.md",
        legacy_markers=(
            "エージェント自身が、自らの行動を明確にハッキングや脆弱性攻撃と認識するような推論状態の下で動いていたことが伺えます。",
            "手段を選ばない問題解決能力",
            "最適解として自律的に編み出してしまうことがあります。",
            "目的達成の過程で自発的に脆弱性悪用へ踏み込んでしまう現実",
        ),
        current_markers=(
            "エージェント内部の認識や意図そのものを証明するものではありません。",
            "なぜその手段が選ばれたのかは分かっていません。",
            "帰属や未確認事項は、研究チームの報告範囲を超えて断定していません。",
        ),
    ),
    Target(
        key="ai_proficiency",
        note_id="n012a6d7edfda",
        old_title="全社にAIを配っても使いこなせない？ 大手企業70万件のログが明かす「熟練度」の壁。",
        new_title="全社にAIを配っても使いこなせない？ 大手企業70万件のログが明かす「熟練度」の壁。",
        manuscript_path=ROOT / "repairs" / "public_legacy_quality_20260919" / "ai_proficiency.md",
        legacy_markers=(
            "期待したROI（投資対効果）や使いこなしのレベルアップが得られない現実",
            "その理由は「ドメイン知識（業務そのものに対する深い理解と経験）」にあります。",
            "AI投資の成果（ROI）を得るのが難しいことは明白です。",
            "一律研修を一度止める",
        ),
        current_markers=(
            "この研究だけでAI投資のROI（投資対効果）への影響までは断定できない。",
            "ただし、この研究だけで因果関係までは断定できません。",
            "この研究だけでROIへの影響や因果関係までは断定できません",
            "一律研修だけに頼らない",
        ),
    ),
)


class PublicLegacyRepairError(RuntimeError):
    pass


def _canon(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _load_manuscript(target: Target) -> str:
    text = target.manuscript_path.read_text(encoding="utf-8").strip()
    if len(text) < 1200:
        raise PublicLegacyRepairError(f"{target.key}: repaired manuscript unexpectedly short")
    for marker in target.current_markers:
        if marker not in text:
            raise PublicLegacyRepairError(f"{target.key}: current marker missing from repair manuscript: {marker}")
    for marker in target.legacy_markers:
        if marker in text:
            raise PublicLegacyRepairError(f"{target.key}: legacy marker survived repair manuscript: {marker}")
    return text


def validate_repair_assets() -> dict[str, Any]:
    if len(TARGETS) != 2:
        raise PublicLegacyRepairError("repair lane must remain hard-bound to exactly two targets")
    ids = [t.note_id for t in TARGETS]
    if len(set(ids)) != 2:
        raise PublicLegacyRepairError("target note IDs must be unique")
    results = {}
    for target in TARGETS:
        manuscript = _load_manuscript(target)
        results[target.key] = {
            "note_id": target.note_id,
            "chars": len(manuscript),
            "legacy_markers_absent": True,
            "current_markers_present": True,
        }
    return results


def _field_text(locator: Any) -> str:
    try:
        tag = str(locator.evaluate("el => el.tagName.toLowerCase()"))
    except Exception:
        tag = ""
    if tag in {"input", "textarea"}:
        try:
            return str(locator.input_value() or "").strip()
        except Exception:
            return ""
    try:
        return str(locator.inner_text() or "").strip()
    except Exception:
        try:
            return str(locator.text_content() or "").strip()
        except Exception:
            return ""


def _unique_button(page: Any, name: str) -> Any:
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*$")
    controls = page.locator("button:visible").filter(has_text=pattern)
    try:
        controls.first.wait_for(state="visible", timeout=10000)
    except Exception as exc:
        raise PublicLegacyRepairError(f"visible button missing: {name}") from exc
    visible = [_canon(v) for v in page.locator("button:visible").all_text_contents() if _canon(v)]
    if sum(1 for value in visible if value == name) != 1:
        raise PublicLegacyRepairError(f"expected exactly one visible {name} button")
    return controls.first


def _open_exact_editor(context: Any, page: Any, target: Target) -> None:
    page.goto(target.editor_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1300)
    if target.note_id not in str(page.url or "") or "/edit" not in str(page.url or ""):
        if cloud._seed_note_state(context, page):
            page.goto(target.editor_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1300)
    current = str(page.url or "")
    if target.note_id not in current or "/edit" not in current:
        raise PublicLegacyRepairError(f"{target.key}: exact editor route unavailable")


def _body_text(page: Any) -> str:
    try:
        article = page.locator("article").first
        if article.count() and article.is_visible(timeout=3000):
            return str(article.inner_text(timeout=10000) or "")
    except Exception:
        pass
    return str(page.locator("body").inner_text(timeout=10000) or "")


def _public_title_ok(page: Any, expected: str) -> bool:
    expected_canon = _canon(expected)
    values: list[str] = []
    for selector, attr in (
        ('meta[property="og:title"]', "content"),
        ('meta[name="twitter:title"]', "content"),
    ):
        try:
            loc = page.locator(selector).first
            if loc.count():
                values.append(str(loc.get_attribute(attr) or ""))
        except Exception:
            pass
    try:
        values.extend(str(x or "") for x in page.locator("h1").all_inner_texts())
    except Exception:
        pass
    return any(expected_canon and expected_canon in _canon(v) for v in values)


def _public_state(context: Any, target: Target) -> tuple[str, dict[str, Any]]:
    page = context.new_page()
    page.set_default_timeout(30000)
    try:
        page.goto(target.public_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        final = str(page.url or "").split("?", 1)[0].rstrip("/")
        if final != target.public_url.rstrip("/"):
            raise PublicLegacyRepairError(f"{target.key}: public URL drift")
        body = _canon(_body_text(page))
        if not body:
            raise PublicLegacyRepairError(f"{target.key}: public body empty")
        current_count = sum(marker in body for marker in target.current_markers)
        legacy_count = sum(marker in body for marker in target.legacy_markers)
        title_new = _public_title_ok(page, target.new_title)
        title_old = _public_title_ok(page, target.old_title)

        if current_count == len(target.current_markers) and legacy_count == 0 and title_new:
            return "current", {
                "public_url": target.public_url,
                "current_markers": current_count,
                "legacy_markers": legacy_count,
                "title_current": True,
            }
        if legacy_count >= 1 and title_old:
            return "legacy", {
                "public_url": target.public_url,
                "current_markers": current_count,
                "legacy_markers": legacy_count,
                "title_current": title_new,
            }
        raise PublicLegacyRepairError(
            f"{target.key}: public surface is neither recognized legacy nor current "
            f"(current_markers={current_count}, legacy_markers={legacy_count}, title_new={title_new}, title_old={title_old})"
        )
    finally:
        page.close()


def _editor_surface(page: Any, target: Target) -> tuple[Any, Any, str]:
    title_field = base._find_title(page)
    title = _field_text(title_field)
    if title not in {target.old_title, target.new_title}:
        raise PublicLegacyRepairError(f"{target.key}: unexpected editor title: {title!r}")
    body = base._find_body(page, title_field)
    try:
        raw = str(body.inner_text(timeout=7000) or "")
    except Exception as exc:
        raise PublicLegacyRepairError(f"{target.key}: editor body unreadable") from exc
    return title_field, body, _canon(raw)


def _repair_one(context: Any, target: Target) -> dict[str, Any]:
    manuscript = _load_manuscript(target)
    public_before, before_metrics = _public_state(context, target)
    if public_before == "current":
        return {
            "key": target.key,
            "note_id": target.note_id,
            "status": "already_current",
            "public_mutation": False,
            "same_public_url": True,
            "new_note_created": False,
            "zero_gemini_calls": True,
            **before_metrics,
        }

    page = context.new_page()
    page.set_default_timeout(30000)
    try:
        _open_exact_editor(context, page, target)
        title_field, body, editor_text = _editor_surface(page, target)
        legacy_count = sum(marker in editor_text for marker in target.legacy_markers)
        current_count = sum(marker in editor_text for marker in target.current_markers)

        if legacy_count < 1 and current_count != len(target.current_markers):
            raise PublicLegacyRepairError(
                f"{target.key}: editor is neither expected legacy nor staged current"
            )

        if _field_text(title_field) != target.new_title:
            title_field = base._set_title(page, target.new_title)
            if _field_text(title_field) != target.new_title:
                raise PublicLegacyRepairError(f"{target.key}: title update did not persist")

        # Always paste the exact reviewed manuscript; this also normalizes any partial staged state.
        body = base._find_body(page, title_field)
        base._paste_manuscript(page, body, manuscript)
        body = base._find_body(page, title_field)
        base._verify_body_content(body, manuscript)
        page.wait_for_timeout(1200)

        _unique_button(page, "公開に進む").click()
        try:
            page.wait_for_url(f"**/notes/{target.note_id}/publish/**", timeout=15000)
        except Exception as exc:
            raise PublicLegacyRepairError(f"{target.key}: exact publish settings route not reached") from exc
        if target.note_id not in str(page.url or "") or "/publish" not in str(page.url or ""):
            raise PublicLegacyRepairError(f"{target.key}: publish route identity lost")

        page.wait_for_timeout(1000)
        _unique_button(page, "更新する").click()
        page.wait_for_timeout(2200)

        public_after, after_metrics = _public_state(context, target)
        if public_after != "current":
            raise PublicLegacyRepairError(f"{target.key}: public verification did not reach current state")
        return {
            "key": target.key,
            "note_id": target.note_id,
            "status": "updated_and_verified",
            "public_mutation": True,
            "same_public_url": True,
            "new_note_created": False,
            "zero_gemini_calls": True,
            **after_metrics,
        }
    finally:
        page.close()


def run() -> dict[str, Any]:
    if os.environ.get("PUBLIC_LEGACY_REPAIR_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise PublicLegacyRepairError("exact repair confirmation token missing or invalid")
    assets = validate_repair_assets()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PublicLegacyRepairError("Playwright is required") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        try:
            results = [_repair_one(context, target) for target in TARGETS]
        finally:
            context.close()

    if {r["note_id"] for r in results} != {t.note_id for t in TARGETS}:
        raise PublicLegacyRepairError("result target set drift")
    return {
        "status": "completed",
        "targets": results,
        "asset_validation": assets,
        "updated_count": sum(r["status"] == "updated_and_verified" for r in results),
        "already_current_count": sum(r["status"] == "already_current" for r in results),
        "public_release_created": False,
        "new_note_created": False,
        "eyecatch_mutation": False,
        "zero_gemini_calls": True,
    }


def main() -> None:
    result = run()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PUBLIC_LEGACY_REPAIR=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
