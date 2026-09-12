import gemini_provider_resilience as provider


def test_pending_retry_validation_uses_pending_provider_policy():
    assert provider._is_pending_retry_origin("pending_retry_validation") is True


def test_existing_pending_retry_origin_remains_supported():
    assert provider._is_pending_retry_origin("pending_retry") is True


def test_normal_origins_do_not_enter_pending_provider_policy():
    assert provider._is_pending_retry_origin("new") is False
    assert provider._is_pending_retry_origin("article_revalidation") is False
    assert provider._is_pending_retry_origin("product_review") is False
