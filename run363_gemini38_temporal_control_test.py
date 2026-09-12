from run363_gemini38_temporal_control import classify, MODEL


def _r(code):
    return {"http_status": code}


def test_model_is_gemini38_only():
    assert MODEL == "gemini-3.8-flash"


def test_classification_request_shape():
    assert classify(_r(200), _r(503), _r(200)) == "request_shape_strongly_implicated"


def test_classification_provider_demand():
    assert classify(_r(503), _r(503), _r(503)) == "provider_high_demand_confounded"


def test_classification_all_success():
    assert classify(_r(200), _r(200), _r(200)) == "no_503_reproduction_on_gemini38"
