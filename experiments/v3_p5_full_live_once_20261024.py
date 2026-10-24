"""Owner-authorized 2026-10-24 original P5 five-stage one-shot live article preview.

No Notion, note, repository or provider-side writing. Strictly two logical Gemini stages, at most four model-level attempts,
for one official-source article. Primary 3.6 Flash, fallback 3.8 Flash only. Reuses the merged Production P5
five-stage A+ adapter, with a bounded standalone provider client rather than
running Daily's downstream dispatch chain. This is NOT a publication Gate proof.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

MODEL_ORDER = ("gemini-3.6-flash", "gemini-3.8-flash")
FALLBACK_HTTP_CODES = frozenset({404, 429, 500, 502, 503, 504})
OUTPUT = Path("p5_full_one_shot_artifact")
TITLE = "Using thousands of AI agents to uncover new leads in biological data"
URL = "https://openai.com/index/scaling-ai-research-for-complex-biological-data/"
PUBLICATION_DATE = "2026-10-21"
FACTS = (
    "OpenAI published this official report on October 21, 2026 with PerturbAI and Scripps Research.",
    "Thousands of GPT-Rosalind-powered agents examined existing experimental data from millions of mouse brain cells in 32 minutes, NOT new human clinical trials.",
    "Each agent investigated a gene disruption, related cellular responses, and scientific literature; the atlas combines gene effects, papers, and potential mechanisms.",
    "At the largest controlled workload, distributed agents cited more than 700 references, versus 11 for one agent when the model and resources were held fixed.",
    "In a blinded expert comparison, human reviewers preferred reports from distributed agents over reports from a single agent 75 percent of the time. This is report preference, not AI/non-AI detection, clinical efficacy, or 75 percent accuracy.",
    "Follow-up hypotheses concerned Tsc1/Tsc2 in cerebellar neurons and DCTN1 with cholesterol transport; they need laboratory validation.",
    "The research team's months-to-a-year estimate for similar sequential human analyses is an estimate, NOT directly measured time-saving equivalence.",
    "This supports research prioritization and generating laboratory hypotheses, NOT established diagnosis, drug efficacy, treatment, or human benefit.",
)
LIMITS = (
    "Source is an official OpenAI vendor account; independent validation not included.",
    "Keep the reported 32 minutes restricted to the distributed-agent research task.",
    "The 700 versus 11 citation contrast concerns a particular workload and controlled conditions.",
    "75% is an expert report preference between agent configurations, not proof of truth or treatment effectiveness.",
    "Months-to-a-year is a human-work estimate, not experimentally measured time saving.",
)
SOURCE = "\n".join(f"- {value}" for value in FACTS) + "\n\nSource limitations:\n" + "\n".join(LIMITS)


def _write(obj):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "manifest.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    assert os.environ.get("AIIF_EDITORIAL_STYLE") == "v3_p5"
    assert os.environ.get("GEMINI_API_KEY"), "Secret GEMINI_API_KEY is missing"
    import pipeline as p
    import a_plus_editorial_orchestration as a_plus
    from canonical_article_contract import aiif_editor_persona
    from google import genai
    from local_skills.a_plus import PREWRITE_CONTRACT_ID

    # Evidence fixture is source-scoped and treated as "sufficient" ONLY for
    # this isolated prompt-routing proof. It does not assert the full Production
    # Evidence/Facts/Publication Gates are satisfied or independently verified.
    evidence_result = {
        "state": p.EVIDENCE_SUFFICIENT,
        "decision_scope_safe": True,
        "limitations_disclosed": True,
        "numeric_claims_allowed": True,
        "actor_attribution_allowed": True,
    }
    metadata = {"required_qualifiers": list(LIMITS), "publication_date": PUBLICATION_DATE, "primary_url": URL}
    source_info = {
        "primary_url": URL,
        "context": SOURCE,
        "verification_context": SOURCE,
        "evidence_result": evidence_result,
        "evidence_sufficient": True,
        "evidence_metadata": metadata,
        "method": "Source Native / controlled fixture",
        "sufficient": True,
    }
    repo = {"name": TITLE, "url": URL, "nameWithOwner": TITLE, "source": "OfficialVendor"}
    state = {
        "case": "20261021_openai_biology_agents_p5_full_original",
        "model_preference": list(MODEL_ORDER),
        "model_active": MODEL_ORDER[0],
        "code_revision": os.environ.get("GITHUB_SHA", "")[:40],
        "production_merge": "b2ba9f93f107fa7fe5dcab0d1a6730ba5b9eb0ba",
        "source_url": URL,
        "source_date": PUBLICATION_DATE,
        "source_digest": hashlib.sha256(SOURCE.encode("utf-8")).hexdigest(),
        "max_provider_requests": 4,
        "max_logical_requests": 2,
        "logical_requests_started": 0,
        "logical_requests_completed": 0,
        "provider_attempts": [],
        "provider_requests_started": 0,
        "provider_requests_completed": 0,
        "status": "NOT_STARTED",
        "publication": False,
        "notion_write": False,
        "full_production_gates_executed": False,
    }
    _write(state)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"timeout": 120000, "retry_options": {"attempts": 1}})
    try:
        def direct_provider(prompt, repo_data, evidence_data, *, request_kind="deep_dive", request_context="", request_origin="new"):
            stage = state["logical_requests_started"] + 1
            if stage > 2:
                raise RuntimeError("Maximum 2 logical generation stages exceeded")
            if stage == 2 and "1. Writer Reaction" not in prompt:
                raise RuntimeError("Second stage is not authentic five-stage P5")
            state["logical_requests_started"] = stage
            _write(state)

            starting_model_index = MODEL_ORDER.index(state["model_active"])
            for model in MODEL_ORDER[starting_model_index:]:
                attempt_count = state["provider_requests_started"] + 1
                if attempt_count > state["max_provider_requests"]:
                    raise RuntimeError("Provider request budget exhausted; no further calls")
                state["provider_requests_started"] = attempt_count
                entry = {"stage": stage, "attempt": attempt_count, "model": model, "result": "STARTED"}
                state["provider_attempts"].append(entry)
                _write(state)
                print(f"P5_PROVIDER_START stage={stage}/2 attempt={attempt_count}/4 model={model}", flush=True)
                try:
                    response = client.models.generate_content(
                        model=model, contents=prompt,
                        config={
                            "system_instruction": aiif_editor_persona(),
                            "max_output_tokens": 18000 if stage == 2 else 9500,
                            "temperature": 0.65 if stage == 2 else 0.4,
                        },
                    )
                except Exception as exc:
                    # Do not store exception body: may include sensitive request data.
                    raw_code = getattr(exc, "code", None)
                    if not isinstance(raw_code, int):
                        raw_code = getattr(exc, "status_code", None)
                    code = int(raw_code) if str(raw_code).isdigit() else None
                    entry.update(result="ERROR", error_type=type(exc).__name__, http_status=code)
                    state["error_type"] = type(exc).__name__
                    state["error_http_status"] = code
                    _write(state)
                    print(f"P5_PROVIDER_ERROR stage={stage} model={model} status={code} type={type(exc).__name__}", flush=True)
                    # One-way fallback on rate limit, unavailability or model deprecation.
                    if model == MODEL_ORDER[0] and code in FALLBACK_HTTP_CODES:
                        state["model_active"] = MODEL_ORDER[1]
                        _write(state)
                        print(f"P5_PROVIDER_FALLBACK from={model} to={MODEL_ORDER[1]} reason_http={code}", flush=True)
                        continue
                    raise
                text = str(getattr(response, "text", "") or "").strip()
                if not text:
                    raise RuntimeError("Empty Gemini response; no retry or fallback")
                entry["result"] = "SUCCESS"
                state["logical_requests_completed"] = stage
                state["provider_requests_completed"] += 1
                state["model_active"] = model
                state.pop("error_type", None)
                state.pop("error_http_status", None)
                (OUTPUT / f"generation_{stage}_raw.txt").write_text(text, encoding="utf-8")
                _write(state)
                print(f"P5_PROVIDER_SUCCESS stage={stage}/2 model={model} chars={len(text)}", flush=True)
                return response, {"grounding_status": "Source Native / supplied prompt evidence fixture", "evidence_urls": [URL]}
            raise RuntimeError("No approved fallback model available")

        p.AIIF_EDITORIAL_STYLE = "v3_p5"
        p.call_gemini_grounded_deep_dive = direct_provider
        a_plus.install(p)
        prompt = p.build_decision_prompt(
            name=TITLE,
            url=URL,
            stars=0,
            desc="Researchers used distributed AI agents to analyze pre-existing mouse brain cell perturbation data and generate testable biological hypotheses.",
            source="OfficialVendor",
            source_context=SOURCE,
            grounding_status_hint="Source Native / supplied official-source facts",
            evidence_metadata=metadata,
            freshness={},
            evidence_result=evidence_result,
        )
        assert prompt.count(PREWRITE_CONTRACT_ID) == 1, "Missing LocalSkills contract"
        assert "=== MANAGEMENT DATA ===" in prompt, "Missing canonical production schema"
        assert p.SECTION_SPLIT_TOKEN in prompt, "Missing canonical article split"
        state["status"] = "RUNNING"
        state["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        _write(state)
        final_response, grounding = p.call_gemini_grounded_deep_dive(
            prompt, repo, source_info,
            request_kind="deep_dive",
            request_context="official:20261021:fullp5",
            request_origin="article_revalidation",
        )
        assert state["logical_requests_started"] == state["logical_requests_completed"] == 2
        assert state["provider_requests_completed"] == 2
        assert 2 <= state["provider_requests_started"] <= 4
        parsed = p._parse_gemini_response(str(final_response.text))
        title = str(parsed.get("title_text") or "").strip()
        draft = str(parsed.get("note_draft") or "").strip()
        assert title and len(draft) > 350, "No parseable substantive P5 article"
        assert not re.search(r"(?m)^#+\s*(?:Writer Reaction|Editorial Discovery|Cognitive Shift|Fact-Safe Review)\s*$", draft)
        (OUTPUT / "p5_article.md").write_text(f"# {title}\n\n{draft}\n", encoding="utf-8")
        (OUTPUT / "p5_production_combined_raw.txt").write_text(str(final_response.text), encoding="utf-8")
        state.update({
            "status": "TECHNICAL_P5_COMPLETED_NEEDS_FACT_AND_EDITORIAL_REVIEW",
            "article_chars": len(draft),
            "article_title": title,
            "management_preserved": "=== MANAGEMENT DATA ===" in str(final_response.text),
            "article_sha256": hashlib.sha256(draft.encode("utf-8")).hexdigest(),
            "full_production_gates_executed": False,
        })
        _write(state)
        print(f"P5_FULL_LIVE_COMPLETE title_chars={len(title)} article_chars={len(draft)} logical_calls=2 provider_attempts={state['provider_requests_started']} model={state['model_active']}", flush=True)
    except Exception as exc:
        state["status"] = "TECHNICAL_NO_GO"
        state["error_type"] = type(exc).__name__
        _write(state)
        print(f"P5_FULL_STOP_FAIL_CLOSED error_type={type(exc).__name__} provider_attempts={state['provider_requests_started']}/4", flush=True)
        raise RuntimeError("P5 Full one-shot did not complete; inspect private artifact and safe status") from None
    finally:
        client.close()


if __name__ == "__main__":
    main()
