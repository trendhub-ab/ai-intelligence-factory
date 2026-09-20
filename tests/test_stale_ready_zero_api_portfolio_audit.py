import stale_ready_zero_api_portfolio_audit as audit


def test_classification_is_deterministic_and_fail_closed():
    assert audit.classify_state({"decision_score":90,"article_value":85},recoverable=True)[0]=="keep_fast_path"
    assert audit.classify_state({"decision_score":70,"article_value":65},recoverable=True)[0]=="reader_reedit_candidate"
    assert audit.classify_state({"decision_score":50,"article_value":30},recoverable=True)[0]=="deep_revalidation_candidate"
    assert audit.classify_state({"decision_score":20,"article_value":20},recoverable=True)[0]=="retire_candidate"
    assert audit.classify_state({"decision_score":90,"article_value":None},recoverable=True)[0]=="manual_unknown"
    assert audit.classify_state({"decision_score":90,"article_value":90},recoverable=False)[0]=="retire_candidate"


def test_protected_states_win_before_value_scoring():
    state={"decision_score":0,"article_value":0}
    assert audit.classify_state(state,recoverable=False,current=True)[0]=="protected_current"
    assert audit.classify_state(state,recoverable=False,published=True)[0]=="protected_published"


def test_module_contract_is_zero_provider_and_read_only():
    text=open("stale_ready_zero_api_portfolio_audit.py",encoding="utf-8").read()
    assert "initialize_runtime(" not in text
    assert "generate_intelligence_report(" not in text
    assert 'model_calls":0' in text
    assert 'writes":0' in text
    assert "PATCH" not in text and "POST" not in text
