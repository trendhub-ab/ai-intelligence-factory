from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "editorial-engine-v3-manual-c-only.yml"
V3_PIN = "524ef9853478be752b4b0aecea225dff6dff47c1"
BASELINE_RUN = "39020858078"


def _workflow() -> str:
    assert WORKFLOW.is_file(), "V3 manual dispatcher must be a separate default-branch workflow"
    return WORKFLOW.read_text(encoding="utf-8")


def test_v3_dispatch_requires_exact_confirmation_and_one_attempt() -> None:
    text = _workflow()
    events = text.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
    assert "workflow_dispatch:" in events
    assert "confirm:" in events
    assert "required: true" in events
    assert "RUN_V3_C_ONLY" in events
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "inputs.confirm == 'RUN_V3_C_ONLY'" in text
    assert "github.run_attempt == 1" in text
    for automatic_event in (
        "push:", "pull_request:", "schedule:", "workflow_run:",
        "repository_dispatch:", "issue_comment:", "pull_request_target:",
    ):
        assert automatic_event not in events


def test_v3_dispatch_uses_only_immutable_reviewed_code_and_checkpoint() -> None:
    text = _workflow()
    assert f"ref: {V3_PIN}" in text
    assert f"run-id: {BASELINE_RUN}" in text
    assert "name: editorial-engine-v3-phase0-checkpoint" in text
    assert "uses: actions/download-artifact@v4" in text
    assert "github-token: ${{ github.token }}" in text
    assert "persist-credentials: false" in text
    assert "ref: feature/editorial-engine-v3-phase0" not in text
    assert "ref: main" not in text


def test_v3_dispatch_is_single_model_and_c_only() -> None:
    text = _workflow()
    assert "AIIF_PHASE0_MODELS: 'gemini-3.8-flash'" in text
    assert "AIIF_PHASE0_REGENERATE_C_ONLY: 'true'" in text
    assert "AIIF_PHASE0_CASE_COOLDOWN_SECONDS: '45'" in text
    assert "AIIF_PHASE0_OUTPUT_DIR: phase0_artifacts" in text
    assert "gemini-3.6" not in text
    assert "gemini-2." not in text
    assert "model_candidates:" not in text
    assert "regenerate_c_only:" not in text
    assert "python -m experiments.editorial_engine_v3_phase0.live" in text


def test_v3_dispatch_enforces_jst_time_readonly_budget_and_no_prod_secrets() -> None:
    text = _workflow()
    assert 'ZoneInfo("Asia/Tokyo")' in text
    assert "hour >= 17" in text
    assert "group: ai-intelligence-gemini-budget" in text
    assert "cancel-in-progress: false" in text
    assert "permissions:\n  contents: read\n  actions: read" in text
    assert "contents: write" not in text
    assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in text
    for forbidden in (
        "GH_PAT", "NOTION_API_KEY", "NOTION_DATABASE_ID",
        "TELEGRAM_BOT_TOKEN", "APIFY_TOKEN", "note.com",
        "production_pipeline.py", "run202_chatops_control.py",
        "pipeline.py", "pull_request:", "schedule:",
    ):
        assert forbidden not in text


def test_v3_dispatch_runs_contract_tests_and_structural_proof() -> None:
    text = _workflow()
    for name in (
        "tests/test_editorial_engine_v3_phase0.py",
        "tests/test_editorial_engine_v3_phase0_live.py",
        "tests/test_editorial_engine_v3_phase0_quality_contract.py",
        "tests/test_editorial_engine_v3_phase0_proof.py",
    ):
        assert name in text
    assert "proof snapshot-baseline --output-dir phase0_artifacts" in text
    assert "proof verify --output-dir phase0_artifacts" in text
    assert "if: ${{ always() }}" in text
    assert "uses: actions/upload-artifact@v7" in text
    assert "retention-days: 7" in text
    assert "if-no-files-found: warn" in text
