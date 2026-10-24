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
    import json
    stage_records = {
        label: {
            "Writer Reaction": "Question: verified sample only",
            "Editorial Discovery": "Evidence Pivot: local-only",
            "Cognitive Shift": "After View: offline",
            "Persona Article Generation": text,
            "Fact-Safe Review": text,
        }
        for label, text in samples.items()
    }
    stage_bytes = {
        label: json.dumps(stages, ensure_ascii=False, indent=2).encode("utf-8")
        for label, stages in stage_records.items()
    }
    archives = tmp_path / "private_fixture.zip"
    with zipfile.ZipFile(archives, "w") as zipped:
        for label, text in samples.items():
            zipped.writestr(f"正本_{label}.md", text.encode("utf-8"))
            zipped.writestr(f"5段階_{label}.json", stage_bytes[label])
    hashes = {
        case_id: hashlib.sha256(samples[label].encode()).hexdigest()
        for case_id, label in zip(guard.CASE_IDS, guard.LABELS)
    }
    sizes = {
        case_id: len(samples[label])
        for case_id, label in zip(guard.CASE_IDS, guard.LABELS)
    }
    stage_hashes = {
        case_id: hashlib.sha256(stage_bytes[label]).hexdigest()
        for case_id, label in zip(guard.CASE_IDS, guard.LABELS)
    }
    with patch.dict(guard.ARTICLE_DIGESTS, hashes), patch.dict(guard.ORIGINAL_CHARS, sizes), patch.dict(guard.STAGE_JSON_DIGESTS, stage_hashes):
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
                zipped.writestr(f"5段階_{label}.json", stage_bytes[label])
        with pytest.raises(guard.PrivateGoldenMismatch, match="altered"):
            guard.verify_private_golden_archive(archives)

        # Identical finished manuscripts are not sufficient if stage records drift.
        with zipfile.ZipFile(archives, "w") as zipped:
            for label, text in samples.items():
                zipped.writestr(f"正本_{label}.md", text.encode("utf-8"))
                zipped.writestr(f"5段階_{label}.json", stage_bytes[label] + b" ")
        with pytest.raises(guard.PrivateGoldenMismatch, match="five-stage"):
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



def test_stage_continuity_flags_lost_question_without_rewriting_article():
    stages = {
        "Writer Reaction": "Question: なぜ同じデータで結果が変わるのだろう？",
        "Editorial Discovery": "Evidence: 条件付きの観察結果から説明が変わった",
        "Cognitive Shift": "単なる高速化ではなく、分業設計の差だった",
        "Persona Article Generation": "# 比較の条件\n\n実験では異なる条件が使われた。",
        "Fact-Safe Review": "# 比較の条件\n\n実験では異なる条件が使われた。",
    }
    original = dict(stages)
    report = guard.review_stage_continuity(stages)
    assert report["reaction_question_punctuation"] == 1
    assert report["final_question_punctuation"] == 0
    assert report["diagnostic_cautions"] == [
        "check_question_to_article_continuity",
        "fact_safe_stage_left_article_unchanged",
    ]
    assert report["persona_to_fact_safe_identical"] is True
    assert stages == original  # Observational only, no source/article rewrite
    assert not report["publication_approval"]
    assert not report["human_quality_approval"]
    assert not report["fact_approval"]
    assert all(len(digest) == 64 for digest in report["stage_digests"].values())
    assert "なぜ同じデータ" not in str(report)  # no private article text in public CI


def test_stage_continuity_does_not_invent_a_human_score_from_question_marks():
    stages = {
        "Writer Reaction": "Question: 何が変わる？",
        "Editorial Discovery": "Evidence: 対象範囲が狭い",
        "Cognitive Shift": "結論は条件付き",
        "Persona Article Generation": "# 条件を読み直す\n\n何が変わる？ まだ調査が必要。",
        "Fact-Safe Review": "# 条件を読み直す\n\n何が変わる？ まだ調査が必要。",
    }
    report = guard.review_stage_continuity(stages)
    assert report["reaction_question_punctuation"] == 1
    assert report["final_question_punctuation"] == 1
    assert "check_question_to_article_continuity" not in report["diagnostic_cautions"]
    assert "quality_score" not in report
    assert report["human_quality_approval"] is False


def test_stage_continuity_rejects_incomplete_or_invalid_bundles():
    with pytest.raises(guard.PrivateGoldenMismatch, match="Five-stage"):
        guard.review_stage_continuity({"Writer Reaction": "Question: なぜ？"})
    with pytest.raises(guard.PrivateGoldenMismatch, match="Five-stage"):
        guard.review_stage_continuity(None)
    with pytest.raises(guard.PrivateGoldenMismatch, match="Empty"):
        guard.review_stage_continuity({
            "Writer Reaction": "Question: なぜ？",
            "Editorial Discovery": "Insight",
            "Cognitive Shift": "Shift",
            "Persona Article Generation": "# Article\n\nBody",
            "Fact-Safe Review": "",
        })
