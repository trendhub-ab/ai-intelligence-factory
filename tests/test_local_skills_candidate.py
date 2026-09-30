from __future__ import annotations

import hashlib
import re
from pathlib import Path

from reader_experience_signals import reader_experience_signals
from reader_quality_precision import correct_reader_signals

from local_skills import (
    CANONICALIZER_BLOB_SHA,
    WRITER_BLOB_SHA,
    CANDIDATE_STATUS,
    compile_snapshot,
)
from local_skills.production_canary import build_snapshot, apply_to_production_parsed


ROOT = Path(__file__).resolve().parents[1]


def test_hacker_news_show_hn_prefix_and_personal_subtitle_are_not_public_title():
    repo = {"name": "Show HN: VT Code – My attempt at building a coding-agent harness", "url": "https://github.com/vinhnx/VTCode"}
    parsed = {"score": 70, "decision_text": "TRY", "source_summary_text": "公開済みのツール。", "what_text": "コード変更の確認に使う仕組み。", "why_important_text": "小さく試せる。", "decision_reason_text": "検証する価値がある。", "action_text": "コード変更を確認する。"}
    snapshot = build_snapshot(repo, parsed, source="HackerNews", primary_url=repo["url"], grounding=None)
    assert snapshot["name"] == repo["name"]
    assert snapshot["reader_title"] == "VT Code：いま何を判断材料にするべきか"
    assert len(snapshot["reader_title"]) <= 52


def test_production_adapter_leaves_provenance_footer_to_canonical_manuscript_builder():
    from note_manuscript import ARTICLE_DISCLAIMER, build_clean_note_manuscript
    repo = {"name": "Show HN: VT Code – My attempt at building a coding-agent harness", "url": "https://github.com/vinhnx/VTCode"}
    parsed = {"score": 70, "decision_text": "TRY", "source_summary_text": "公開済みのツール。", "what_text": "コード変更の確認に使う仕組み。", "why_important_text": "小さく試せる。", "decision_reason_text": "検証する価値がある。", "action_text": "コード変更を確認する。"}
    out, _ = apply_to_production_parsed(repo, parsed, source="HackerNews", primary_url=repo["url"], grounding=None)
    assert "### Sources / Evidence" not in out["note_draft"]
    manuscript = build_clean_note_manuscript(
        out["note_draft"], repo["name"], repo["url"], "N/A", "HackerNews",
        evidence_urls=[repo["url"]], title_text=out["title_text"],
        split_free_paid=lambda draft, name: (draft, ""),
        display_heading_aliases=lambda heading: [], subscription_enabled=False,
        subscription_landing_url="", subscription_campaign_id="",
    )
    assert manuscript.count("### Sources / Evidence") == 1
    assert f"- **主一次情報**: [{repo['name']}]({repo['url']})" in manuscript
    assert "- **出典について**:" in manuscript
    assert ARTICLE_DISCLAIMER.strip() in manuscript
WRITER_PATH = ROOT / "local_skills" / "writer.py"
CANON_PATH = ROOT / "local_skills" / "publication_canonicalizer.py"


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def _snapshot() -> dict:
    return {
        "schema": "aiif_local_writer_snapshot_v1",
        "case_id": "fresh-synthetic-contract-case",
        "canonical_entity_id": "url:https://example.invalid/kernel",
        "name": "Benchmark example: measured 7x faster kernel",
        "reader_title": "Kernel benchmark candidate",
        "source": "HackerNews",
        "source_summary": "A benchmark example measured 7x faster on a fixed workload.",
        "what": "A kernel implementation evaluated with a benchmark example.",
        "why_important": "It can be checked as a bounded engineering result rather than a universal claim.",
        "decision": "WATCH",
        "decision_score": 60,
        "decision_reason": "The benchmark is useful, but the result needs workload-specific verification.",
        "action": "Inspect the implementation and reproduce the benchmark.",
        "primary_risk": "The observed speedup may not transfer to another workload.",
        "best_for": "Teams that can reproduce kernel benchmarks.",
        "avoid_for": "Teams that need a universal performance guarantee.",
        "evidence_urls": ["https://example.invalid/kernel"],
    }


def test_candidate_blobs_match_declared_repair_versions():
    assert _git_blob_sha(WRITER_PATH) == WRITER_BLOB_SHA
    assert _git_blob_sha(CANON_PATH) == CANONICALIZER_BLOB_SHA


