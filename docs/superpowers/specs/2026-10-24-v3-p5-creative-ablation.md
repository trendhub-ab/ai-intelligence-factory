# P5 Creative-call Controlled Ablation — 2026-10-24 (DRAFT)

Scope: investigate why the old 83/100 P5 manuscript style was not reproduced after integration. NOT an article publication or a production release. Do not assert integration was the cause of the observed deterioration: the old reference used Gemini 3 Flash Preview, whereas later proof used Gemini 3.6/3.8, different API transport and source envelope.

## Exact controlled inputs

- Source/case: pinned Phase0 case "Your Transformer Is Secretly Elastic" from selected P5 baseline commit 95016a65701979063f56130bf181bca831661f5d.
- Model: gemini-3.8-flash for all arms, no fallback, Preview, or Lite.
- A/B/C use EXACT same original five-stage prompt. D/E append the existing integrated LocalSkills/management advice without rewriting the golden source fixture.
- One fresh request context per call, SDK attempts=1, 90s pacing, one logical call per arm. No fixed seed or sampling override: single results remain exploratory, NOT conclusive causality.
- Managed Decision Reason and Action in D/E are copied from the frozen Phase0 input, NOT obtained through a new management model call or a newly validated Evidence Gate.

## A/B/C/D/E staged intervention

| Arm | Provider transport | Prompt | Config |
|---|---|---|---|
| A | models.generate_content | original P5 | unspecified |
| B | fresh Chat + send_message | same as A | unspecified |
| C | fresh Chat | same as A | thinking_level=low |
| D | fresh Chat | managed extra LocalSkills/Action after original P5 prompt | thinking_level=low |
| E (optional) | fresh Chat | same as D | thinking_level=low, extra canonical AIIF Editor system persona AND max_output_tokens |

A→B probes transport; B→C probes low-thinking; C→D probes appended management instruction. D→E changes two things at once (system persona and output cap), therefore CANNOT isolate those individually. Actual integrated Production includes upstream management generation, content shaping, possible URL tools, and separate downstream Fact/Evidence/Publication gates: E is a creative-call approximation, NOT full end-to-end integration.

## Provider-free preflight

    python -m experiments.v3_p5_controlled_ablation
    python -m pytest -q tests/test_v3_p5_controlled_ablation.py

Preflight accesses no credentials and never sends API, note, Notion, or other external requests.

## OPTIONAL manual private live run

Requires both GH_PAT and GEMINI_API_KEY, native enabled repository-persistent counter, and an unused PRIVATE output directory outside repository. Gemini API execution is permitted at any hour. No clock-time restrictions apply; explicit manual authorization, private handoff, native per-model quota, and shared concurrency remain mandatory. Live proof is forbidden in GitHub Actions except when the reviewed manual-dispatch guard authorizes the exact owner, one-shot run, and a private Telegram-keyed Fernet handoff is confirmed before any Gemini send. Raw manuscripts stay inside RUNNER_TEMP. Only encrypted artifacts may be uploaded, and the encryption key goes exclusively to the existing Telegram bot chat after verifying it is a private chat; groups/channels fail closed. This handoff requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID. Failed chat preflight forbids any Gemini requests.

    python -m experiments.v3_p5_controlled_ablation --live --confirm RUN_P5_ABLATION_ONCE --private-output /private/path/p5-experiment-YYYYMMDD

Default four calls A/B/C/D maximum, optional fifth E with --include-e; no model fallback or API auto retry. Native per-request budget + persistent counter reserves before every real provider send. Ambiguous errors retain reservation. If any sample fails validation/response, stop, keep partial results private, report INCOMPLETE_TECHNICAL_NO_GO and do not rank the arms.

Outputs are mode 0700 directory, 0600 files: blindly labeled Candidate_*.md, Stages_Candidate_*.json, manifest.json, KEY_OPEN_AFTER_SCORING.json. The stages are kept strictly local and include Persona Article Generation versus Fact-Safe Review, enabling stage-by-stage analysis of any shortening. Never commit raw manuscripts, five-stage bundles, compressed equivalents, or identifying blind KEY into repository or public GitHub Actions artifacts. The live proof does not upload or publish anywhere.

## Blind scoring and limits

Evaluate each completed manuscript, without model/arm key: Opening 15, Writer-specific curiosity 15, Evidence-driven discovery 20, Cognitive shift 15, Natural Japanese 15, Memorability 10, claim restraint 10. Independently verify factual statements before any real Publication Gate. Scores are subjective and not Proof of model or integration causality. Independent repetitions (ideally >=3 per contrast, respecting quota) needed for robust attribution. No selection solely on content length or synthetic style-check metrics.

Do NOT modify main, V1/V2/Classic, Daily, note, Notion, publication gates, Gemini production resilience code. PR #862 is draft; this experiment is a separate stacked draft. NO MERGE absent explicit owner MERGE GO.


