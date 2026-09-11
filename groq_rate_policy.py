"""Conservative Groq Free Plan safety policy for AI Intelligence Factory.

Official limits for openai/gpt-oss-120b checked 2026-09-12:
30 RPM / 1000 RPD / 8000 TPM / 200000 TPD.

These are local safety limits, deliberately below the provider limits. They are not
claims about account-specific remaining allowance. Provider response headers remain
the final authority for current remaining quota.
"""

# Groq Free Plan published limits for openai/gpt-oss-120b.
OFFICIAL_RPM = 30
OFFICIAL_RPD = 1000
OFFICIAL_TPM = 8000
OFFICIAL_TPD = 200000

# Factory safety envelope. Keep headroom for provider/account variance and concurrent
# activity outside this validation lane while allowing development to proceed normally.
SAFE_RPM = 24
SAFE_RPD = 900
SAFE_TPM = 7000
SAFE_TPD = 180000

ROLLING_MINUTE_SECONDS = 60
ROLLING_DAY_SECONDS = 86400
MAX_RESERVED_TOKENS_PER_REQUEST = SAFE_TPM
