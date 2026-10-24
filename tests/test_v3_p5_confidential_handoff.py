"""Provider-free privacy tests for Telegram-keyed P5 encrypted handoff."""
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from experiments import v3_p5_confidential_handoff as handoff


def make_case(tmp_path, n=4):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    files = {"manifest.json": json.dumps({
        "status": "ALL_VALID_AWAITING_BLIND_HUMAN_REVIEW",
        "arms": list("ABCDE"[:n]), "gemini_requests": n,
    }), "KEY_OPEN_AFTER_SCORING.json": '{"A":"B"}'}
    for i in range(n):
        files["Candidate_" + str(i) + ".md"] = "# 私用記事\n本文"
        files["Stages_Candidate_" + str(i) + ".json"] = '{"Fact-Safe Review":"未公開"}'
    for name, text in files.items():
        file = root / name
        file.write_text(text, encoding="utf-8")
        file.chmod(0o600)
    return root


def fake_telegram(monkeypatch, kind="private"):
    calls = []
    def stub(token, method, fields):
        calls.append((token, method, dict(fields)))
        if method == "getChat":
            return {"type": kind, "id": 1234}
        return {"message_id": 99}
    monkeypatch.setattr(handoff, "_telegram_request", stub)
    return calls


def test_private_chat_only(monkeypatch):
    calls = fake_telegram(monkeypatch, kind="group")
    with pytest.raises(handoff.ConfidentialHandoffError, match="Refusing group"):
        handoff.assert_private_chat("BOT", "1234")
    assert [x[1] for x in calls] == ["getChat"]


def test_encrypted_artifact_contains_private_5_stages_but_no_plaintext(monkeypatch, tmp_path):
    calls = fake_telegram(monkeypatch)
    root = make_case(tmp_path, n=5)
    target = tmp_path / "encrypted-review.fernet"
    handoff.encrypt_and_deliver(
        root, target, token="BOT", chat_id="1234", run_id="9001",
    )
    assert target.exists()
    assert os.stat(target).st_mode & 0o077 == 0
    assert b"\xe6\x9c\xac\xe6\x96\x87" not in target.read_bytes()
    key_message = calls[-1][2]["text"]
    assert "9001" in key_message
    key = key_message.split("Fernet key: ")[1].splitlines()[0].encode()
    decrypted = Fernet(key).decrypt(target.read_bytes())
    with zipfile.ZipFile(io.BytesIO(decrypted)) as z:
        names = z.namelist()
        assert len(names) == 12
        assert "KEY_OPEN_AFTER_SCORING.json" in names
        assert "Stages_Candidate_0.json" in names
        assert "Candidate_0.md" in names
    assert all(x[1] in ("getChat", "sendMessage") for x in calls)


def test_missing_stage_or_extra_file_never_delivers(monkeypatch, tmp_path):
    calls = fake_telegram(monkeypatch)
    root = make_case(tmp_path)
    (root / "Stages_Candidate_0.json").unlink()
    with pytest.raises(handoff.ConfidentialHandoffError, match="Incomplete"):
        handoff.encrypt_and_deliver(root, tmp_path / "secret.fernet",
                                    token="BOT", chat_id="1234", run_id="1")
    assert not (tmp_path / "secret.fernet").exists()
    assert not any(x[1] == "sendMessage" for x in calls)


def test_telegram_delivery_failure_deletes_encrypted_file(monkeypatch, tmp_path):
    root = make_case(tmp_path)
    def fail(token, method, fields):
        if method == "getChat":
            return {"type": "private", "id": 1234}
        raise handoff.ConfidentialHandoffError("fail")
    monkeypatch.setattr(handoff, "_telegram_request", fail)
    destination = tmp_path / "review.fernet"
    with pytest.raises(handoff.ConfidentialHandoffError):
        handoff.encrypt_and_deliver(root, destination,
                                    token="BOT", chat_id="1234", run_id="1")
    assert not destination.exists()


def test_preflight_never_generates_article_or_contacts_gemini(monkeypatch, capsys):
    fake_telegram(monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1234")
    monkeypatch.setenv("AIIF_P5_HANDOFF_STAGE", "preflight")
    handoff.main()
    assert "PREFLIGHT_PASS_PRIVATE_CHAT" in capsys.readouterr().out


def test_no_automatic_trigger_or_rerun(monkeypatch):
    for variable, value in (
        ("GITHUB_ACTIONS", "true"),
        ("GITHUB_EVENT_NAME", "push"),
        ("GITHUB_RUN_ATTEMPT", "1"),
    ):
        monkeypatch.setenv(variable, value)
    with pytest.raises(handoff.ConfidentialHandoffError, match="manual dispatch"):
        handoff.main()
