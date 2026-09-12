from __future__ import annotations

import os

os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "true")

import run362_gemini_request_shape_validation as run362


def test_context_lengths_are_bounded():
    assert len(run362._make_context(3000)) == 3000
    assert len(run362._make_context(18000)) == 18000


def test_status_code_parser_handles_common_provider_codes():
    class E(Exception):
        status_code = 503
    assert run362._status_code(E("service unavailable")) == 503
    assert run362._status_code(RuntimeError("429 RESOURCE_EXHAUSTED")) == 429
