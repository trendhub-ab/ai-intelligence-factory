#!/usr/bin/env python3
"""One-off, exact-target repair for the existing SGPS private note draft.

Safety contract:
- ZERO Gemini/model calls.
- Exact Content Intelligence sync id and note Ready queue row are hard-bound.
- The existing note /notes/<id>/edit route is discovered from the persistent Chrome history.
- No /new route is opened and no second draft may be created.
- Title/body are replaced only after the repaired manuscript passes the current deterministic
  Production Fact / Editorial / Publication / Human Appeal stack.
- Save must resolve to the exact same edit route that was opened.
- No public-release action exists in this module.
- The existing eyecatch is not modified by this body/title repair; its persistence is verified.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as run190
import run291_note_private_draft_audit as audit_base
import run417_note_body_verification as run417

SYNC_ID = "3e0479ffdca981a1b4b6d827f2656d49"
DESTINATION_PAGE_ID = "3e0479ff-dca9-81ec-9b8a-e79ca7fd2ebb"
CONFIRM_TOKEN = "REPAIR_SGPS_EXISTING_DRAFT"
OLD_TITLE = "1台のGPUで実機が動く。ロボットAIの学習コストを激変させる「SGPS」の衝撃。"
NEW_TITLE = "GPU 1台でロボット方策を学習。実機へゼロショット転送する「SGPS」は何を変えるのか？"
MANUSCRIPT_PATH = Path(__file__).resolve().parent / "repairs" / "sgps_publishable_20260919.md"

# Source-native facts used by the deterministic publication gates. This deliberately
# includes the method/deployment/limitations boundaries that the historical article blurred.
SOURCE_CONTEXT = """
Learning visual policies for locomotion and manipulation can incur substantial computation
and GPU memory costs. First-order policy gradients (FoPG) reduce training cost through
differentiable simulation, but local optimization can converge to unintended contact patterns.
SGPS couples recurring action-target refinement by sampling-based model-predictive control
with first-order policy optimization. Behavior cloning initializes the policy from sampled
actions; training alternates sampling-based refinement with short-horizon FoPG updates under
perturbed initial states and randomized dynamics.

For visual policy training, decoupled FoPG excludes rendering from the computation graph.
Depth is rendered from detached simulator states while physics remains differentiable,
training the visual encoder and actor without renderer derivatives. Visual specialists are
trained directly without a privileged state-policy teacher.

On a single GPU, SGPS learns policies on simulated Unitree Go2 and G1 robots for locomotion,
obstacle traversal, crate pushing, and bimanual carrying. Experiments show that refinement
improves policy learning beyond initialization and tracking alone. Sampling targets need not
follow a return gradient, and acceptance on the nominal model does not guarantee an increase
in expected return after policy fitting.

For hardware deployment, Go2 specialists are distilled into a unified visual policy.
The unified policy transfers zero-shot to a real Unitree Go2 EDU without hardware fine-tuning,
using onboard depth and proprioception. No online MPC or reference inputs are used at deployment.
The control loop runs at 50 Hz and the recurrent depth encoder at 10 Hz. The deployed policy
autonomously trots, crawls, clears hurdles, and switches between these behaviors.

