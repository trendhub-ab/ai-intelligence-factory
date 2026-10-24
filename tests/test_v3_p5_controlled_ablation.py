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
