"""Offline inspection of the V1 Human Narrative prompt assembly stack.

Reconstructs a SYNTHETIC candidate using existing pure builders. It is not a
replay of the November 5 Daily: run-specific source context, evidence, display
rotation and retry history were not saved as an exact prompt receipt.

This module has NO Gemini client, network, Notion, note, or publish authority.
It never prints prompt text or any article and does not change pipeline.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha1, sha256
import json
from pathlib import Path

import content_generation_protocol as cgp
from canonical_article_contract import ensure_writer_contract, ensure_final_reader_check
from run226_reader_delight_planning import augment_prompt as reader_delight
from run228_reader_rhythm_planning import augment_prompt as reader_rhythm
from reader_value_review_bridge import PRODUCTION_YIELD_CONTRACT
from local_skills.a_plus import build_prewrite_contract
from a_plus_editorial_orchestration import _OUTPUT_MARKER
from runtime_layers import RUNTIME_LAYER_ORDER

RUN_ID = 42016503443
RUN_SHA = "3276b740c8a525cd47ec9ebe9e6057044137b551"
STYLE = "human_narrative"
# These are source snapshots of the observed V1 production code, NOT secret keys.
SOURCE_BLOBS = {
    "content_generation_protocol.py": "2986ed5be0a46ec0dfc5594b3d23f7798cf25177",
    "canonical_article_contract.py": "6a1465955d6b95cf489886207769944dfc556a48",
    "run226_reader_delight_planning.py": "f360f5d9cd73850c767d8ea7a7f122d80729b8c3",
    "run228_reader_rhythm_planning.py": "3af4cc2bf0da05b281d8fcab411f349da02446ec",
    "reader_value_review_bridge.py": "b1adec4f6bcf6e022530d5d147a9698ed8e030ab",
    "run208_reader_value_repair.py": "6a1c61b2c9ed2a3e05cb199be0adb9983164c8a7",
    "a_plus_editorial_orchestration.py": "02ce0e938dd7f889c343fcca1fedafac594a0fa9",
    "local_skills/a_plus.py": "595caa5a8bcf207dbf1e4df8f22a8ae2a241d128",
    "run248_first_real_publish_quality_calibration.py": "b6d29b5ed16cdd9b35e27535d75764c8cc31d4f6",
    "runtime_layers.py": "acac2f3b96319c52943ff6623fdc3b7448582ff1",
}
ROOT = Path(__file__).resolve().parents[1]
ORDER = (
    "run226_reader_delight_planning.install",
    "run228_reader_rhythm_planning.install",
    "reader_value_review_bridge.install",
    "run208_reader_value_repair.install",
    "a_plus_editorial_orchestration.install",
    "run248_first_real_publish_quality_calibration.install",
)


def _blob_sha(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()


def verify_pinned_sources() -> None:
    """Fail closed if this diagnostic is run against another code revision."""
    for path, expected in SOURCE_BLOBS.items():
        file = ROOT / path
        if not file.is_file() or _blob_sha(file.read_bytes()) != expected:
            raise ValueError("V1_SOURCE_DRIFT:" + path)
    positions = [RUNTIME_LAYER_ORDER.index(layer) for layer in ORDER]
    if positions != sorted(positions) or len(set(positions)) != len(ORDER):
        raise ValueError("V1_PROMPT_LAYER_ORDER_DRIFT")


class _FrozenDate(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 5, 20, 15, tzinfo=tz)


def _base_synthetic() -> str:
    """Use only intentionally fictional fixture data; never fetch sources."""
    return cgp.build_decision_prompt(
        name="synthetic_prompt_trace_only",
        url="https://example.com/synthetic-only",
        stars=0,
        desc="架空の品質検証用題材であり公開・執筆に使用しない",
        source="HackerNews",
        source_context="SYNTHETIC FIXTURE — no factual claims; never publish.",
        grounding_status_hint="SYNTHETIC",
        evidence_metadata={"synthetic": True},
        freshness={"context": "SYNTHETIC_ONLY"},
        evidence_result={"numeric_claims_allowed": False,
                         "actor_attribution_allowed": False},
        engagement_labels={"HackerNews": "Engagement"},
        max_evidence_total_chars=1200,
        truncate_source_context=lambda value: str(value)[:1200],
        source_fact_discipline=cgp._source_fact_discipline,
        human_editorial_style_rules=lambda: cgp.editorial_style_rules(STYLE),
        article_display_variant=lambda name: {
            "style": "SYNTHETIC", "opening": "SYNTHETIC", "tone": "SYNTHETIC"
        },
        section_split_token="===NOTE_DRAFT_START===",
        datetime_cls=_FrozenDate,
        jst=timezone(timedelta(hours=9)),
    )


def _receipt(stage: str, prompt: str) -> dict:
    return {
        "stage": stage,
        "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_utf8_bytes": len(prompt.encode("utf-8")),
    }


def trace_synthetic() -> dict:
    """Print SHA receipts only; explicitly NEVER attribute them to actual Daily."""
    verify_pinned_sources()
    raw = _base_synthetic()
    receipts = [_receipt("base_generation_protocol", raw)]
    raw = reader_delight(raw)
    receipts.append(_receipt("run226_reader_delight", raw))
    raw = reader_rhythm(raw)
    receipts.append(_receipt("run228_reader_rhythm", raw))
    raw = raw.rstrip() + "\n\n" + PRODUCTION_YIELD_CONTRACT + "\n"
    receipts.append(_receipt("reader_value_bridge", raw))
    raw = ensure_writer_contract(raw)
    receipts.append(_receipt("run208_reader_value", raw))
    contract = build_prewrite_contract(
        {"numeric_claims_allowed": False, "actor_attribution_allowed": False},
        {"synthetic": True},
    )
    block = "\n【A+ Local Skills Pre-Write Contract】\n" + contract + "\n"
    raw = (raw.replace(_OUTPUT_MARKER, block + _OUTPUT_MARKER, 1)
           if _OUTPUT_MARKER in raw else raw.rstrip() + "\n" + block)
    receipts.append(_receipt("a_plus_prewrite", raw))
    raw = ensure_final_reader_check(raw)
    receipts.append(_receipt("run248_final_reader_check", raw))
    assert raw.count("AIIF_CANONICAL_ARTICLE_CONTRACT_V1") >= 1
    assert raw.count("AIIF_CANONICAL_FINAL_READER_CHECK_V1") >= 1
    return {
        "schema": "v1-synthetic-writer-prompt-stack-receipt-v1",
        "status": "SYNTHETIC_ONLY_NOT_ACTUAL_NOV05_PROMPT",
        "v1_run_id": RUN_ID,
        "observed_v1_run_commit": RUN_SHA,
        "observed_style": STYLE,
        "pinned_source_blobs": dict(SOURCE_BLOBS),
        "stages": receipts,
        "actual_run_prompt_sha256": None,
        "actual_run_input_evidence_verified": False,
        "actual_run_dynamic_display_rotation_verified": False,
        "actual_run_retry_prompt_verified": False,
        "real_world_fact_verified": False,
        "next_v04_identical_evidence_verified": False,
        "can_rank_writers": False,
        "eligible_for_live_generation": False,
        "authorized_model_requests": 0,
        "production_modified": False,
        "publication_approved": False,
    }


if __name__ == "__main__":
    print(json.dumps(trace_synthetic(), ensure_ascii=False, sort_keys=True, indent=2))
