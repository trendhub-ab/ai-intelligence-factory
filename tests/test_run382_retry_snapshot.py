from types import SimpleNamespace

import run382_retry_snapshot as run382


class _Logger:
    def __init__(self):
        self.messages = []

    def warning(self, message, *args):
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

    # Second candidate never enters a retry; stale snapshot must not leak.
    def no_retry(*args, **kwargs):
        return None

    # Replace the installed wrapper's underlying behavior by reinstalling a fresh fake
    # pipeline so this assertion exercises candidate isolation rather than monkeypatching
    # closure internals.
    p2 = _pipeline(generator_result=None, trigger_retry=False)
    run382.install(p2)
    assert p2.generate_intelligence_report(
        {},
        candidate_origin="pending_retry_validation",
        persist_results=False,
    ) is None
