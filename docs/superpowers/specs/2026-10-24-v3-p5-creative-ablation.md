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

Requires both GH_PAT and GEMINI_API_KEY, native enabled repository-persistent counter, and an unused PRIVATE output directory outside repository. Only after 17:00 JST. Live proof is explicitly forbidden in GitHub Actions to avoid public publication of draft artifacts.

    python -m experiments.v3_p5_controlled_ablation --live --confirm RUN_P5_ABLATION_ONCE --private-output /private/path/p5-experiment-YYYYMMDD

Default four calls A/B/C/D maximum, optional fifth E with --include-e; no model fallback or API auto retry. Native per-request budget + persistent counter reserves before every real provider send. Ambiguous errors retain reservation. If any sample fails validation/response, stop, keep partial results private, report INCOMPLETE_TECHNICAL_NO_GO and do not rank the arms.

Outputs are mode 0700 directory, 0600 files: blindly labeled Candidate_*.md, manifest.json, KEY_OPEN_AFTER_SCORING.json. Never commit raw manuscripts, five-stage bundles, compressed equivalents, or identifying blind KEY into repository or public GitHub Actions artifacts. The live proof does not upload or publish anywhere.

## Blind scoring and limits

Evaluate each completed manuscript, without model/arm key: Opening 15, Writer-specific curiosity 15, Evidence-driven discovery 20, Cognitive shift 15, Natural Japanese 15, Memorability 10, claim restraint 10. Independently verify factual statements before any real Publication Gate. Scores are subjective and not Proof of model or integration causality. Independent repetitions (ideally >=3 per contrast, respecting quota) needed for robust attribution. No selection solely on content length or synthetic style-check metrics.

Do NOT modify main, V1/V2/Classic, Daily, note, Notion, publication gates, Gemini production resilience code. PR #862 is draft; this experiment is a separate stacked draft. NO MERGE absent explicit owner MERGE GO.
