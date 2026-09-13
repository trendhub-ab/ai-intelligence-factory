import inspect
import os
from unittest.mock import patch

import gemini_provider_resilience as provider


def test_pending_retry_validation_uses_pending_provider_policy():
    assert provider._is_pending_retry_origin("pending_retry_validation") is True


def test_existing_pending_retry_origin_remains_supported():
    assert provider._is_pending_retry_origin("pending_retry") is True


def test_normal_origins_do_not_enter_pending_provider_policy():
    assert provider._is_pending_retry_origin("new") is False
    assert provider._is_pending_retry_origin("article_revalidation") is False
    assert provider._is_pending_retry_origin("product_review") is False


def test_run374_pending_retry_exclusion_parses_exact_models():
    with patch.dict(
        os.environ,
        {"GEMINI_PENDING_RETRY_EXCLUDED_MODELS": "gemini-3.6-flash, gemini-legacy"},
        clear=False,
    ):
        assert provider._pending_retry_excluded_models() == frozenset(
            {"gemini-3.6-flash", "gemini-legacy"}
        )


def test_run374_provider_dispatch_skips_excluded_model_before_any_call():
    source = inspect.getsource(provider.install)
    assert "excluded = _pending_retry_excluded_models() if _is_pending_retry_origin(request_origin)" in source
    assert "if model_name in excluded:" in source
    excluded_pos = source.index("if model_name in excluded:")
    dispatch_pos = source.index("response = pipeline_module._generate_via_chat")
    assert excluded_pos < dispatch_pos


def test_run374_exclusion_is_pending_only_not_global():
    source = inspect.getsource(provider.install)
    assert "if _is_pending_retry_origin(request_origin) else frozenset()" in source
