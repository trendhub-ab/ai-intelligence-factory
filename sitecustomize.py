import os

# Run146 validation-only guard: when the existing read-only Real Article Regression
# is explicitly active, lock Deep Dive generation to Gemini 3.6 Flash so provider
# fallback cannot contaminate A/B quality comparisons. Normal production and unit
# tests are unchanged because REGEN_TEST_MODE is not set there.
if os.environ.get("REGEN_TEST_MODE", "false").lower() in {"1", "true", "yes", "on"}:
    os.environ["GEMINI_DEEP_DIVE_MODEL_CANDIDATES"] = "gemini-3.6-flash"
