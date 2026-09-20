from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"stale_ready_top_fast_path_preflight.py").read_text(encoding="utf-8")
WF=(ROOT/".github/workflows/stale-ready-retirement-audit.yml").read_text(encoding="utf-8")

def test_preflight_is_zero_provider_and_read_only():
    assert '"model_calls":0' in SRC
    assert '"writes":0' in SRC
    assert "initialize_runtime" not in SRC
    assert "generate_intelligence_report" not in SRC
    assert "requests.patch" not in SRC.lower()
    assert '"safe_to_restamp_without_validation":False' in SRC

def test_preflight_requires_current_gates_and_is_wired_to_manual_audit():
    assert '"requires_current_gates":True' in SRC
    assert '"requires_model_validation":True' in SRC
    assert "python stale_ready_top_fast_path_preflight.py" in WF
    assert "article_audit/stale_ready_top_fast_path_preflight.json" in WF
