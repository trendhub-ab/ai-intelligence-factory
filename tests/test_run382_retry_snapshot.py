from types import SimpleNamespace

import run382_retry_snapshot as run382


class _Logger:
    def __init__(self):
        self.messages = []

    def warning(self, message, *args):
        self.messages.append(message % args if args else str(message))

    def info(self, message, *args):
        self.messages.append(message % args if args else str(message))


def _pipeline(*, generator_result=None, trigger_retry=True):
    p = SimpleNamespace()
    p.logger = _Logger()

    def build_decision_prompt(*args, **kwargs):
        return "prompt"

    def generate_intelligence_report(*args, **kwargs):
        if trigger_retry:
            p.build_decision_prompt(
                "name",
                "url",
                0,
                "desc",
                "PUB_INTRO_OVERCLAIM: fix intro only",
                previous_article="PRE_RETRY_MANUSCRIPT",
            )
        return generator_result

    p.build_decision_prompt = build_decision_prompt
    p.generate_intelligence_report = generate_intelligence_report
    return p


def _gate_pipeline(article_issues):
    p = SimpleNamespace()
    p.logger = _Logger()

    def validate_publication_readiness_gate(parsed, source_context="", source_info=None):
        issues = list(article_issues)
        return ("REVIEW" if issues else "PASS"), issues

    p.validate_publication_readiness_gate = validate_publication_readiness_gate
    return p


def test_read_only_pending_retry_preserves_snapshot_as_rejected_when_provider_path_returns_none():
    p = _pipeline(generator_result=None, trigger_retry=True)
    run382.install(p)
    result = p.generate_intelligence_report(
        {},
        candidate_origin="pending_retry_validation",
        persist_results=False,
    )
    assert result == ("PRE_RETRY_MANUSCRIPT", "rejected")
    assert any("RUN382 RETRY SNAPSHOT PRESERVED" in message for message in p.logger.messages)


def test_read_only_article_validation_preserves_snapshot_as_rejected():
    p = _pipeline(generator_result=None, trigger_retry=True)
    run382.install(p)
    assert p.generate_intelligence_report(
        {},
        candidate_origin="article_revalidation",
        persist_results=False,
    ) == ("PRE_RETRY_MANUSCRIPT", "rejected")


def test_persisting_production_path_never_consumes_snapshot_fallback():
    p = _pipeline(generator_result=None, trigger_retry=True)
    run382.install(p)
    assert p.generate_intelligence_report(
        {},
        candidate_origin="new",
        persist_results=True,
    ) is None


def test_read_only_without_actual_retry_has_no_snapshot_to_return():
    p = _pipeline(generator_result=None, trigger_retry=False)
    run382.install(p)
    assert p.generate_intelligence_report(
        {},
        candidate_origin="pending_retry_validation",
        persist_results=False,
    ) is None


def test_successful_generator_result_is_never_replaced_by_snapshot():
    p = _pipeline(generator_result=("NEW_MANUSCRIPT", "accepted"), trigger_retry=True)
    run382.install(p)
    assert p.generate_intelligence_report(
        {},
        candidate_origin="pending_retry_validation",
        persist_results=False,
    ) == ("NEW_MANUSCRIPT", "accepted")


def test_snapshot_is_cleared_between_candidates():
    p = _pipeline(generator_result=None, trigger_retry=True)
    run382.install(p)
    assert p.generate_intelligence_report(
        {},
        candidate_origin="pending_retry_validation",
        persist_results=False,
    ) == ("PRE_RETRY_MANUSCRIPT", "rejected")

    p2 = _pipeline(generator_result=None, trigger_retry=False)
    run382.install(p2)
    assert p2.generate_intelligence_report(
        {},
        candidate_origin="pending_retry_validation",
        persist_results=False,
    ) is None


def test_negated_complete_claim_is_not_intro_overclaim():
    p = _gate_pipeline(["intro_overclaim"])
    run382.install(p)
    state, issues = p.validate_publication_readiness_gate(
        {"note_draft": "この方式だけで問題を完全には防げない。まず限定検証が必要です。"},
        "prototype research",
        {},
    )
    assert state == "PASS"
    assert issues == []


def test_limited_must_claim_is_not_intro_overclaim():
    p = _gate_pipeline(["intro_overclaim"])
    run382.install(p)
    state, issues = p.validate_publication_readiness_gate(
        {"note_draft": "この結果が必ず本番でも再現するとは限らない。研究条件の確認が必要です。"},
        "experimental abstract",
        {},
    )
    assert state == "PASS"
    assert issues == []


def test_positive_complete_claim_remains_blocked():
    p = _gate_pipeline(["intro_overclaim"])
    run382.install(p)
    state, issues = p.validate_publication_readiness_gate(
        {"note_draft": "この新方式なら従来の問題を完全に解決できます。"},
        "prototype research",
        {},
    )
    assert state == "REVIEW"
    assert issues == ["intro_overclaim"]


def test_one_positive_strong_claim_keeps_review_even_if_another_is_negated():
    p = _gate_pipeline(["intro_overclaim"])
    run382.install(p)
    state, issues = p.validate_publication_readiness_gate(
        {"note_draft": "必ず成功するとは限らない。ただし開発を変える技術です。"},
        "experimental abstract",
        {},
    )
    assert state == "REVIEW"
    assert issues == ["intro_overclaim"]


def test_other_publication_issues_are_never_removed():
    p = _gate_pipeline(["intro_overclaim", "headline_overclaim"])
    run382.install(p)
    state, issues = p.validate_publication_readiness_gate(
        {"note_draft": "この方式だけで問題を完全には防げない。"},
        "prototype",
        {},
    )
    assert state == "REVIEW"
    assert issues == ["headline_overclaim"]
