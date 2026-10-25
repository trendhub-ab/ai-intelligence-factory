"""P5 no-provider encrypted restart regression: secrets never enter logs."""
import json
from pathlib import Path

from cryptography.fernet import Fernet
import pytest

from experiments import v3_p5_checkpoint as cp
from experiments import v3_p5_confidential_handoff as handoff
from experiments import v3_p5_controlled_ablation as exp
from types import SimpleNamespace


def sample():
    rows = {
        "Writer Reaction": "不思議な点を考える。",
        "Editorial Discovery": "根拠を調べる。",
        "Cognitive Shift": "理解が変わる。",
        "Persona Article Generation": "# 記事\n\n根拠を詳しく確かめる。",
        "Fact-Safe Review": "# 記事\n\n根拠を詳しく確かめる。",
    }
    return SimpleNamespace(text=json.dumps(rows, ensure_ascii=False))


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
    raw = next(output.glob("Candidate_*.md"))
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
    key = msg.split("Fernet key: ", 1)[1][:44]
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


def test_cumulative_requests_remain_auditable_without_experiment_cap(tmp_path, monkeypatch):
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
    assert sender.max_request_attempts is None


def test_bad_fifth_json_is_not_checkpointed_as_completed_arm(tmp_path, monkeypatch):
    from types import SimpleNamespace
    arms = exp.build_arms(mixed_models=True)
    calls = []

    def sender(arm):
        sender.request_attempts += 1
        calls.append(arm.code)
        return (SimpleNamespace(text='{"Writer Reaction": incomplete'), arm.model
                ) if arm.code == "E" else (sample(), arm.model)

    sender.request_attempts = 0
    out = tmp_path / "bad-fifth"
    with pytest.raises(Exception):
        exp.run_private(arms, out, sender, sleep=lambda _: None)
    m = json.loads((out / "manifest.json").read_text())
    key = json.loads((out / "KEY_OPEN_AFTER_SCORING.json").read_text())
    assert m["status"] == "INCOMPLETE_TECHNICAL_NO_GO"
    assert m["gemini_requests"] == 5
    assert set(key["__actual_models_by_arm__"]) == set("ABCD")
    assert len(m["candidates"]) == 4
    assert len(list(out.glob("Candidate_*.md"))) == 4
    assert calls == list("ABCDE")

    sent = []
    def fake(token, method, fields):
        sent.append(method)
        return {"type": "private", "id": 987} if method == "getChat" else {"message_id": 1}
    monkeypatch.setattr(handoff, "_telegram_request", fake)
    encrypted = tmp_path / "valid-prefix.fernet"
    handoff.encrypt_and_deliver(
        out, encrypted, token="bot", chat_id="987",
        run_id="3344", allow_partial=True)
    assert encrypted.exists()
    assert sent == ["getChat", "sendMessage"]


def test_legacy_eight_request_checkpoint_resumes_only_e(tmp_path, monkeypatch):
    """An authenticated legacy eight-attempt checkpoint must not regenerate A-D."""
    arms = exp.build_arms(mixed_models=True)
    old = tmp_path / "legacy-private"

    def previous(arm):
        previous.request_attempts += 2 if arm.code in ("B", "C", "E") else 1
        if arm.code == "E":
            raise RuntimeError("simulated 503 after E fallback")
        return sample(), arm.model

    previous.request_attempts = 0
    with pytest.raises(RuntimeError, match="simulated 503"):
        exp.run_private(arms, old, previous, sleep=lambda _: None)
    prior_manifest = json.loads((old / "manifest.json").read_text())
    assert prior_manifest["gemini_requests"] == 8
    assert len(prior_manifest["candidates"]) == 4
    prior_blind_key = json.loads((old / "KEY_OPEN_AFTER_SCORING.json").read_text())
    prior_articles = {p.name: p.read_bytes() for p in old.glob("Candidate_*.md")}
    # Recreate the old v1 manifest, without changing manuscript hashes or mapping.
    prior_manifest["max_provider_requests"] = 8
    (old / "manifest.json").write_text(json.dumps(prior_manifest), encoding="utf-8")

    sent = []
    def private_telegram(token, method, fields):
        sent.append((method, fields))
        return {"id": 987, "type": "private"} if method == "getChat" else {"message_id": 1}
    monkeypatch.setattr(handoff, "_telegram_request", private_telegram)
    encrypted = tmp_path / "legacy-eight.fernet"
    handoff.encrypt_and_deliver(old, encrypted, token="bot", chat_id="987",
                                run_id="40178724927", allow_partial=True)
    secret_key = sent[-1][1]["text"].split("Fernet key: ", 1)[1][:44]

    resumed_arms = []
    def only_missing(arm):
        resumed_arms.append(arm.code)
        only_missing.request_attempts += 1
        return sample(), arm.model
    only_missing.request_attempts = 0
    report = exp.run_private(arms, tmp_path / "resumed-eight", only_missing,
                             sleep=lambda _: None, resume_bundle=encrypted,
                             resume_key=secret_key)
    assert resumed_arms == ["E"]
    assert report["gemini_requests"] == 9
    assert report["max_provider_requests"] is None
    assert report["legacy_checkpoint_max_provider_requests"] == 8
    assert report["status"] == "ALL_VALID_AWAITING_BLIND_HUMAN_REVIEW"
    for name, content in prior_articles.items():
        assert (tmp_path / "resumed-eight" / name).read_bytes() == content
    resumed_key = json.loads((tmp_path / "resumed-eight" /
                              "KEY_OPEN_AFTER_SCORING.json").read_text())
    assert {arm: resumed_key[arm] for arm in "ABCDE"} == {
        arm: prior_blind_key[arm] for arm in "ABCDE"}
