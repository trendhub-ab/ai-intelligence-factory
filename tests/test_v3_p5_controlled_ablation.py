"""Provider-free proof of P5 creative call ablation: NEVER touches Gemini."""
import json
import os
from types import SimpleNamespace

import pytest

from experiments import v3_p5_controlled_ablation as exp


def test_exact_case_and_stepwise_prompt_config_differences():
    a, b, c, d, e = exp.build_arms()
    assert [x.code for x in (a, b, c, d, e)] == list("ABCDE")
    assert [x.transport for x in (a, b, c, d, e)] == [
        "generate_content", "chat", "chat", "chat", "chat",
    ]
    assert a.prompt == b.prompt == c.prompt
    assert d.prompt == e.prompt
    assert d.prompt != c.prompt
    assert d.prompt.startswith(a.prompt.rstrip())
    assert a.config is b.config is None
    assert c.config == d.config == e.config == {
        "thinking_config": {"thinking_level": "low"}
    }
    assert exp.MODEL == "gemini-3.8-flash"


def test_no_api_default_with_no_credentials(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["p5"])
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GH_PAT", raising=False)
    exp.main()
    m = json.loads(capsys.readouterr().out)
    assert m["status"] == "PROVIDER_FREE_PREFLIGHT"
    assert m["arms"] == ["A", "B", "C", "D"]
    assert m["gemini_requests"] == 0
    assert m["publication_approved"] is False
    assert m["human_quality_approved"] is False
    assert m["prompt_sha256"]["A"] == m["prompt_sha256"]["B"]


def sample():
    rows = {
        "Writer Reaction": "不思議な点を考える。",
        "Editorial Discovery": "根拠を調べる。",
        "Cognitive Shift": "理解が変わる。",
        "Persona Article Generation": "# 記事\n\n根拠を詳しく確かめる。",
        "Fact-Safe Review": "# 記事\n\n根拠を詳しく確かめる。",
    }
    return SimpleNamespace(text=json.dumps(rows, ensure_ascii=False))


def test_mock_sender_private_blind_only(tmp_path):
    attempts, delays = [], []
    def fake(arm):
        attempts.append(arm.code)
        return sample()
    output = tmp_path / "private-blind"
    result = exp.run_private(
        exp.build_arms()[:4], output, fake,
        sleep=lambda sec: delays.append(sec),
    )
    assert attempts == list("ABCD")
    assert delays == [exp.PACE_SECONDS] * 3
    assert result["status"] == "ALL_VALID_AWAITING_BLIND_HUMAN_REVIEW"
    assert result["gemini_requests"] == 4
    assert len(list(output.glob("Candidate_*.md"))) == 4
    assert len(list(output.glob("Stages_Candidate_*.json"))) == 4
    for stage_file in output.glob("Stages_Candidate_*.json"):
        stages = json.loads(stage_file.read_text())
        assert len(stages) == 5
        assert "Persona Article Generation" in stages
        assert "Fact-Safe Review" in stages
    assert all(item["writing_stage_chars"] > 0 for item in result["candidates"].values())
    assert all(item["review_stage_chars"] > 0 for item in result["candidates"].values())
    assert (output / "KEY_OPEN_AFTER_SCORING.json").exists()
    assert (output / "manifest.json").exists()
    assert os.stat(output).st_mode & 0o077 == 0
    for file in output.iterdir():
        assert os.stat(file).st_mode & 0o077 == 0


def test_failure_stops_without_fallback_or_publishing(tmp_path):
    attempts = []
    def fake(arm):
        attempts.append(arm.code)
        if arm.code == "B":
            raise RuntimeError("503")
        return sample()
    output = tmp_path / "partial"
    with pytest.raises(RuntimeError, match="503"):
        exp.run_private(exp.build_arms()[:4], output, fake, sleep=lambda _: None)
    assert attempts == ["A", "B"]
    m = json.loads((output / "manifest.json").read_text())
    assert m["status"] == "INCOMPLETE_TECHNICAL_NO_GO"
    assert m["gemini_requests"] == 2
    assert m["publication_approved"] is False
    assert len(list(output.glob("Candidate_*.md"))) == 1
    assert len(list(output.glob("Stages_Candidate_*.json"))) == 1


def test_existing_directory_and_public_repo_blocked(tmp_path):
    with pytest.raises(RuntimeError, match="existing"):
        exp.private_directory(tmp_path)
    with pytest.raises(RuntimeError, match="public repository"):
        exp.private_directory(exp.REPO_ROOT / "bad-raw-articles")


@pytest.mark.parametrize("argv", [
    ["--live"],
    ["--live", "--confirm", "BAD_CONFIRMATION"],
])
def test_missing_manual_confirmation_never_calls_provider(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["p5", *argv])
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Manual confirmation"):
        exp.main()


def test_optional_e_is_explicit_and_still_no_api(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["p5", "--include-e"])
    exp.main()
    m = json.loads(capsys.readouterr().out)
    assert m["arms"] == ["A", "B", "C", "D", "E"]
    assert m["uses_extra_editor_persona"] is True
    assert m["gemini_requests"] == 0


def test_actions_live_mode_rejects_unprotected_manuscript(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", [
        "p5", "--live", "--confirm", exp.CONFIRM,
        "--private-output", str(tmp_path / "private"),
    ])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_ACTOR", "trendhub-ab")
    monkeypatch.delenv("AIIF_P5_CONFIDENTIAL_REVIEW", raising=False)
    with pytest.raises(RuntimeError, match="protected manual dispatch"):
        exp.main()


