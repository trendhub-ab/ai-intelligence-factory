"""Run382/383: preserve retry specimens and remove one proven intro false positive.

Run382 keeps the last valid pre-retry manuscript available to read-only validation when a
provider fails before returning a replacement. Run383 adds a publication-gate precision
contract for the same failure family exposed by Run381: a strong word in the introduction
must not count as overclaim when that exact claim is explicitly rejected or limited.

Neither contract weakens Fact/Evidence. Positive strong claims remain REVIEW, and the retry
snapshot can never promote a manuscript or write through a Production persistence path.
"""
from __future__ import annotations

import re
from typing import Any

SNAPSHOT_ATTR = "_run382_pre_retry_snapshot"
_INSTALLED_ATTR = "_run382_retry_snapshot_installed"
_READ_ONLY_ORIGINS = frozenset({"pending_retry_validation", "article_revalidation"})
_INTRO_STRONG_RE = re.compile(
    r"(?:革命的|圧倒的|ゲームチェンジャー|世界初|世界最速|必ず|完全に|従来技術を終わらせ|開発を変える)"
)


def clear_snapshot(pipeline_module: Any) -> None:
    setattr(pipeline_module, SNAPSHOT_ATTR, None)


def peek_snapshot(pipeline_module: Any) -> dict[str, str] | None:
    value = getattr(pipeline_module, SNAPSHOT_ATTR, None)
    return dict(value) if isinstance(value, dict) else None


def consume_snapshot(pipeline_module: Any) -> dict[str, str] | None:
    value = peek_snapshot(pipeline_module)
    clear_snapshot(pipeline_module)
    return value


def _capture_from_prompt_call(pipeline_module: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    # Canonical signature: name, url, stars, desc, quality_feedback, ...,
    # previous_article=<...>. Retry calls use previous_article as a keyword today.
    feedback = str(kwargs.get("quality_feedback") or (args[4] if len(args) > 4 else "") or "").strip()
    previous = str(kwargs.get("previous_article") or "").strip()
    if not feedback or not previous:
        return
    setattr(
        pipeline_module,
        SNAPSHOT_ATTR,
        {
            "manuscript": previous,
            "quality_feedback": feedback,
        },
    )


def _candidate_origin(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if "candidate_origin" in kwargs:
        return str(kwargs.get("candidate_origin") or "new")
    # generate_intelligence_report positional order:
    # repo, notion_page_id, screening_score, screening_reason, persist_results,
    # candidate_rank, candidate_origin, ...
    return str(args[6] if len(args) > 6 else "new")


def _persist_results(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
    if "persist_results" in kwargs:
        return bool(kwargs.get("persist_results"))
    return bool(args[4]) if len(args) > 4 else True


def _sentence_around(text: str, start: int, end: int) -> str:
    body = str(text or "")
    left = max([body.rfind(mark, 0, start) for mark in "。！？!?\n"], default=-1) + 1
    rights = [pos for mark in "。！？!?\n" if (pos := body.find(mark, end)) >= 0]
    right = min(rights) + 1 if rights else len(body)
    return body[left:right].strip()


def _strong_intro_claim_is_explicitly_rejected(sentence: str, token: str) -> bool:
    """Return true only when the matched strong claim is visibly negated/limited."""
    s = re.sub(r"\s+", "", str(sentence or ""))
    t = re.escape(str(token or ""))
    if not s or not token or token not in s:
        return False

    generic_after = rf"{t}.{{0,32}}(?:ではない|ではありません|とは言えない|とはいえない|とは限らない|とは断定できない|とまでは言えない|わけではない|とは確認できない|とは確認されていない|保証されない|保証できない)"
    if re.search(generic_after, s):
        return True

    if token == "完全に" and re.search(
        r"完全に(?:は)?.{0,32}(?:ない|ません|できない|防げない|避けられない|保証されない|保証できない)",
        s,
    ):
        return True
    if token == "必ず" and re.search(
        r"必ず.{0,32}(?:とは限らない|わけではない|ではない|保証されない|保証できない)",
        s,
    ):
        return True
    return False


def _all_intro_strong_claims_are_explicitly_rejected(article: str) -> bool:
    intro = str(article or "")[:1200]
    matches = list(_INTRO_STRONG_RE.finditer(intro))
    if not matches:
        return False
    return all(
        _strong_intro_claim_is_explicitly_rejected(
            _sentence_around(intro, match.start(), match.end()), match.group(0)
        )
        for match in matches
    )


def _install_intro_overclaim_precision(pipeline_module: Any) -> None:
    original = getattr(pipeline_module, "validate_publication_readiness_gate", None)
    if not callable(original):
        return

    def validate_with_intro_precision(parsed: dict, source_context: str = "", source_info: dict | None = None):
        state, issues = original(parsed, source_context, source_info)
        issues = list(issues or [])
        if "intro_overclaim" not in issues:
            return state, issues
        article = str((parsed or {}).get("note_draft") or "")
        if not _all_intro_strong_claims_are_explicitly_rejected(article):
            return state, issues
        issues = [issue for issue in issues if issue != "intro_overclaim"]
        new_state = "REVIEW" if issues else "PASS"
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.info("[RUN383 INTRO OVERCLAIM PRECISION] removed explicitly rejected strong-claim false positive")
        return new_state, issues

    validate_with_intro_precision.__name__ = getattr(original, "__name__", "validate_publication_readiness_gate")
    validate_with_intro_precision.__doc__ = getattr(original, "__doc__", None)
    pipeline_module.validate_publication_readiness_gate = validate_with_intro_precision


def install(pipeline_module: Any) -> Any:
    """Install bounded retry preservation plus fail-closed intro-overclaim precision."""
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original_prompt = getattr(pipeline_module, "build_decision_prompt", None)
    original_generate = getattr(pipeline_module, "generate_intelligence_report", None)

    # Minimal test doubles and non-article runtimes may omit these callables. Run383's
    # publication precision can still install independently when its gate exists.
    if callable(original_prompt) and callable(original_generate):
        def prompt_with_snapshot(*args: Any, **kwargs: Any):
            _capture_from_prompt_call(pipeline_module, args, kwargs)
            return original_prompt(*args, **kwargs)

        prompt_with_snapshot.__name__ = getattr(original_prompt, "__name__", "build_decision_prompt")
        prompt_with_snapshot.__doc__ = getattr(original_prompt, "__doc__", None)
        pipeline_module.build_decision_prompt = prompt_with_snapshot

        def generate_with_snapshot(*args: Any, **kwargs: Any):
            origin = _candidate_origin(args, kwargs)
            persist = _persist_results(args, kwargs)
            clear_snapshot(pipeline_module)
            result = original_generate(*args, **kwargs)
            if result is not None:
                clear_snapshot(pipeline_module)
                return result
            if persist or origin not in _READ_ONLY_ORIGINS:
                clear_snapshot(pipeline_module)
                return None
            snapshot = consume_snapshot(pipeline_module) or {}
            manuscript = str(snapshot.get("manuscript") or "").strip()
            if not manuscript:
                return None
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning(
                    "[RUN382 RETRY SNAPSHOT PRESERVED] origin=%s chars=%s status=rejected persist=false",
                    origin,
                    len(manuscript),
                )
            return manuscript, "rejected"

        generate_with_snapshot.__name__ = getattr(original_generate, "__name__", "generate_intelligence_report")
        generate_with_snapshot.__doc__ = getattr(original_generate, "__doc__", None)
        pipeline_module.generate_intelligence_report = generate_with_snapshot
        clear_snapshot(pipeline_module)

    _install_intro_overclaim_precision(pipeline_module)
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
