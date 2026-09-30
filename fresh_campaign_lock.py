"""Fail-closed, measurement-only lock for the new source-stratified Fresh campaign.

This module is opt-in. Normal Daily, generic Local Skills canary, and the
zero-Gemini acquisition trial are deliberately outside this campaign.
No API, network, Notion, Writer, Canonicalizer, or Gate implementation lives here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

BASE_MAIN = "f149bda8c176dd0a9997d89396b0acee0f0d1611"
CAMPAIGN = "source-stratified-fresh-v439-new-holdouts-stage3-v1"
MAX_GEMINI_SENDS = 6                 # All failed attempts and fallbacks count.
MAX_DEEP_DIVE_SENDS = 1              # Including failed sends and fallback sends.
EXPECTED_SCREENING = "gemini-3.5-flash-lite,gemini-3.1-flash-lite"
EXPECTED_DEEP_DIVE = "gemini-3.7-flash,gemini-3.8-flash,gemini-3.6-flash,gemini-3.5-flash"
SOURCES = frozenset({"GitHub", "HackerNews", "ArXiv", "OfficialVendor"})
AUDIT_RELATIVE = "article_audit/fresh_campaign_budget.json"

# Exact Git blob fingerprints captured from main f149bda8 BEFORE this PR.
# Together with the all-Python-file diff rule, these freeze the entire current
# validated Python runtime, not merely the Writer/Canonicalizer version strings.
FROZEN_BLOBS = {
    "pipeline.py": "109ac619011050706292eea4d94c9883e7bcd18c",
    "runtime_layers.py": "acac2f3b96319c52943ff6623fdc3b7448582ff1",
    "local_skills_daily_canary.py": "bdec6e15c61536f92af13f1a8cd5ee1c5fcd3d95",
    "local_skills/writer.py": "884c550125ff563b2d8bcf20132f3373d332f28d",
    "local_skills/publication_canonicalizer.py": "93a62ef2311d43dc1cb84fa5affe9d798a133021",
    "local_skills/production_canary.py": "c0fb2f29210031920fd1ba2128aed0ab784c9f60",
    "local_skills/evidence_boundary.py": "baea845264f97d23b7f30673d2eac573d932c940",
    "gemini_provider_resilience.py": "832214b52e62162599eca6eac6f5e73e16b63a5e",
    "gemini_transient_recovery.py": "d02f9d14ae199420f710a2be894bb29803aa14b2",
    "gemini_timeout_rpd_fail_closed.py": "dd50fe206f88b1730bdb13767dc2f1584df5449d",
    "run260_gemini_model_routing.py": "2584fb342b8c7d6ed8839063ae3a9d82e331eea9",
    "run203_runtime_state_channel.py": "a50d8fda6953eb46dbe35d6c826eaab27086064f",
    "run268_business_source_strategy.py": "d8563ea107231b5ed708466824054aac887b2845",
    "run269_business_source_precision.py": "aa8df7c9f2bb6dfcd6b97158cc0c06b04881e22a",
    "run283_numeric_evidence_equivalence.py": "4c183909677446ddbc71d09c3d444a0ed364dec0",
    "run284_reader_recovery_precision.py": "c8fc63d8cb58f3ff3a566d72c5596d4aced9c1c1",
    "run287_publication_date_provenance.py": "e5f35633d4a55d5cb4d71a93d316160799e67485",
    "reader_quality_precision.py": "97f4d028d184d930fa46b8d260009d75e95034d3",
    "source_normalization.py": "0075ae08d1044fa38a6da234b7adf872cf71a554",
    "screening_protocol.py": "068dd235c221cc14ad1e1d35e579c456ab5c6c89",
    "deep_dive_portfolio.py": "27e4dd67b9eeba405b03adde200fddfb98e2dd42",
    "fresh_candidate_supply_experiment.py": "9713d687b7be8e88cefaed8d051eb22a9f8762bc",
}
# New entrypoint SHA is established by the FIRST stage-3 commit. Updating
# production_pipeline.py again requires a newly registered protocol.
LOCKED_ENTRYPOINT_BLOB = "dfe302e4f0dcf35049a3f417a76ef77ff6da5e7e"


class FreshCampaignAbort(BaseException):
    """Never permit broad provider 'except Exception' fallbacks after hard stop."""


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def verify_checkout(root: Path) -> None:
    for relative, expected in {
        **FROZEN_BLOBS, "production_pipeline.py": LOCKED_ENTRYPOINT_BLOB
    }.items():
        path = root / relative
        if not path.is_file() or git_blob_sha(path) != expected:
            raise RuntimeError("Frozen Fresh fingerprint mismatch: " + relative)
    # All other runtime Python files, including quality wrappers NOT enumerated
    # above, must be untouched since the reviewed source baseline.
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", BASE_MAIN, "HEAD", "--", "*.py"],
            cwd=root, check=True, capture_output=True, text=True, timeout=15,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Frozen Fresh requires a complete, verifiable Git baseline") from exc
    allowed = {"production_pipeline.py", "fresh_campaign_lock.py"}
    illegal = [name for name in changed if name not in allowed and not name.startswith("tests/")]
    if illegal:
        raise RuntimeError("Post-baseline Python changes require new Fresh registration: " + ",".join(illegal))


def verify_environment(env: dict[str, str]) -> str:
    source = env.get("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "")
    if source not in SOURCES:
        raise RuntimeError("Locked Fresh requires exactly one valid source")
    required = {
        "AIIF_FRESH_CAMPAIGN_LOCK": "true",
        "AIIF_RUN_MODE": "local_skills_canary_validation",
        "AIIF_X_DISCOVERY_ENABLED": "false",
        "AIIF_GEMINI_TEMP_EXCLUDED_MODELS": "",
        "FRESH_SUPPLY_TRIAL_PROTOCOL": "",
        "GEMINI_SCREENING_MODEL_CANDIDATES": EXPECTED_SCREENING,
        "GEMINI_DEEP_DIVE_MODEL_CANDIDATES": EXPECTED_DEEP_DIVE,
        "MAX_SCREENING_CANDIDATES": "200",
        "GITHUB_FETCH_LIMIT": "50",
        "HN_FETCH_LIMIT": "50",
        "ARXIV_FETCH_LIMIT": "50",
        "OFFICIAL_VENDOR_FETCH_LIMIT": "50",
        "GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET": "1",
        "MAX_QUALITY_RETRIES": "0",
    }
    # MAX_QUALITY_RETRIES may be the Production default before the canary
    # overrides it; it is enforced inside the canary immediately before Deep Dive.
    required.pop("MAX_QUALITY_RETRIES")
    for name, expected in required.items():
        if env.get(name, "") != expected:
            raise RuntimeError("Frozen Fresh environment mismatch: " + name)
    if not env.get("GEMINI_API_KEY"):
        raise RuntimeError("Locked Fresh requires explicit model credentials")
    if not env.get("GH_PAT") or not env.get("NOTION_API_KEY"):
        raise RuntimeError("Locked Fresh requires authoritative source/dedupe credentials")
    return source


class SendGuard:
    def __init__(self, original: Any, pipeline: Any, root: Path, source: str) -> None:
        self.original, self.pipeline, self.root, self.source = original, pipeline, root, source
        self.total = 0
        self.deep = 0
        self.status = "REGISTERED_NO_SEND"
        self._dump()

    def _dump(self) -> None:
        path = self.root / AUDIT_RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "campaign": CAMPAIGN, "source": self.source,
            "acquisition_protocol": "unchanged-production-baseline",
            "base_main": BASE_MAIN,
            "writer_blob": FROZEN_BLOBS["local_skills/writer.py"],
            "canonicalizer_blob": FROZEN_BLOBS["local_skills/publication_canonicalizer.py"],
            "max_model_sends": MAX_GEMINI_SENDS,
            "max_deep_dive_sends": MAX_DEEP_DIVE_SENDS,
            "attempted_model_sends": self.total,
            "attempted_deep_dive_sends": self.deep,
            "status": self.status,
            "quality_measured": False,  # Canary result is the ONLY quality authority.
            "persist_results": False,
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _abort(self, reason: str) -> None:
        self.status = reason
        self._dump()
        raise FreshCampaignAbort(reason)

    def send(self, model_name: str, prompt: str, config: dict | None = None,
             request_kind: str = "other", reserve: int = 0,
             request_context: str = "", count_as_deep_dive: bool = False,
             request_origin: str = "new") -> Any:
        # No quality retry or Rescue may participate in a Fresh quality claim.
        name = str(request_kind).lower()
        if any(word in name for word in ("quality", "rescue", "recompose", "repair")):
            self._abort("FORBIDDEN_FRESH_MODEL_REQUEST_KIND")
        permitted = set(EXPECTED_SCREENING.split(",")) | set(EXPECTED_DEEP_DIVE.split(","))
        if model_name not in permitted:
            self._abort("UNREGISTERED_MODEL")
        if self.total >= MAX_GEMINI_SENDS:
            self._abort("MODEL_SEND_BUDGET_EXHAUSTED")
        if count_as_deep_dive and self.deep >= MAX_DEEP_DIVE_SENDS:
            self._abort("DEEP_DIVE_SEND_BUDGET_EXHAUSTED")
        self.total += 1  # Reserve BEFORE SDK/provider send, failures count.
        if count_as_deep_dive:
            self.deep += 1
        self.status = "SEND_RESERVED"
        self._dump()
        try:
            response = self.original(
                model_name, prompt, config=config, request_kind=request_kind,
                reserve=reserve, request_context=request_context,
                count_as_deep_dive=count_as_deep_dive,
                request_origin=request_origin,
            )
        except Exception as exc:
            code = getattr(exc, "code", None)
            try:
                code = int(code)
            except (TypeError, ValueError):
                code = None
            if code in (503, 429):
                # Hard stop without a same-run retry, fallback, or new model.
                self._abort("PROVIDER_" + str(code) + "_HARD_STOP")
            self.status = "OTHER_PROVIDER_ERROR_RESERVED"
            self._dump()
            raise
        self.status = "SEND_COMPLETED"
        self._dump()
        return response

    def assert_usage_reconciled(self, pipeline: Any) -> None:
        records = getattr(getattr(pipeline, "GEMINI_USAGE_AUDIT", None), "records", None)
        if not isinstance(records, list) or len(records) != self.total:
            self._abort("PROVIDER_SEND_LEDGER_MISMATCH")
        if self.total > MAX_GEMINI_SENDS or self.deep > MAX_DEEP_DIVE_SENDS:
            self._abort("PROVIDER_SEND_CAP_BREACHED")
        self._dump()


def install_locked_fresh(pipeline: Any, *, repo_root: Path) -> SendGuard:
    root = Path(repo_root)
    source = verify_environment(dict(os.environ))
    verify_checkout(root)
    from local_skills.compiler import INTEGRATION_VERSION, WRITER_BLOB_SHA, CANONICALIZER_BLOB_SHA
    from local_skills.evidence_boundary import EVIDENCE_BOUNDARY_VERSION
    if (INTEGRATION_VERSION != "v4.3.9-integrated"
        or WRITER_BLOB_SHA != FROZEN_BLOBS["local_skills/writer.py"]
        or CANONICALIZER_BLOB_SHA != FROZEN_BLOBS["local_skills/publication_canonicalizer.py"]
        or EVIDENCE_BOUNDARY_VERSION != "stage10-v4"):
        raise RuntimeError("Validated Local Skills contract changed")
    original = getattr(pipeline, "_generate_via_chat", None)
    if not callable(original) or getattr(pipeline, "_FRESH_CAMPAIGN_LOCK_INSTALLED", False):
        raise RuntimeError("Frozen Fresh provider transport unavailable or double-installed")
    audit = getattr(pipeline, "GEMINI_USAGE_AUDIT", None)
    if getattr(audit, "records", None):
        raise RuntimeError("Fresh measurement cannot inherit existing provider sends")
    guard = SendGuard(original, pipeline, root, source)
    pipeline._generate_via_chat = guard.send
    pipeline._FRESH_CAMPAIGN_LOCK_INSTALLED = True
    return guard
