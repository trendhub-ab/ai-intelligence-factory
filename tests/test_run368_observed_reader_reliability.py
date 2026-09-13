from __future__ import annotations

from types import SimpleNamespace

import run203_runtime_state_channel as runtime_state
import run228_reader_rhythm_planning as reader_rhythm


class _Response:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _Http:
    def __init__(self, responses):
        self.responses = list(responses)
        self.put_calls = 0

    def put(self, _url, **_kwargs):
        self.put_calls += 1
        return self.responses.pop(0)


def test_runtime_rule_timeout_retries_once_then_succeeds():
    http = _Http([
        _Response(409, "Repository rule violations found\nTimed out validating rule, please try again"),
        _Response(201, "created"),
    ])
    delays = []

    result = runtime_state._put_with_runtime_rule_retry(
        http,
        "https://api.github.test/runtime-state",
        headers={},
        payload={},
        timeout=30,
        sleep_fn=delays.append,
    )

    assert result.status_code == 201
    assert http.put_calls == 2
    assert delays == [1.0]


def test_non_transient_409_is_not_retried():
    http = _Http([
        _Response(409, "sha does not match current blob"),
        _Response(201, "must not be reached"),
    ])
    delays = []

    result = runtime_state._put_with_runtime_rule_retry(
        http,
        "https://api.github.test/runtime-state",
        headers={},
        payload={},
        timeout=30,
        sleep_fn=delays.append,
    )

    assert result.status_code == 409
    assert http.put_calls == 1
    assert delays == []


def test_permission_failure_is_not_retried():
    http = _Http([
        _Response(403, "Resource not accessible by integration"),
        _Response(201, "must not be reached"),
    ])

    result = runtime_state._put_with_runtime_rule_retry(
        http,
        "https://api.github.test/runtime-state",
        headers={},
        payload={},
        timeout=30,
        sleep_fn=lambda _delay: None,
    )

    assert result.status_code == 403
    assert http.put_calls == 1


def test_runtime_rule_timeout_stops_after_three_puts():
    transient = "Repository rule violations found\nTimed out validating rule, please try again"
    http = _Http([_Response(409, transient), _Response(409, transient), _Response(409, transient)])
    delays = []

    result = runtime_state._put_with_runtime_rule_retry(
        http,
        "https://api.github.test/runtime-state",
        headers={},
        payload={},
        timeout=30,
        sleep_fn=delays.append,
    )

    assert result.status_code == 409
    assert http.put_calls == 3
    assert delays == [1.0, 2.0]


def test_reader_final_check_is_last_and_evidence_safe():
    prompt = reader_rhythm.augment_prompt("BASE PROMPT")

    assert reader_rhythm.RUN228_MARKER in prompt
    assert reader_rhythm.RUN368_FINAL_READER_CHECK_MARKER in prompt
    assert prompt.rstrip().endswith("読みやすさを理由に根拠を強めたり欠落を埋めたりしない。")
    assert "Evidence・重要数値・条件・反証・Decisionは削らない" in prompt
    assert "新しいFact、因果、数値、利用経験、保証、競合情報を作らない" in prompt
    assert "Fact/Evidence安全境界を優先" in prompt


def test_reader_prompt_augmentation_is_idempotent():
    once = reader_rhythm.augment_prompt("BASE PROMPT")
    twice = reader_rhythm.augment_prompt(once)

    assert twice.count(reader_rhythm.RUN228_MARKER) == 1
    assert twice.count(reader_rhythm.RUN368_FINAL_READER_CHECK_MARKER) == 1
    assert twice == once


def test_reader_install_adds_no_provider_call_surface():
    calls = []

    def base_prompt(*_args, **_kwargs):
        calls.append("prompt")
        return "BASE"

    fake_pipeline = SimpleNamespace(build_decision_prompt=base_prompt)
    reader_rhythm.install(fake_pipeline)

    result = fake_pipeline.build_decision_prompt()
    assert calls == ["prompt"]
    assert reader_rhythm.RUN368_FINAL_READER_CHECK_MARKER in result
    assert getattr(fake_pipeline, reader_rhythm.RUN368_FINAL_READER_CHECK_MARKER) is True
