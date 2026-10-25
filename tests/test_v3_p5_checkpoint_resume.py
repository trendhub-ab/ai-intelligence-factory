"""P5 no-provider encrypted restart regression: secrets never enter logs."""
import json
from pathlib import Path

from cryptography.fernet import Fernet
import pytest

from experiments import v3_p5_checkpoint as cp
from experiments import v3_p5_confidential_handoff as handoff
from experiments import v3_p5_controlled_ablation as exp
from tests.test_v3_p5_controlled_ablation import sample


def checkpoint_fixture(tmp_path, monkeypatch):
    arms = exp.build_arms(mixed_models=True)
    def sender(arm):
        sender.request_attempts += 1
        if arm.code == "B":
            raise RuntimeError("simulated provider")
        return sample(), arm.model
    sender.request_attempts = 0
    sender.max_request_attempts = 8
    output = tmp_path / "private"
    with pytest.raises(RuntimeError, match="simulated provider"):
        exp.run_private(arms, output, sender, sleep=lambda _: None)
    assert sender.request_attempts == 2
    raw = (output / "Candidate_" +
        "A") if False else next(output.glob("Candidate_*.md"))
    orig = raw.read_bytes()
    calls = []
    def fake_telegram(token, method, fields):
        calls.append((method, fields))
        return {"id": 987, "type": "private"} if method == "getChat" else {"message_id": 1}
    monkeypatch.setattr(handoff, "_telegram_request", fake_telegram)
    encrypted = tmp_path / "checkpoint.fernet"
    handoff.encrypt_and_deliver(
        output, encrypted, token="bot", chat_id="987",
        run_id="12345", allow_partial=True,
    )
    msg = calls[-1][1]["text"]
    key = msg.split("Fernet key: ")[1].splitlines()[0]
    return arms, output, encrypted, key, orig


def test_failure_partial_is_encrypted_and_resumes_only_missing_arms(tmp_path, monkeypatch):
    arms, old, encrypted, secret_key, original_article = checkpoint_fixture(
        tmp_path, monkeypatch)
    assert b"Candidate_" not in encrypted.read_bytes()
    before = json.loads((old / "manifest.json").read_text())
    key = json.loads((old / "KEY_OPEN_AFTER_SCORING.json").read_text())
    first_label = key["A"]
    assert before["gemini_requests"] == 2
    completed = []
    def sender(arm):
        completed.append(arm.code)
        sender.request_attempts += 1
        return sample(), arm.model
    sender.request_attempts = 0
    sender.max_request_attempts = 8
    out = tmp_path / "resumed"
    final = exp.run_private(
        arms, out, sender, sleep=lambda _: None,
        resume_bundle=encrypted, resume_key=secret_key,
    )
    assert completed == ["B", "C", "D", "E"]
    assert final["gemini_requests"] == 6
    assert final["status"] == "ALL_VALID_AWAITING_BLIND_HUMAN_REVIEW"
    assert (out / f"Candidate_{first_label}.md").read_bytes() == original_article
    after = json.loads((out / "KEY_OPEN_AFTER_SCORING.json").read_text())
    assert {arm: after[arm] for arm in "ABCDE"} == {
        arm: key[arm] for arm in "ABCDE"}
    assert after["__actual_models_by_arm__"] == {
        "A": exp.FALLBACK_MODEL if key["__fallback_used_by_arm__"]["A"] else exp.MODEL,
        "B": exp.FALLBACK_MODEL, "C": exp.MODEL,
        "D": exp.FALLBACK_MODEL, "E": exp.MODEL,
    }


def test_resume_wrong_key_fails_before_creating_private_output(tmp_path, monkeypatch):
    arms, old, encrypted, secret_key, _ = checkpoint_fixture(tmp_path, monkeypatch)
    dest = tmp_path / "bad"
    with pytest.raises(cp.CheckpointError, match="authentication failed"):
        exp.run_private(
            arms, dest, lambda _: pytest.fail("no provider"),
            resume_bundle=encrypted, resume_key=Fernet.generate_key().decode())
    assert not dest.exists()


def test_checkpoint_change_of_prompt_fails_closed(tmp_path, monkeypatch):
    arms, old, encrypted, secret_key, _ = checkpoint_fixture(tmp_path, monkeypatch)
    from dataclasses import replace
    tampered = tuple(replace(a, prompt=a.prompt+" changed") if a.code == "B"
                     else a for a in arms)
    with pytest.raises(cp.CheckpointError, match="contract mismatch"):
        exp.run_private(
            tampered, tmp_path/"bad-contract",
            lambda _: pytest.fail("no provider"), resume_bundle=encrypted,
            resume_key=secret_key)


def test_partial_artifact_not_review_approved(tmp_path, monkeypatch):
    arms, old, encrypted, key, _ = checkpoint_fixture(tmp_path, monkeypatch)
    assert json.loads((old / "manifest.json").read_text())["status"] == (
        "INCOMPLETE_TECHNICAL_NO_GO")
    with pytest.raises(handoff.ConfidentialHandoffError, match="incomplete"):
        handoff.encrypt_and_deliver(
            old, tmp_path/"wrong.fernet", token="bot", chat_id="987",
            run_id="999", allow_partial=False)


def test_cumulative_limit_blocks_retries_before_future_arms(tmp_path, monkeypatch):
    arms, old, encrypted, key, _ = checkpoint_fixture(tmp_path, monkeypatch)
    calls = []
    def sender(arm):
        calls.append(arm.code)
        sender.request_attempts += 1
        return sample(), arm.model
    sender.request_attempts = 0
    sender.max_request_attempts = 8
    report = exp.run_private(arms, tmp_path/"limit", sender, sleep=lambda _: None,
                             resume_bundle=encrypted, resume_key=key)
    assert report["gemini_requests"] == 6
    assert sender.max_request_attempts == 6
