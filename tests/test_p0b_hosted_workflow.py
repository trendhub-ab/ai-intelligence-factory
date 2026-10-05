from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-create-draft.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_production_note_workflow_has_no_self_hosted_or_gce_runtime():
    text = _workflow_text()
    banned = (
        "self-hosted",
        "aiif-note-cloud",
        "gcloud compute instances start",
        "gcloud compute instances stop",
        "GCP_NOTE_VM_NAME",
        "GCP_NOTE_VM_ZONE",
        "NOTE_DELIVERY_LEDGER_PATH",
        "~/.aiif-note",
        "xvfb-run",
        "run194_note_persistent_cloud.py",
    )
    for token in banned:
        assert token not in text


def test_production_note_workflow_runs_delivery_on_github_hosted_runner():
    text = _workflow_text()
    assert "runs-on: ubuntu-latest" in text
    assert "id-token: write" in text
    assert "google-github-actions/auth@v3" in text
    assert "NOTE_DELIVERY_LEDGER_BACKEND: 'gcs'" in text
    assert "NOTE_DELIVERY_LEDGER_BUCKET:" in text
    assert "GCP_NOTE_LEDGER_BUCKET" in text


def test_gcp_auth_precedes_durable_ledger_preflight():
    text = _workflow_text()
    auth = text.index("google-github-actions/auth@v3")
    ledger = text.index("Read durable ledger authority before browser setup")
    assert auth < ledger


def test_hosted_browser_is_installed_without_persistent_profile_assumptions():
    text = _workflow_text()
    assert "pip install requests playwright pytest google-cloud-storage" in text
    assert "python -m playwright install --with-deps chromium" in text
    assert "NOTE_CHROME_HEADLESS: 'true'" in text
    assert "NOTE_STORAGE_STATE_B64:" in text
    assert "python run194_note_hosted.py" in text


def test_workflow_preserves_private_only_zero_model_result_contract():
    text = _workflow_text()
    assert "zero Gemini calls" in text
    assert "automatic publication" in text
    assert "queue_confirmed" in text
    assert "creation_unknown" in text
    assert "manual_reconciliation_required" in text
