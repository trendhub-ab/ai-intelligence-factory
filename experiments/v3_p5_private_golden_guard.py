"""Offline golden fidelity guard: public-safe metadata, NEVER private manuscripts.

The three completed 83-point-era articles live in a user-controlled ZIP,
NOT in the public repository. Verifies an explicitly supplied private archive,
or assesses a candidate. No APIs, notes, Notion, or auto-publication.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiments.v3_p5_golden_cases import READY_CASES

BASELINE_COMMIT = "95016a65701979063f56130bf181bca831661f5d"
BASELINE_RUN = 39963513015
LABELS = ("FFT", "Elastic", "Claude")
CASE_IDS = (
    "3f8479ff-dca9-8146-b90d-df1fc42c40ef",
    "3fa479ff-dca9-8194-a493-cb3a0d2b3a36",
    "3f3479ff-dca9-8153-a62e-d3768adb3160",
)
ARTICLE_DIGESTS = {
    CASE_IDS[0]: "e0808d455c843f3f07e27ebf2a8478ffb7852f59d46296f0f366dd3c8ad7c756",
    CASE_IDS[1]: "e74ee9fedbdfe21d227b210d9ba971c6639b63cfc95ff34fd60f262ac2c577c3",
    CASE_IDS[2]: "38b4c0e1a65c02e8f83e296e17ed6584ae3e294107bdc70203b90a66f23afd3d",
}
INPUT_DIGESTS = {
    CASE_IDS[0]: "1704037a92711d2a961fd3c584f357cc32c529295b8098923a6e2b2777f254ca",
    CASE_IDS[1]: "16f4fa6d9c2648804a0d9df22466b0c9701aa06971a559ec16f02db745f9e8fb",
    CASE_IDS[2]: "2bd648caa7a9c9e7094cc00790a0138d1b95620fc7ddd0c508e4b053237f54df",
}
ORIGINAL_CHARS = dict(zip(CASE_IDS, (1206, 1159, 721)))
ORIGINAL_SECTIONS = dict(zip(CASE_IDS, (3, 3, 0)))
HISTORICAL_HUMAN_SCORES = dict(zip(CASE_IDS, (75, 85, 88)))


class PrivateGoldenMismatch(RuntimeError):
    """Reject mutable/cross-topic/unverified golden content."""


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def input_digest(case: Any) -> str:
    data = {
        "case_id": case.case_id,
        "title": case.title,
        "evidence": case.evidence,
        "facts": case.facts,
        "sources": case.sources,
        "target_reader": case.target_reader,
    }
    return _sha(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def assert_selected_case(case: Any) -> None:
    case_id = str(getattr(case, "case_id", ""))
    if case_id not in INPUT_DIGESTS or input_digest(case) != INPUT_DIGESTS[case_id]:
        raise PrivateGoldenMismatch("Exact original Phase0 case and unchanged source inputs required")


def verify_private_golden_archive(path: Path) -> dict[str, str]:
    """Check user's LOCAL review ZIP against pinning; do not upload or publish.

    Original historical 83-point evaluation remains provenance only.
    Do not trust a ZIP label as proof: hash all three exact UTF-8 manuscript bytes.
    """
    if not Path(path).is_file():
        raise PrivateGoldenMismatch("Private golden archive missing")
    try:
        with zipfile.ZipFile(path) as zipped:
            articles = {}
            for item, label in zip(READY_CASES, LABELS, strict=True):
                assert_selected_case(item.case)
                article = zipped.read(f"正本_{label}.md").decode("utf-8")
                case_id = item.case.case_id
                if _sha(article.encode("utf-8")) != ARTICLE_DIGESTS[case_id]:
                    raise PrivateGoldenMismatch("Archived original manuscript altered")
                if not article.startswith("# ") or len(article) != ORIGINAL_CHARS[case_id]:
                    raise PrivateGoldenMismatch("Original article layout/length drift")
                articles[label] = article
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeError) as exc:
        raise PrivateGoldenMismatch("Cannot verify private golden archive") from exc
    return articles


def review_candidate(case: Any, article: str) -> dict:
    """Diagnostics, not a machine claim of human quality or publication approval."""
    assert_selected_case(case)
    original_hash = ARTICLE_DIGESTS[case.case_id]
    article = str(article or "")
    candidate_hash = _sha(article.encode("utf-8"))
    ratio = round(len(article) / ORIGINAL_CHARS[case.case_id], 3)
    sections = len(re.findall(r"(?m)^#{2,3}\s+", article))
    warnings = []
    if ratio < 0.8:
        warnings.append("large_compression_vs_original")
    if ORIGINAL_SECTIONS[case.case_id] >= 2 and sections == 0:
        warnings.append("lost_structured_discovery")
    if not article.startswith("# "):
        warnings.append("missing_article_title")
    if candidate_hash != original_hash:
        warnings.append("not_original_manuscript")
    return {
        "case_id": case.case_id,
        "historical_source_run": BASELINE_RUN,
        "historical_human_score": HISTORICAL_HUMAN_SCORES[case.case_id],
        "original_article_sha256": original_hash,
        "candidate_article_sha256": candidate_hash,
        "exact_original": candidate_hash == original_hash,
        "relative_chars": ratio,
        "warnings": warnings,
        "human_quality_approval": False,
        "fact_approval": False,
        "publication_approval": False,
        "next_step": "HUMAN_EDITORIAL_AND_INDEPENDENT_FACT_REVIEW",
    }


def export_verified_private_goldens(archive: Path, output: Path) -> dict:
    """Private review-only original article copies; fail before writing if invalid."""
    originals = verify_private_golden_archive(archive)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for item, label in zip(READY_CASES, LABELS, strict=True):
        article = originals[label]
        output_path = output / f"P5_original_{label}.md"
        output_path.write_text(article, encoding="utf-8")
        rows.append({
            "label": label,
            "file": output_path.name,
            "source_run": BASELINE_RUN,
            "input_sha256": INPUT_DIGESTS[item.case.case_id],
            "article_sha256": ARTICLE_DIGESTS[item.case.case_id],
            "human_review_required": True,
        })
    manifest = {
        "mode": "private_verbatim_nonpublishing_review",
        "articles": rows,
        "gemini_calls": 0,
        "note_write": False,
        "notion_write": False,
        "ready_or_publication_approval": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