def test_compiler_preserves_evidence_surface_and_numeric_lexemes():
    original = _snapshot()
    result = compile_snapshot(original)

    assert result["status"] == CANDIDATE_STATUS
    assert result["canonicalizer_version"] == "stage6-v4"
    assert result["publication_topic_fit_version"] == "local-v1"
    assert result["integration_version"] == "v4.3.9-integrated"
    assert result["base_fresh_4_of_4_writer_blob_sha"] == "204cce30ab838e0d6dac9cbe762d0a82ff02f1aa"
    assert result["original_snapshot"] == original
    assert result["original_snapshot"] is not original

    canonical = result["canonicalized_snapshot"]
    assert canonical["canonical_entity_id"] == original["canonical_entity_id"]
    assert canonical["decision"] == original["decision"]
    assert canonical["decision_score"] == original["decision_score"]
    assert canonical["evidence_urls"] == original["evidence_urls"]
    assert "7x faster（一次情報で示された特定条件下の目安）" in canonical["name"]
    assert "実際の改善幅は処理内容・条件・実行環境によって変わります。" in canonical["primary_risk"]

    number_re = re.compile(r"[+-]?(?:\\d{1,3}(?:,\\d{3})+|\\d+)(?:\\.\\d+)?(?:[eE][+-]?\\d+)?")
    fields = (
        "name", "reader_title", "source_summary", "what", "why_important",
        "decision_reason", "action", "primary_risk", "best_for", "avoid_for",
    )
    before = number_re.findall("\\n".join(str(original.get(k) or "") for k in fields))
    after = number_re.findall("\\n".join(str(canonical.get(k) or "") for k in fields))
    assert before == after

    # Gate evidence context must come from the untouched record, not the
    # canonicalized publication surface.
    assert "一次情報で示された特定条件下の目安" not in result["evidence_context"]
    assert "Benchmark example: measured 7x faster kernel" in result["evidence_context"]
    assert result["parsed"]["note_draft"]


def test_candidate_is_idempotent():
    first = compile_snapshot(_snapshot())
    second = compile_snapshot(first["canonicalized_snapshot"])
    assert second["canonicalized_snapshot"] == first["canonicalized_snapshot"]


def test_local_skills_wiring_is_canary_only_and_fail_closed():
    # Stage 8 deliberately wires the frozen candidate only behind the explicit
    # measurement-only canary. Normal Production must not enable it implicitly.
    pipeline_text = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    production_text = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
    assert 'os.environ.get("AIIF_LOCAL_SKILLS_CANARY", "false")' in pipeline_text
    assert 'if local_skills_canary and persist_results:' in pipeline_text
    assert 'local_skills_canary_validation' in production_text
    assert 'from local_skills_daily_canary import run' in production_text


def test_evidence_boundary_removes_derived_currency_but_keeps_supported_latency():
    snapshot = _snapshot()
    snapshot["decision_reason"] = (
        "1回あたり0.30秒・約0.02円という低い遅延とコストで動作します。"
    )
    result = compile_snapshot(
        snapshot,
        evidence_context="The benchmark measured 7x on the fixed workload. The measured latency was 0.30 seconds and the source also mentioned $0.02.",
    )

    bounded = result["canonicalized_snapshot"]["decision_reason"]
    assert "0.30秒" in bounded
    assert "0.02" not in bounded
    assert "約0.02円" not in result["parsed"]["note_draft"]
    assert result["evidence_boundary_version"] == "stage10-v4"
    assert result["evidence_boundary"]["removed_count"] == 1
    assert result["evidence_boundary"]["removed_unsupported_numeric_claims"] == [
        {"field": "decision_reason", "claim": "約0.02円"}
    ]


def test_writer_adds_first_use_non_engineer_subject_bridge_without_new_source_fact():
    snapshot = _snapshot()
    snapshot.update({
        "name": "Jevmem – automatic project memory for Claude Code, built on Jev",
        "reader_title": "Jevmem：いま何を判断材料にするべきか",
        "source_summary": (
            "開発AIとのチャットから意思決定や制約を記録し、"
            "次回の作業時に必要な文脈を再利用する構成です。"
        ),
        "what": "開発AIとのチャット内容をプロジェクト履歴として扱うツールです。",
    })
    result = compile_snapshot(snapshot)
    article = result["parsed"]["note_draft"]

    assert "今回の検証対象（Jevmem）" in article
    assert "一次情報で確認できる説明はこうです。" in article
    assert re.search(r"(?:ですよね|ませんか)", article)
    assert snapshot["source_summary"] in result["evidence_context"]


