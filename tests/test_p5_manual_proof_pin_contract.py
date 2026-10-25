"""Provider-free regression for reviewed P5 manual proof's immutable source pin.

This test must NEVER call Gemini or dispatch Actions. Any experimental source
change requires a separately reviewed pin update (and human authorization).
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/p5-creative-ablation-manual.yml"
CHATOPS = ROOT / ".github/workflows/chatops-one-shot.yml"
REVIEWED_P5_SHA = "9e76864d2d3d31facae881a05356b941e3cc9fe3"
RETIRED_P5_SHA = "922ef5b49b76683529957d37ead155d459e886dc"


def test_p5_manual_checkout_and_verification_use_same_reviewed_immutable_commit():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    chatops = CHATOPS.read_text(encoding="utf-8")
    assert workflow.count(REVIEWED_P5_SHA) == 2, "pin and HEAD verification must agree"
    assert "ref: " + REVIEWED_P5_SHA in workflow
    assert 'test "$(git rev-parse HEAD)" = \'%s\'' % REVIEWED_P5_SHA in workflow
    assert chatops.count(REVIEWED_P5_SHA) == 1, "ChatOps audit must report actual checked-out SHA"
    assert RETIRED_P5_SHA not in workflow + chatops


def test_p5_proof_stays_manual_private_and_capped_after_pin_update():
    text = WORKFLOW.read_text(encoding="utf-8")
    header = text.split("permissions:", 1)[0]
    assert re.search(r"(?m)^  workflow_dispatch:", header)
    for event in ("push", "pull_request", "pull_request_target", "schedule",
                  "workflow_run", "issue_comment"):
        assert not re.search(rf"(?m)^  {event}:", header)
    assert "github.actor == 'trendhub-ab'" in text
    assert "github.run_attempt == 1" in text
    assert "inputs.confirm == 'RUN_P5_ABLATION_ONCE'" in text
    assert "group: ai-intelligence-gemini-budget" in text
    assert "GEMINI_COUNTER_BRANCH: runtime-state" in text
    assert "GEMINI_PERSISTENT_DAILY_COUNTER: 'true'" in text
    assert "GEMINI_DAILY_REQUEST_BUDGET: '8'" not in text
    assert "GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET: '8'" not in text
    assert "AIIF_P5_CONFIDENTIAL_REVIEW: fernet_telegram_private" in text
    assert "persist-credentials: false" in text
    assert "--include-e --mix-models" in text
    assert "max 8 attempts" not in text
    assert "v3_p5_checkpoint_resume" in text
    assert "No P5-local 8-call cap" in text
    assert (text.index("Check recipient is truly private before ANY Gemini send")
            < text.index("Generate A B C D E with bounded model fallback"))
    assert (text.index("Encrypt manuscripts and deliver separate one-time key privately")
            < text.index("Upload encrypted review bundle ONLY"))
    assert "actions/upload-artifact@v4" in text
    assert "retention-days: 7" in text
    assert "resume_run_id:" in text
    assert "secrets.P5_RESUME_FERNET_KEY" in text
    assert "AIIF_P5_ALLOW_PARTIAL:" in text
    assert "steps.generate.outcome == 'failure'" in text
    assert "always() && steps.seal.outcome == 'success'" in text
    assert "gh run download" in text
    assert "Untrusted prior P5 run" in text
    assert "AIIF_P5_RESUME_BUNDLE" in text
    assert "--resume-bundle" in text


def test_p5_chatops_remains_owner_only_exact_one_shot():
    text = CHATOPS.read_text(encoding="utf-8")
    assert "github.event.issue.number == 71" in text
    assert "github.event.issue.pull_request == null" in text
    assert "github.event.comment.user.login == 'trendhub-ab'" in text
    assert "github.actor == 'trendhub-ab'" in text
    assert "github.run_attempt == 1" in text
    assert "github.event.comment.body == '/aiif run p5_ablation_once'" in text
    assert "target='p5-creative-ablation-manual.yml'" in text
    assert 'RUN_P5_ABLATION_ONCE' in text
