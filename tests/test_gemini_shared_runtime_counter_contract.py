"""Provider-free contract: every Gemini caller uses the SAME runtime-state ledger."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BRANCH = "runtime-state"
COUNTER_PATH = ".runtime/gemini_daily_usage.json"
REQUIRED = {
    "article-revalidation-apply.yml", "daily-one-shot.yml",
    "inventory-bootstrap.yml", "issue668-stage2-live-rerun.yml",
    "issue683-stage3-live-batch.yml", "issue698-scheduled-rereview.yml",
    "p5-creative-ablation-manual.yml", "ready-asset-recovery-once.yml",
    "ready-draft-regenerate-once.yml", "ready-eyecatch-finalize-once.yml",
    "regression-test.yml",
}

def active(text: str) -> bool:
    return bool(re.search(r"(?m)^\s*GEMINI_PERSISTENT_DAILY_COUNTER:\s*['\"]?true['\"]?\s*$", text, re.I))

def branches(text: str) -> list[str]:
    return re.findall(r"(?m)^\s*GEMINI_COUNTER_BRANCH:\s*['\"]?([A-Za-z0-9_/-]+)", text)

def test_every_gemini_persistent_caller_uses_single_runtime_branch():
    found = set()
    for p in WORKFLOWS.glob("*.yml"):
        src = p.read_text(encoding="utf-8")
        selected = branches(src)
        if active(src):
            found.add(p.name)
            assert selected, f"{p.name}: implicit counter branch"
        if selected:
            assert active(src), f"{p.name}: branch without persistent gate"
            assert set(selected) == {BRANCH}, f"{p.name}: inconsistent branch {selected}"
            assert "group: ai-intelligence-gemini-budget" in src
            explicit_paths = re.findall(
                r"(?m)^\s*GEMINI_PERSISTENT_COUNTER_PATH:\s*['\"]?([^'\"\n]+)", src
            )
            assert all(s.strip() == COUNTER_PATH for s in explicit_paths)
    assert found == REQUIRED, f"caller drift: missing={REQUIRED-found}, extra={found-REQUIRED}"

def test_daily_and_p5_share_auth_and_quota_counter_identity():
    daily = (WORKFLOWS / "daily-one-shot.yml").read_text(encoding="utf-8")
    p5 = (WORKFLOWS / "p5-creative-ablation-manual.yml").read_text(encoding="utf-8")
    assert set(branches(daily)) == {BRANCH}
    assert set(branches(p5)) == {BRANCH}
    for src in (daily, p5):
        assert "GH_PAT:" in src
        assert "GEMINI_QUOTA_FALLBACK_ID:" in src

def test_issue668_wont_auto_send_model_api_after_merge():
    src = (WORKFLOWS / "issue668-stage2-live-rerun.yml").read_text(encoding="utf-8")
    assert "  workflow_dispatch:" in src
    for trigger in ("  push:", "  pull_request:", "  schedule:", "  workflow_run:"):
        assert trigger not in src
    assert "if: github.actor == 'trendhub-ab'" in src

def test_native_counter_keeps_github_atomic_sha_and_preflight():
    src = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    assert 'payload["sha"] = sha' in src
    assert 'payload["branch"] = self.branch' in src
    assert "PERSISTENT_GEMINI_COUNTER.reserve(kind, reserve=reserve, model_name=model_name)" in src