def test_explicit_production_evidence_context_is_kept_separate_from_structured_record():
    snapshot = _snapshot()
    evidence = "Primary source evidence: benchmark measured 7x on the fixed workload."
    result = compile_snapshot(snapshot, evidence_context=evidence)
    assert result["evidence_context"] == evidence
    assert "reader_title:" not in result["evidence_context"]


def test_evidence_boundary_requires_compatible_unit_not_only_same_number():
    snapshot = _snapshot()
    snapshot["decision_reason"] = "約0.02円のコストです。"
    result = compile_snapshot(snapshot, evidence_context="The benchmark measured 7x on the fixed workload. The measured latency was 0.02 seconds and cost was $0.02.")
    assert "0.02円" not in result["parsed"]["note_draft"]
    assert result["evidence_boundary"]["removed_count"] == 1


def test_writer_explains_mcp_and_agent_skills_and_uses_complete_negative_fit_sentence():
    snapshot = _snapshot()
    snapshot["action"] = "Model Context Protocol (MCP) サーバーとAgent Skillsを限定環境で試す。"
    result = compile_snapshot(snapshot)
    article = result["parsed"]["note_draft"]
    assert "Model Context Protocol (MCP)（AIと外部ツールやデータを接続する共通規格）" in article
    assert "Agent Skills（AIに特定作業の手順や知識を追加する仕組み）" in article
    assert "向いていないのは、" in article



def test_evidence_boundary_matches_fact_gate_currency_surface_fail_closed():
    snapshot = _snapshot()
    snapshot["why_important"] = "計算費用は約100ドルから2000ドルです。"
    result = compile_snapshot(
        snapshot,
        evidence_context=(
            "The benchmark measured 7x. The reported cost range was $100 to $2,000."
        ),
    )
    article = result["parsed"]["note_draft"]
    assert "100ドル" not in article
    assert "2000ドル" not in article
    assert result["evidence_boundary"]["removed_count"] == 2


def test_evidence_boundary_keeps_fact_gate_equivalent_seconds_surface():
    snapshot = _snapshot()
    snapshot["decision_reason"] = "処理時間は0.30秒です。"
    result = compile_snapshot(
        snapshot,
        evidence_context="The benchmark measured 7x and latency was 0.30 seconds.",
    )
    assert "0.30秒" in result["parsed"]["note_draft"]



def test_writer_explains_model_generation_and_version_labels_in_long_news_title():
    snapshot = _snapshot()
    snapshot.update({
        "name": "DeepSeek beats GPT-6 Sol in autonomous drug development",
        "reader_title": "DeepSeek benchmark：いま何を判断材料にするべきか",
        "source_summary": (
            "製薬・バイオテック分野の実務を模擬した新ベンチマーク"
            "「Biopharma Bench V0.1」において、DeepSeek-V4.1 Flashが"
            "GPT-5.6 Solの平均スコアを上回る結果を示した。"
        ),
        "what": "規制の厳しいバイオ医薬品開発プロセスを模した評価テストです。",
        "decision_reason": "GPT-6 Astraも含め、実務投入前に追加確認が必要です。",
        "action": "ベンチマーク動向を確認し、限定的な評価を続けます。",
    })
    result = compile_snapshot(snapshot)
    article = result["parsed"]["note_draft"]

    assert "今回の検証対象であるこの対象" not in article
    assert "Biopharma Bench V0.1" in article
    assert "GPT-6（AIモデルの世代名）" in article
    assert "GPT-5（AIモデルの世代名）" in article
    assert "V0（名称中のバージョン表記）" in article
    assert "V4（名称中のバージョン表記）" in article



