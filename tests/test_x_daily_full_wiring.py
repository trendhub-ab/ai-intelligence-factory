from pathlib import Path


def test_production_entrypoint_installs_x_after_business_source_precision():
    text = Path("production_pipeline.py").read_text(encoding="utf-8")
    import_line = "from run367_x_daily_discovery import install as install_run367_x_daily_discovery"
    run269 = "install_run269_business_source_precision(pipeline)"
    run367 = "install_run367_x_daily_discovery(pipeline)"

    assert import_line in text
    assert run269 in text
    assert run367 in text
    assert text.index(run269) < text.index(run367)


def test_one_shot_exposes_apify_only_through_full_gated_production_step():
    text = Path(".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")

    assert "AIIF_RUN_MODE: ${{ inputs.mode }}" in text
    assert "AIIF_X_DISCOVERY_ENABLED: ${{ inputs.mode == 'full' }}" in text
    assert "APIFY_TOKEN: ${{ inputs.mode == 'full' && secrets.APIFY_TOKEN || '' }}" in text
    assert 'APIFY_ACTOR_ID: "simple.actor~x-profile-posts"' in text
    assert 'APIFY_MAX_CHARGE_USD: "0.05"' in text
    assert 'X_DISCOVERY_MAX_RECORDS: "100"' in text
    assert "run: python production_pipeline.py" in text


def test_pending_retry_step_does_not_receive_apify_credentials():
    text = Path(".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    pending = text.split("- name: Pending Retry fast laneを1回だけ実行", 1)[1]
    pending = pending.split("- name: Portfolio-aware Product Review", 1)[0]

    assert "APIFY_TOKEN" not in pending
    assert "AIIF_X_DISCOVERY_ENABLED" not in pending


def test_scheduled_daily_remains_hard_paused_with_dormant_x_contract():
    text = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

    assert "name: Daily Intelligence & Content Pipeline [PAUSED]" in text
    assert "if: ${{ false }}" in text
    assert "schedule:" not in text
    assert 'AIIF_X_DISCOVERY_ENABLED: "true"' in text
    assert 'APIFY_MAX_CHARGE_USD: "0.05"' in text
    assert 'X_DISCOVERY_MAX_RECORDS: "100"' in text
