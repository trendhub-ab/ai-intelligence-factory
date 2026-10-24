"""Public CI verifies P5 golden digests without storing unpublished manuscripts."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import hashlib
import zipfile

import pytest

from experiments.v3_p5_golden_cases import READY_CASES
from experiments import v3_p5_private_golden_guard as guard


def test_exact_historical_input_identity_and_article_digests_are_pinned():
    assert len(READY_CASES) == len(guard.CASE_IDS) == 3
    assert list(guard.HISTORICAL_HUMAN_SCORES.values()) == [75, 85, 88]
    assert guard.BASELINE_RUN == 39963513015
    for item in READY_CASES:
        guard.assert_selected_case(item.case)
        assert guard.input_digest(item.case) == guard.INPUT_DIGESTS[item.case.case_id]
        assert len(guard.ARTICLE_DIGESTS[item.case.case_id]) == 64


@pytest.mark.parametrize("field,value", [
    ("title", "different headline"),
    ("evidence", ("different fact",)),
    ("facts", ("added fact",)),
    ("sources", ("https://example.org/new",)),
    ("target_reader", "different people"),
])
def test_reuse_rejects_changed_source_or_topic(field, value):
    modified = replace(READY_CASES[0].case, **{field: value})
    with pytest.raises(guard.PrivateGoldenMismatch, match="Exact original"):
        guard.assert_selected_case(modified)


def test_previous_plain_explanation_regression_remains_unapproved():
    for item in READY_CASES[:2]:
        summary_only = "# Technical explanation\n\n" + "要点を短く説明します。" * 20
        receipt = guard.review_candidate(item.case, summary_only)
        assert receipt["warnings"] == [
            "large_compression_vs_original",
            "lost_structured_discovery",
            "not_original_manuscript",
        ]
        assert receipt["human_quality_approval"] is False
        assert receipt["fact_approval"] is False
        assert receipt["publication_approval"] is False


def test_missing_or_corrupt_private_archive_is_fail_closed(tmp_path: Path):
    with pytest.raises(guard.PrivateGoldenMismatch, match="archive missing"):
        guard.verify_private_golden_archive(tmp_path / "absent.zip")
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")
    with pytest.raises(guard.PrivateGoldenMismatch, match="Cannot verify"):
        guard.verify_private_golden_archive(broken)


def test_private_archive_verification_and_export_do_not_need_gemini(tmp_path: Path):
    samples = {
        label: "# Editorial reference\n\n" + f"Dummy local fixture for {label}." * 18
        for label in guard.LABELS
    }
    archives = tmp_path / "private_fixture.zip"
    with zipfile.ZipFile(archives, "w") as zipped:
        for label, text in samples.items():
            zipped.writestr(f"正本_{label}.md", text.encode("utf-8"))
    hashes = {
        case_id: hashlib.sha256(samples[label].encode()).hexdigest()
        for case_id, label in zip(guard.CASE_IDS, guard.LABELS)
    }
    sizes = {
        case_id: len(samples[label])
        for case_id, label in zip(guard.CASE_IDS, guard.LABELS)
    }
    with patch.dict(guard.ARTICLE_DIGESTS, hashes), patch.dict(guard.ORIGINAL_CHARS, sizes):
        assert guard.verify_private_golden_archive(archives) == samples
        exported = tmp_path / "review-only"
        manifest = guard.export_verified_private_goldens(archives, exported)
        assert manifest["gemini_calls"] == 0
        assert manifest["ready_or_publication_approval"] is False
        assert not manifest["note_write"] and not manifest["notion_write"]
        for label in guard.LABELS:
            assert (exported / f"P5_original_{label}.md").read_text() == samples[label]
        # A tampered sentence fails even when the outer ZIP structure is valid.
        with zipfile.ZipFile(archives, "w") as zipped:
            for label, text in samples.items():
                zipped.writestr(f"正本_{label}.md", text + " tampered")
        with pytest.raises(guard.PrivateGoldenMismatch, match="altered"):
            guard.verify_private_golden_archive(archives)


def test_repository_public_contract_has_no_original_article_plaintext():
    from inspect import getsource
    source = getsource(guard)
    assert "client.models.generate_content" not in source
    assert "GEMINI_API_KEY" not in source
    assert "notion.create" not in source
    assert "verbatim" in source



def test_unpublished_golden_articles_are_not_stored_in_public_repo():
    """A repeat of the private-fixture mistake must fail the PR's CI."""
    repository = Path(__file__).resolve().parents[1]
    for pattern in (
        "**/v3_p5_golden_83_articles.json.gz.b64",
        "**/p5_83_fixture.b64",
        "**/P5_original_FFT.md",
        "**/P5_original_Elastic.md",
        "**/P5_original_Claude.md",
    ):
        assert not list(repository.glob(pattern)), f"Private P5 manuscript may not be committed: {pattern}"
