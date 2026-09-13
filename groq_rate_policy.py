"""Conservative Groq Free Plan safety policies for AI Intelligence Factory.

Official limits checked 2026-09-12 from Groq rate-limit documentation.
Standalone GPT-OSS 120B: 30 RPM / 1000 RPD / 8000 TPM / 200000 TPD.
Compound / Compound Mini: 30 RPM / 250 RPD / 70000 TPM; no TPD is published.

Factory limits deliberately leave headroom and are not claims about account-specific
remaining allowance. Provider response headers remain the authority for live quota.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RatePolicy:
    name: str
    model: str
    official_rpm: int
    official_rpd: int
    official_tpm: int
    official_tpd: int | None
    safe_rpm: int
    safe_rpd: int
    safe_tpm: int
    safe_tpd: int | None


GPT_OSS_120B = RatePolicy(
    name="gpt_oss_120b",
    model="openai/gpt-oss-120b",
    official_rpm=30,
    official_rpd=1000,
    official_tpm=8000,
    official_tpd=200000,
    safe_rpm=24,
    safe_rpd=900,
    safe_tpm=7000,
    safe_tpd=180000,
)

# Article generation uses Compound Mini because the canonical Production article prompt
# itself is larger than the standalone model's Free Plan TPM envelope. Tool execution is
# disabled by the provider adapter, so the validation remains source-bounded and does not
# create paid/variable external-tool behavior. We retain ~14% TPM and 10% RPD headroom.
COMPOUND_MINI = RatePolicy(
    name="compound_mini_article",
    model="groq/compound-mini",
    official_rpm=30,
    official_rpd=250,
    official_tpm=70000,
    official_tpd=None,
    safe_rpm=24,
    safe_rpd=225,
    safe_tpm=60000,
    safe_tpd=None,
)

POLICIES = {policy.name: policy for policy in (GPT_OSS_120B, COMPOUND_MINI)}
MODEL_TO_POLICY = {policy.model: policy for policy in POLICIES.values()}


def policy_for_name(name: str) -> RatePolicy:
    try:
        return POLICIES[name]
    except KeyError:
        raise ValueError("unknown Groq rate policy") from None


def policy_for_model(model: str) -> RatePolicy:
    try:
        return MODEL_TO_POLICY[model]
    except KeyError:
        raise ValueError("unsupported Groq model") from None


# Backward-compatible standalone constants used by the calibration validation lane.
OFFICIAL_RPM = GPT_OSS_120B.official_rpm
OFFICIAL_RPD = GPT_OSS_120B.official_rpd
OFFICIAL_TPM = GPT_OSS_120B.official_tpm
OFFICIAL_TPD = GPT_OSS_120B.official_tpd
SAFE_RPM = GPT_OSS_120B.safe_rpm
SAFE_RPD = GPT_OSS_120B.safe_rpd
SAFE_TPM = GPT_OSS_120B.safe_tpm
SAFE_TPD = GPT_OSS_120B.safe_tpd

ROLLING_MINUTE_SECONDS = 60
ROLLING_DAY_SECONDS = 86400
MAX_RESERVED_TOKENS_PER_REQUEST = max(policy.safe_tpm for policy in POLICIES.values())