## Owner extension — 2026-10-25, mixed-model fallback (EXPERIMENT ONLY)

Owner explicitly authorized a controlled comparison where **gemini-3.8-flash**
falls back once to **gemini-3.6-flash** after a structured provider HTTP
404/429/503. No retry on local counter failures, invalid request, authentication,
unstructured errors, content-quality failure, parse failure, or exhausted budget.
Every provider attempt reserves the shared runtime-state counter *before* send;
the failed 3.8 request remains counted. 90-second spacing applies to fallback
attempts as well as arms. Maximum **8 provider attempts** per manual run
(5 article arms + at most 3 3.8-to-3.6 fallbacks). No cross-provider/API key changes.

With explicit `--mix-models`, planned primary models for A/B/C/D/E are
3.8 / 3.6 / 3.8 / 3.6 / 3.8 Flash. Actual model per arm and fallback flags
are stored **only** inside the private KEY_OPEN_AFTER_SCORING.json. The blind
Candidate_*.md and public Actions log must contain no arm-model map. This
five-arm mixture is **exploratory**, because model variation confounds arm
differences; do not interpret A–E ranking as a causal effect of transport or
editorial instruction. A future matched-arm, same-model repeated experiment
would be required for controlled model-to-model comparisons.

A successful run encrypts five manuscripts and stages; total provider
requests may be **5–8**. A failed or incomplete request sequence remains
`INCOMPLETE_TECHNICAL_NO_GO` and cannot ship any article review bundle.
Fernet key only goes to a Telegram recipient verified as private. No note,
Notion, publication-gate, existing Daily, Classic, or V1/V2 changes.

Previous single-model experiment source commit `922ef5b49b76683529957d37ead155d459e886dc`
remains historically valid, but cannot satisfy this new authorization by
itself. Do not execute the old pinned workflow expecting fallback.
Immutable source pin, audited ChatOps text, workflow request cap and tests
must all be updated together and reviewed before any owner-only run.

## 2026-10-25 — encrypted partial checkpoint and budget-aware resume (DRAFT)

Failure evidence: P5 Runs 40150657370, 40163148618 and 40171771740 failed.
Run 40163148618 received HTTP 200 for A–D and 200 for the E fallback,
but E's response failed strict five-stage JSON parsing; Run 40171771740
received 503 on B's 3.6-primary. Neither produced a review artifact.

**Must preserve:** Never loosen bundle JSON, source/evidence, Fact,
Publication, naturalness or blind scoring gates. Each arm is accepted
**only after** the five-stage JSON validates and private files are durable.
An invalid E response is not a finished manuscript.

On failure with at least one complete arm, allow the manual P5 Actions job
to seal the private RUNNER_TEMP prefix as a **Fernet-encrypted partial**
artifact and Telegram its random key **only** to the verified private chat.
This remains INCOMPLETE_TECHNICAL_NO_GO, never a review-ready article.
No raw drafts, prompt, blind key, intermediate stage or resume secret may go
to public logs, artifact names, outputs or workflow_dispatch inputs.

Optional owner-only manual resume requires previous FAILED run ID and
GitHub Actions repository secret P5_RESUME_FERNET_KEY filled with the
previously Telegram-delivered Fernet key. Retrieve only the named P5 artifact
from the same repository; verify origin and decrypt in runner.temp.
Authenticate the sealed bytes and fail-closed on missing, wrong or altered
key, unexpected files, corrupted SHA, non-prefix completed arms, wrong
prompt/config/source/model fingerprint, and excessive cumulative requests.
Preserve original blinded labels, stages, finished manuscripts and model
provenance, then call Gemini **only** for missing arms in A–E order.

Provider calls are independently budget-reserved by the canonical runtime
counter. At most eight **cumulative** actual provider attempts across resume
runs for this comparison. One 3.8→3.6 switch is allowed on structured
404/429/503; a structured 503/429 on 3.6 can retry on **3.6 only** with
bounded 90/180-second waits, never unlimited loops. Before retry, reserve
at least one possible call for each not-yet-attempted arm. Do not retry
on invalid JSON, quality problems, auth/permission errors or unstructured
text. Retrying an arm or starting a new Run does not grant more than eight
cumulative attempts once a checkpoint chain has begun.

The checkpoint artifact TTL is seven days; rotate/update
P5_RESUME_FERNET_KEY for each new partial checkpoint. GitHub does not
expose existing secrets for reading. An owner must intentionally configure
the secret through GitHub Actions settings prior to resume; no attempt to
pass the key in issue comments, plaintext dispatch parameters or logs.
The old failed runs, which never uploaded encrypted partial checkpoints,
are **not recoverable** under this protocol.

Production V1/V2/Daily/note/Notion stays unchanged. Do not merge or
dispatch any API without explicit owner approval following CI verification.
