"""Controlled P5 authorial-boundary A/B/C nonpreview-model test; NO persistence or publication.

One public-source evidence fixture, three editorial prompts, same model/settings,
30s request pacing, 60s model failover backoff, at most nine provider attempts.
A: managed writer prompt + canonical system persona (current integrated)
B: original writer prompt + canonical system persona (prompt ablation)
C: original writer prompt + no added system persona (system ablation)
Do not call this a production Gate or a statistically decisive quality benchmark.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from pathlib import Path
from types import SimpleNamespace

from canonical_article_contract import aiif_editor_persona
from google import genai
from local_skills.v3_p5_one_shot import P5EditorialContractError, _extract_bundle, _p5_prompt, _source_case
from local_skills.v3_p5_prompts import build_editorial_bundle_prompt

MODEL_ORDER = ("gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.8-flash")
RETRIABLE_STATUS = frozenset((404, 429, 500, 502, 503, 504))
MAX_ATTEMPTS = 9
MIN_INTERVAL = 30.0
FAILOVER_BACKOFF = 60.0
OUTPUT = Path("p5_original_boundary_abc_artifact")
URL = "https://openai.com/index/scaling-ai-research-for-complex-biological-data/"
TITLE = "Using thousands of AI agents to uncover new leads in biological data"
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
SOURCE = "\n".join("- "+s for s in FACTS) + "\n\nSource limitations:\n" + "\n".join(LIMITS)
MANAGEMENT = {
    "source_summary_text": "OpenAI、PerturbAI、Scripps Researchは、数千のGPT-Rosalind搭載AIエージェントを用いて数百万のマウス脳細胞データを32分で解析し、研究用仮説を自動生成した実験成果を発表した。",
    "decision_text": "WATCH",
    "decision_reason_text": "並列エージェントによる多角的な仮説抽出手法は有望だが、生成された仮説の妥当性は実際の実験検証が必要であり、第三者による独立検証も未実施なため。",
    "action_text": "自社の研究開発やデータ解析において並列エージェントによる調査手法の可能性を整理しつつ、ラボでの実証報告や他社による再現検証の動向を注視する。",
}


def save(state):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "manifest.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")


def status_of(exc):
    code = getattr(exc,"code",None)
    if not isinstance(code,int):
        code = getattr(exc,"status_code",None)
    return int(code) if str(code).isdigit() else None


def main():
    assert os.environ.get("GEMINI_API_KEY"), "missing bounded proof API key"
    assert os.environ.get("AIIF_EDITORIAL_STYLE") == "v3_p5"
    assert len(MODEL_ORDER) == len(set(MODEL_ORDER)) == 3
    assert all(model.startswith("gemini-3.") and "preview" not in model.lower() and "lite" not in model.lower() for model in MODEL_ORDER)
    assert MAX_ATTEMPTS == 3 * len(MODEL_ORDER)
    evidence_result = {
        "state":"SUFFICIENT","decision_scope_safe":True,"limitations_disclosed":True,
        "numeric_claims_allowed":True,"actor_attribution_allowed":True,
    }
    meta = {"required_qualifiers":list(LIMITS),"publication_date":"2026-10-21","primary_url":URL}
    info = {
        "primary_url":URL,"context":SOURCE,"verification_context":SOURCE,
        "evidence_result":evidence_result,"evidence_sufficient":True,
        "evidence_metadata":meta,"method":"Source Native / controlled fixture",
        "sufficient":True,
    }
    case = _source_case({"name":TITLE,"url":URL},info,SimpleNamespace(EVIDENCE_SUFFICIENT="SUFFICIENT"))
    original = build_editorial_bundle_prompt(case)
    managed = _p5_prompt(case,MANAGEMENT,info,writer_boundary="managed")
    isolated = _p5_prompt(case,MANAGEMENT,info,writer_boundary="original")
    assert original == isolated and managed != original
    assert all(s in original for s in ("1. Writer Reaction","5. Fact-Safe Review"))
    assert "a-plus-local-skeleton-v2" in managed
    assert "a-plus-local-skeleton-v2" not in isolated
    profiles = {
        "managed_plus_system":{"prompt":managed,"system":True},
        "original_plus_system":{"prompt":isolated,"system":True},
        "original_without_system":{"prompt":isolated,"system":False},
    }
    order = list(profiles)
    random.Random(20261024).shuffle(order)
    # Public samples and sealed mapping only stored after the entire same-model comparison passes.
    state = {
        "status":"NOT_STARTED","source_url":URL,"source_digest":hashlib.sha256(SOURCE.encode()).hexdigest(),
        "candidate_code_revision":os.getenv("GITHUB_SHA",""),
        "production_base":"b2ba9f93f107fa7fe5dcab0d1a6730ba5b9eb0ba",
        "model_priority":list(MODEL_ORDER),"model_used":None,
        "variants":3,"max_attempts":MAX_ATTEMPTS,"provider_attempts":0,
        "min_interval":MIN_INTERVAL,"fallback_backoff":FAILOVER_BACKOFF,
        "publication":False,"note_write":False,"notion_write":False,
        "full_production_gates_executed":False,"failure_events":[],
    }
    save(state)
    client=genai.Client(api_key=os.environ["GEMINI_API_KEY"],http_options={"timeout":120000,"retry_options":{"attempts":1}})
    last_terminal=None
    last_failed=False
    try:
        for model in MODEL_ORDER:
            raw_results={}
            for name in order:
                if last_terminal is not None:
                    required=FAILOVER_BACKOFF if last_failed else MIN_INTERVAL
                    wait=max(0.0,required-(time.monotonic()-last_terminal))
                    if wait:
                        print(f"P5_ABC_PACING before={name} required={required:.1f}s slept={wait:.1f}s",flush=True)
                        time.sleep(wait)
                count=state["provider_attempts"]+1
                if count>MAX_ATTEMPTS:
                    raise RuntimeError("Provider attempt ceiling exceeded")
                state["provider_attempts"]=count
                save(state)
                print(f"P5_ABC_PROVIDER_START attempt={count}/{MAX_ATTEMPTS} model={model} variant={name}",flush=True)
                profile=profiles[name]
                config={"temperature":0.65,"max_output_tokens":18000}
                if profile["system"]:
                    config["system_instruction"]=aiif_editor_persona()
                try:
                    response=client.models.generate_content(model=model,contents=profile["prompt"],config=config)
                except Exception as exc:
                    last_terminal=time.monotonic()
                    last_failed=True
                    code=status_of(exc)
                    state["failure_events"].append({"attempt":count,"model":model,"status":code,"error_type":type(exc).__name__})
                    save(state)
                    print(f"P5_ABC_PROVIDER_ERROR attempt={count} model={model} status={code} type={type(exc).__name__}",flush=True)
                    if model!=MODEL_ORDER[-1] and code in RETRIABLE_STATUS:
                        print(f"P5_ABC_RESTART_ALL_ARMS_WITH_NEXT_MODEL_AFTER_{model}",flush=True)
                        break  # Discard this model partial set; restart complete A/B/C with next model.
                    raise
                last_terminal=time.monotonic()
                last_failed=False
                response_text=str(getattr(response,"text","") or "").strip()
                try:
                    if not response_text:
                        raise P5EditorialContractError("Empty response: fail closed")
                    final,stages=_extract_bundle(response_text)
                    if not final.startswith("# "):
                        raise P5EditorialContractError("Missing P5 article title")
                except P5EditorialContractError as exc:
                    # Reject malformed or reader-unsafe output. It may never
                    # count as a completed arm, and we never weaken the P5 gate.
                    # Only a different, allowlisted nonpreview model may start
                    # an entirely fresh same-model three-arm comparison.
                    last_terminal=time.monotonic()
                    last_failed=True
                    event={"attempt":count,"model":model,
                           "status":"P5_CONTRACT_REJECTED",
                           "error_type":type(exc).__name__,
                           "error_message":str(exc)[:300],
                           "response_digest":hashlib.sha256(response_text.encode()).hexdigest()}
                    state["failure_events"].append(event)
                    save(state)
                    print(f"P5_ABC_OUTPUT_REJECTED attempt={count} model={model} type={type(exc).__name__} details={str(exc)[:160]}",flush=True)
                    if model!=MODEL_ORDER[-1]:
                        print(f"P5_ABC_RESTART_ALL_ARMS_WITH_NEXT_MODEL_AFTER_{model}",flush=True)
                        break
                    raise
                raw_results[name]={"raw":response_text,"article":final,"stage_keys":list(stages),"sha256":hashlib.sha256(final.encode()).hexdigest()}
                (OUTPUT / f"attempt_{count}_raw.txt").write_text(response_text,encoding="utf-8")
                print(f"P5_ABC_PROVIDER_SUCCESS model={model} variant={name} article_chars={len(final)}",flush=True)
            if len(raw_results)==3:
                state["model_used"]=model
                state["status"]="TECHNICAL_ABC_COMPLETED_NEEDS_BLIND_EDITORIAL_AND_FACT_REVIEW"
                manifest=[]
                for index,name in enumerate(order):
                    label="ABC"[index]
                    item=raw_results[name]
                    (OUTPUT / f"sample_{label}.md").write_text(item["article"]+"\n",encoding="utf-8")
                    (OUTPUT / f"stages_{label}.json").write_text(item["raw"],encoding="utf-8")
                    manifest.append({"sample":label,"variant":name,"article_chars":len(item["article"]),"sha256":item["sha256"]})
                # Intentionally separate mapping; article samples contain no variant labels.
                (OUTPUT / "blind_mapping.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
                (OUTPUT / "comparative_prompt_digests.json").write_text(json.dumps(
                    {"original":hashlib.sha256(original.encode()).hexdigest(),
                     "managed":hashlib.sha256(managed.encode()).hexdigest(),
                     "same_facts":True,"same_model":True,"same_temperature":True},
                     indent=2),encoding="utf-8")
                save(state)
                print(f"P5_ABC_LIVE_COMPLETE model={model} three_full_editorial_bundles=PASS requests={count}",flush=True)
                return
            assert model!=MODEL_ORDER[-1] and state["failure_events"],"All three variants required"
        raise RuntimeError("No model delivered all three P5 variants")
    except Exception as exc:
        state["status"]="TECHNICAL_NO_GO"
        state["error_type"]=type(exc).__name__
        save(state)
        print(f"P5_ABC_STOP_FAIL_CLOSED type={type(exc).__name__} attempts={state['provider_attempts']}",flush=True)
        raise RuntimeError("Bounded nonpreview P5 A/B/C proof did not finish; review safe manifest") from None
    finally:
        client.close()


if __name__=="__main__":
    main()