def test_writer_cockpit_case_has_product_label_and_reader_accessibility():
    snapshot = _snapshot()
    snapshot.update({
        "case_id": "observed-cockpit-reader-regression",
        "canonical_entity_id": "url:https://aidash.dev/",
        "name": "Show HN: I couldn't deal with another Claude Code tab",
        "reader_title": "Show HN: I couldn't deal with another Claude Code tab：いま何を判断材料にするべきか。",
        "source_summary": (
            "簡単に言えば、コーディングAIエージェントであるClaude CodeやCodexが"
            "ローカルに書き出す対話ログを自動で読み込み、開発状況を一つの画面で"
            "並行管理できるmacOS向けデスクトップアプリ「Cockpit」が公開されました。"
        ),
        "what": (
            "ターミナルのタブに散らばりがちな複数のAIエージェント実行セッションを"
            "監視・整理し、人間の承認待ち状態を検知して一元的に返答できる"
            "軽量なローカル管理ツールが登場しました。"
        ),
        "why_important": (
            "AIエージェントに自律的なコーディングを任せる際、どのタブが処理を終えたか、"
            "どこで承認待ちで止まっているかを把握する手間を減らし、"
            "開発者のマルチタスク管理を助けます。"
        ),
        "decision": "TRY",
        "decision_score": 66,
        "decision_reason": (
            "Claude CodeやCodexをCLIで動かしている環境で、既存セッションを"
            "並行管理できるか限定的に確認します。"
        ),
        "action": (
            "開発マシンにCockpitを導入し、既存セッションの読み込みと"
            "画面上からの指示・承認を限定環境でテストします。"
        ),
        "primary_risk": "一次情報の対象範囲を越えて一般化せず、限定した検証で条件差を確認する必要があります。",
        "best_for": "AIコーディング作業を複数並行で扱い、小さく検証できる開発チーム。",
        "avoid_for": "検証条件を確認せず、本番適用を広く一般化したいチーム。",
        "evidence_urls": ["https://aidash.dev/"],
    })
    result = compile_snapshot(snapshot)
    article = result["parsed"]["note_draft"]

    assert "Show HNを自社" not in article
    assert "今回の検証対象（Cockpit）" in article
    assert "CLI（文字でコマンドを入力して操作する方式）" in article
    assert "AIエージェント（つまり、AIが複数の手順を自律的に進める仕組み）" in article
    assert "何が変わる" in article
    assert "チーム" in article

    base = reader_experience_signals(article, lambda value, limit: value[:limit])
    signals = correct_reader_signals(article, base)
    assert signals["accessibility"] == "GOOD"
    assert signals["curiosity_pull"] == "GOOD"
    assert signals["reader_enjoyment"] == "GOOD"
    assert signals["jargon_translation"] == "GOOD"
    assert signals["non_engineer_core_clarity"] == "GOOD"


def test_evidence_boundary_removes_unsupported_generic_counts_before_fact_gate():
    snapshot = _snapshot()
    snapshot["decision_reason"] = (
        "コードレビューでは4件の重大な問題と6件の追加指摘を検出したと評価されています。"
    )
    result = compile_snapshot(
        snapshot,
        evidence_context=(
            "The benchmark measured 7x on the fixed workload. "
            "The review discusses code quality findings, but the primary source does not "
            "state four major issues or six additional findings."
        ),
    )

    bounded = result["canonicalized_snapshot"]["decision_reason"]
    article = result["parsed"]["note_draft"]
    assert "4件" not in bounded
    assert "6件" not in bounded
    assert "4件" not in article
    assert "6件" not in article
    assert bounded == "判断理由は、一次情報で確認できる事実と未確認部分を分けて扱います。"
    assert result["evidence_boundary"]["removed_unsupported_numeric_claims"] == [
        {"field": "decision_reason", "claim": "4件"},
        {"field": "decision_reason", "claim": "6件"},
    ]


def test_evidence_boundary_keeps_supported_generic_count_with_matching_entity_semantics():
    snapshot = _snapshot()
    snapshot["what"] = "不審なパッケージを2,000件確認した調査です。"
    result = compile_snapshot(
        snapshot,
        evidence_context="Researchers observed 2,000 suspicious packages in the study.",
    )

    assert "2,000件" in result["canonicalized_snapshot"]["what"]
    assert not any(
        row["claim"] == "2,000件"
        for row in result["evidence_boundary"]["removed_unsupported_numeric_claims"]
    )


def test_evidence_boundary_rejects_same_count_when_evidence_entity_differs():
    snapshot = _snapshot()
    snapshot["what"] = "不審なパッケージを2,000件確認した調査です。"
    result = compile_snapshot(
        snapshot,
        evidence_context="The report mentions 2,000 users and 14 suspicious packages.",
    )

    assert "2,000件" not in result["canonicalized_snapshot"]["what"]
    assert {"field": "what", "claim": "2,000件"} in result["evidence_boundary"]["removed_unsupported_numeric_claims"]