def test_live_manual_p5_has_no_clock_time_restriction(monkeypatch, tmp_path, capsys):
    """Explicit authorization and privacy controls remain; no time-of-day gate."""
    import inspect
    source = inspect.getsource(exp.main)
    assert "datetime.now" not in source
    assert "ZoneInfo" not in source
    assert "hour <" not in source
    assert "hour >" not in source

    called = []
    monkeypatch.setattr("sys.argv", [
        "p5", "--live", "--confirm", exp.CONFIRM, "--include-e",
        "--private-output", str(tmp_path / "unused-private-directory"),
    ])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(exp, "native_sender",
        lambda: (lambda arm: None, lambda: called.append("closed")))
    monkeypatch.setattr(exp, "run_private",
        lambda arms, target, send: (
            called.append(("run", len(arms), target)) or {"gemini_requests": len(arms)}
        ))
    exp.main()
    assert called[0][0:2] == ("run", 5)
    assert called[-1] == "closed"
    assert "requests=5" in capsys.readouterr().out


class ProviderStatus(RuntimeError):
    def __init__(self, code):
        super().__init__("structured provider response")
        self.status_code = code


def test_mixed_model_plan_retains_original_prompts_and_stage_order():
    normal = exp.build_arms()
    mixed = exp.build_arms(mixed_models=True)
    assert [(x.code, x.prompt, x.transport, x.config) for x in mixed] == [
        (x.code, x.prompt, x.transport, x.config) for x in normal
    ]
    assert [x.model for x in mixed] == [
        exp.MODEL, exp.FALLBACK_MODEL, exp.MODEL,
        exp.FALLBACK_MODEL, exp.MODEL,
    ]
    manifest = exp.manifest_for(mixed)
    assert manifest["model"] == "MIXED"
    assert manifest["max_provider_requests"] == 8
    assert manifest["gemini_requests"] == 0


@pytest.mark.parametrize("code", [404, 429, 503])
def test_recognized_provider_error_retries_once_with_fallback(code):
    attempts, sleeps = [], []
    arm = exp.build_arms()[0]

    def attempt(_, model):
        attempts.append(model)
        if model == exp.MODEL:
            raise ProviderStatus(code)
        return sample()

    response, actual = exp.dispatch_with_fallback(
        arm, attempt, sleep=lambda seconds: sleeps.append(seconds)
    )
    assert response.text
    assert actual == exp.FALLBACK_MODEL
    assert attempts == [exp.MODEL, exp.FALLBACK_MODEL]
    assert sleeps == [exp.PACE_SECONDS]


@pytest.mark.parametrize("code", [400, 401, 403, 409, 500])
def test_non_eligible_error_must_not_retry(code):
    models = []

    def attempt(_, model):
        models.append(model)
        raise ProviderStatus(code)

    with pytest.raises(ProviderStatus):
        exp.dispatch_with_fallback(
            exp.build_arms()[0], attempt, sleep=lambda _: None
        )
    assert models == [exp.MODEL]


def test_unstructured_503_text_must_not_trigger_fallback():
    attempts = []

    def attempt(_, model):
        attempts.append(model)
        raise RuntimeError("503 not a structured provider status")

    with pytest.raises(RuntimeError):
        exp.dispatch_with_fallback(
            exp.build_arms()[0], attempt, sleep=lambda _: None
        )
    assert attempts == [exp.MODEL]


def test_36_primary_never_falls_back_to_38():
    arm = exp.build_arms(mixed_models=True)[1]
    assert arm.model == exp.FALLBACK_MODEL
    attempts = []

    def attempt(_, model):
        attempts.append(model)
        raise ProviderStatus(503)

    with pytest.raises(ProviderStatus):
        exp.dispatch_with_fallback(arm, attempt, sleep=lambda _: None)
    assert attempts == [exp.FALLBACK_MODEL]


def test_fallback_count_and_actual_models_are_private(tmp_path):
    arms = exp.build_arms(mixed_models=True)
    called = []

    def sender(arm):
        primary = arm.model
        sender.request_attempts += 1
        called.append(primary)
        if arm.code == "C":
            sender.request_attempts += 1
            called.append(exp.FALLBACK_MODEL)
            return sample(), exp.FALLBACK_MODEL
        return sample(), primary

    sender.request_attempts = 0
    out = tmp_path / "model-aware-review"
    report = exp.run_private(arms, out, sender, sleep=lambda _: None)
    assert report["gemini_requests"] == 6
    assert len(report["candidates"]) == 5
    assert "__actual_models_by_arm__" not in report
    key = json.loads((out / "KEY_OPEN_AFTER_SCORING.json").read_text())
    assert key["__actual_models_by_arm__"]["C"] == exp.FALLBACK_MODEL
    assert key["__fallback_used_by_arm__"]["C"] is True
    assert key["__fallback_used_by_arm__"]["D"] is False
    assert called == [exp.MODEL, exp.FALLBACK_MODEL,
                      exp.MODEL, exp.FALLBACK_MODEL,
                      exp.FALLBACK_MODEL, exp.MODEL]


def test_mix_flag_default_does_not_send_provider(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["p5", "--include-e", "--mix-models"])
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    exp.main()
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["arms"] == list("ABCDE")
    assert manifest["model"] == "MIXED"
    assert manifest["gemini_requests"] == 0