SGPS relies on differentiable dynamics, successful sampled references, and task-specific
objectives. Humanoid tasks simplify object motion and hand-object interactions, complex
manipulation remains unexplored, and humanoid hardware deployment is future work.
""".strip()

SOURCE_INFO = {
    "sufficient": True,
    "deep_source_required": True,
    "deep_source_scanned": True,
    "decision_scope_safe": True,
}
EVIDENCE_METADATA = {
    "evidence_strength": "PRIMARY_SOURCE",
    "coverage": {
        "hardware": "FOUND",
        "runtime": "FOUND",
        "benchmark": "FOUND",
        "code_availability": "UNKNOWN",
    },
}


class SGPSRepairError(RuntimeError):
    pass


def load_manuscript() -> str:
    text = MANUSCRIPT_PATH.read_text(encoding="utf-8").strip()
    if len(text) < 1200:
        raise SGPSRepairError("SGPS repaired manuscript is unexpectedly short")
    return text


def build_parsed(manuscript: str) -> dict[str, Any]:
    return {
        "note_draft": manuscript,
        "title_text": NEW_TITLE,
        "decision_text": "TRY",
        "score": 76,
        "decision_reason_text": (
            "単一GPUでのシミュレーション学習と、蒸留した統合方策の実機Go2への"
            "ゼロショット転送が一次論文で示されており、微分可能シミュレーション基盤を"
            "持つチームには限定PoCで比較する価値がある。"
        ),
        "action_text": (
            "既存の微分可能シミュレータ上で代表タスクを1つ選び、SGPS型refinementの"
            "有無を同条件で比較し、学習時間・GPUメモリ・接触挙動・実機転送工数を計測する。"
        ),
        "source_summary_text": (
            "SGPSはサンプリングベースMPCによる行動ターゲット改善とdecoupled FoPGを"
            "反復し、視覚方策学習を行う。単一GPUでシミュレーション学習し、蒸留した"
            "統合方策を実機Go2へゼロショット転送した。"
        ),
        "alternative_comparison_text": "",
    }


def validate_repaired_manuscript(manuscript: str | None = None) -> dict[str, Any]:
    """Run the current deterministic Production publication gates, with zero provider calls."""
    import pipeline
    import runtime_layers

    # Installing current layers changes only local deterministic gate surfaces here.
    # No generation/provider method is invoked.
    runtime_layers.install_runtime_layers(pipeline)
    body = manuscript if manuscript is not None else load_manuscript()
    parsed = build_parsed(body)

    fact_ok, fact_failures = pipeline.validate_fact_gate(
        parsed,
        "sgps-existing-draft-repair",
        source_context=SOURCE_CONTEXT,
        source="ArXiv",
        evidence_metadata=EVIDENCE_METADATA,
        source_info=SOURCE_INFO,
        freshness={"status": "CURRENT"},
        output_truncated=False,
    )
    editorial_ok, editorial_warnings = pipeline.validate_editorial_gate(
        parsed, "sgps-existing-draft-repair"
    )
    publication_state, publication_issues = pipeline.validate_publication_readiness_gate(
        parsed, SOURCE_CONTEXT, SOURCE_INFO
    )
    human_state, human_issues = pipeline.validate_human_appeal_gate(parsed, [])

    result = {
        "fact_ok": bool(fact_ok),
        "fact_failures": list(fact_failures or []),
        "editorial_ok": bool(editorial_ok),
        "editorial_warnings": list(editorial_warnings or []),
        "publication_state": publication_state,
        "publication_issues": list(publication_issues or []),
        "human_state": human_state,
        "human_issues": list(human_issues or []),
    }
    if not fact_ok:
        raise SGPSRepairError("Fact Gate failed: " + "; ".join(result["fact_failures"]))
    if not editorial_ok:
        raise SGPSRepairError("Editorial Gate failed: " + "; ".join(result["editorial_warnings"]))
    if publication_state != "PASS":
        raise SGPSRepairError("Publication Gate failed: " + "; ".join(result["publication_issues"]))
    if human_state != "ACCEPTABLE":
        raise SGPSRepairError("Human/Reader Gate failed: " + "; ".join(result["human_issues"]))
    return result


def _destination_preflight() -> dict[str, Any]:
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": SYNC_ID}}},
    )
    exact = [
        page for page in pages
        if str(page.get("id") or "") == DESTINATION_PAGE_ID
        and re.sub(r"[^0-9a-fA-F]", "", ready_sync._text((page.get("properties") or {}).get("同期ID"))).lower() == SYNC_ID
    ]
    if len(exact) != 1:
        raise SGPSRepairError("Exact SGPS note queue row was not found")
    props = exact[0].get("properties") or {}
    posting = ready_sync._select(props.get("投稿状態"))
    quality = ready_sync._select(props.get("品質状態"))
    if posting != "投稿準備中":
        raise SGPSRepairError(f"SGPS queue row is not 投稿準備中: {posting!r}")
    # This target was intentionally revoked by the new publication-policy fingerprint.
    # The repair lane must not silently promote it back to Ready.
    if quality != "Ready取消":
        raise SGPSRepairError(f"SGPS queue quality state changed unexpectedly: {quality!r}")
    return {"posting_state": posting, "quality_state": quality}


def _route_key(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return f"{parsed.scheme.lower()}://{parsed.hostname.lower() if parsed.hostname else ''}{parsed.path.rstrip('/')}"


def _same_edit_route(left: str, right: str) -> bool:
    if not audit_base._is_note_edit_url(left) or not audit_base._is_note_edit_url(right):
        return False
    return _route_key(left) == _route_key(right)


def _title_value(page: Any) -> str:
    return audit_base._title_value(page)


def _find_exact_existing_draft(page: Any, profile_dir: Path) -> tuple[str, int]:
    candidates = audit_base._recent_private_edit_urls(profile_dir)
    if not candidates:
        raise SGPSRepairError("No existing private note edit route is present in Chrome history")
    matched: list[tuple[str, int]] = []
    seeded = False
    for rank, candidate in enumerate(candidates, start=1):
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if note_base._looks_logged_out(page) and not seeded:
                seeded = bool(run190._seed_note_state(page.context, page))
                if seeded:
                    page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(900)
            if note_base._looks_logged_out(page):
                continue
            if not audit_base._is_note_edit_url(str(page.url or "")):
                continue
            title = _title_value(page)
            if title in {OLD_TITLE, NEW_TITLE}:
                matched.append((str(page.url), rank))
        except Exception:
            continue
    # Different URL variants for the same note collapse to the same route key.
    unique: dict[str, tuple[str, int]] = {}
    for url, rank in matched:
        unique.setdefault(_route_key(url), (url, rank))
    if len(unique) != 1:
        raise SGPSRepairError(f"Expected exactly one existing SGPS private draft, found {len(unique)}")
    return next(iter(unique.values()))


def _browser_repair(manuscript: str) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SGPSRepairError("Playwright is required for SGPS draft repair") from exc

    run417.install(note_base)
    profile = run190._profile_dir()
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            existing_url, history_rank = _find_exact_existing_draft(page, profile)
            page.goto(existing_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if note_base._looks_logged_out(page):
                if not run190._seed_note_state(context, page):
                    raise SGPSRepairError("note authentication could not be restored")
                page.goto(existing_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)

            before_url = str(page.url or "")
            if not _same_edit_route(existing_url, before_url):
                raise SGPSRepairError("Existing SGPS draft route changed before mutation")
            before_title = _title_value(page)
            if before_title not in {OLD_TITLE, NEW_TITLE}:
                raise SGPSRepairError("Matched draft title changed before mutation")

            title_field = note_base._set_title(page, NEW_TITLE)
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, manuscript)

            saved_url = note_base._save_draft_and_verify(
                page, NEW_TITLE, manuscript, image_required=False
            )
            if not _same_edit_route(existing_url, saved_url):
                raise SGPSRepairError("Save escaped the existing SGPS draft route; refusing duplicate draft")

            title_field = note_base._find_title(page)
            metrics = eyecatch.collect_eyecatch_metrics(page, title_locator=title_field)
            if not eyecatch.eyecatch_persistence_confirmed(metrics):
                raise SGPSRepairError("Existing eyecatch persistence could not be confirmed after body repair")

            return {
                "status": "existing_draft_repaired",
                "same_edit_route": True,
                "title_match": _title_value(page) == NEW_TITLE,
                "body_verified": True,
                "eyecatch_preserved": True,
                "history_rank": history_rank,
                "editor_route_hash": hashlib.sha256(_route_key(existing_url).encode("utf-8")).hexdigest()[:12],
                "zero_gemini_calls": True,
                "new_draft_created": False,
                "public_release": False,
            }
        finally:
            context.close()


def run(*, confirm: str, prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise SGPSRepairError(f"Confirmation must equal {CONFIRM_TOKEN}")
    manuscript = load_manuscript()
    gate_result = validate_repaired_manuscript(manuscript)
    state = _destination_preflight()
    result: dict[str, Any] = {
        "status": "repair_ready" if prepare_only else "existing_draft_repaired",
        "sync_id": SYNC_ID,
        "zero_gemini_calls": True,
        "new_draft_created": False,
        "public_release": False,
        "publication_gates_passed": True,
        "quality_state_preserved": state["quality_state"],
        "posting_state_preserved": state["posting_state"],
        "gate_summary": {
            "fact_ok": gate_result["fact_ok"],
            "editorial_ok": gate_result["editorial_ok"],
            "publication_state": gate_result["publication_state"],
            "human_state": gate_result["human_state"],
        },
    }
    if prepare_only:
        return result
    result.update(_browser_repair(manuscript))
    return result


def main() -> None:
    result = run(
        confirm=os.environ.get("SGPS_DRAFT_REPAIR_CONFIRM", ""),
        prepare_only=os.environ.get("SGPS_DRAFT_REPAIR_PREPARE_ONLY", "").lower() in {"1", "true", "yes", "on"},
    )
    # Never expose the private edit URL or unpublished article body in CI output.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
