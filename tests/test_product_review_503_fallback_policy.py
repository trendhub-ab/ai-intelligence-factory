from __future__ import annotations

import inventory_bootstrap


def test_product_only_environment_sets_full_product_review_model_pool():
    env = inventory_bootstrap.product_only_environment(2, 3)

    assert env["GEMINI_DEEP_DIVE_MODEL_CANDIDATES"] == (
        "gemini-3.6-flash,gemini-3.5-flash,gemini-3.7-flash,gemini-3.8-flash"
    )
    assert env["PRODUCT_REVIEW_MAX_PER_RUN"] == "2"
    assert env["GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET"] == "3"
