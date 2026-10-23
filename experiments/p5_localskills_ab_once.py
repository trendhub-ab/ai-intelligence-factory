"""V3 P5/Classic Production prompt A/B, bounded live-only proof.

Four provider sends maximum; no retries, no publishing, no Notion,
no Production Daily. Import canonical Production prompt builder and installed
A+ LocalSkills prewrite contract, then compare the *same source and model*.
Not a full LocalSkills publication/Gate run. Any failure is NO-GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

MODEL = "gemini-3-flash-preview"
PINNED_ADAPTER = "68697a04d5c762203f15b6df7a7bf2b53dd48a99"
MAX_PROVIDER_CALLS = 4
OUT = Path("p5_ab_artifacts")
STYLES = ("classic", "v3_p5")

# Manually delimited fact extracts from the referenced official vendor reports.
# Dates/metrics/caveats are part of the controlled input; publication readiness
# and full source coverage are NOT inferred from this fixture.
CASES = (
    {
        "id": "openai_biology_agents_20261021",
        "name": "Using thousands of AI agents to uncover new leads in biological data",
        "url": "https://openai.com/index/scaling-ai-research-for-complex-biological-data/",
        "published": "2026-10-21",
        "description": "OpenAI, PerturbAI and Scripps Research applied multiple AI agents to mouse brain cellular perturbation data; findings are hypotheses, not clinically proven therapies.",
        "facts": (
            "OpenAI published this report on October 21, 2026 with PerturbAI and Scripps Research.",
            "Thousands of GPT-Rosalind-powered agents examined existing experimental data from millions of mouse brain cells in 32 minutes; NOT a new trial on human patients.",
            "Each agent analyzed a gene disruption, cellular responses and scientific literature; the assembled reasoning atlas connects genes, effects, papers and potential mechanisms.",
            "At the largest controlled workload, distributed agents cited more than 700 references versus 11 for one agent when model and resources were held fixed.",
            "Blinded human experts preferred distributed-agent reports over single-agent reports 75% of the time. This is a report-preference comparison, NOT treatment effectiveness.",
            "Agents suggested follow-up hypotheses involving Tsc1/Tsc2 in cerebellar neurons and DCTN1/cholesterol transport; these need laboratory validation.",
            "The team's estimate that similar sequential human analysis could take months to a year is a research-team estimate, not a measured human trial.",
            "The result is research-prioritization assistance. It does not establish diagnosis, treatment or general clinical efficacy.",
        ),
        "required_qualifiers": (
            "Use the terms mouse brain cell data, research leads, and hypotheses requiring validation.",
            "Scope 700 vs 11 to one controlled largest-workload reference-coverage comparison.",
            "Scope 75% to blinded preference for reports, not accuracy or medical benefit.",
        ),
    },
    {
        "id": "openai_low_resource_code_20261019",
        "name": "Advancing coding in low-resource programming languages",
        "url": "https://openai.com/index/low-resource-programming-languages/",
        "published": "2026-10-19",
        "description": "OpenAI reported two separate coding benchmarks for language-portable SQLite engine building and COBOL program migration; evaluated scores must not be treated as real-world production migration reliability.",
        "facts": (
            "OpenAI published this research explanation October 19, 2026.",
            "MultiLangBench assesses building a SQLite-compatible database engine across 20 programming languages; tests compare resulting database state to SQLite reference behavior.",
            "At maximum reasoning effort, GPT-6 Astra scored an 87.4% mean test pass rate across 20 languages versus 26.8% for GPT-5.6 Sol in MultiLangBench.",
            "COBOL is comparatively difficult: in MultiLangBench its score was 72.1% for Astra, according to the OpenAI report, not 87.4%.",
            "A separate COBOL migration assessment tests behavior-preserving conversion from COBOL to C++, Java, Kotlin, Python, or Rust using hidden byte-exact output tests.",
            "In that separate migration test at low reasoning effort, GPT-6.1 Sol scored 86.6% versus GPT-5.6 Sol 5.4%; higher reasoning effort reached 97.9%.",
            "A COBOL fixed-point truncation versus rounding mismatch can change amounts even when migrated code runs without crashing. Production migrations require independent behavioral checks.",
            "These are OpenAI-reported evaluation conditions; do not infer guaranteed production readiness, full safety, or external validation.",
        ),
        "required_qualifiers": (
            "Separate MultiLangBench 20-language mean from COBOL migration benchmark: do not mix scores.",
            "Attribute numbers to OpenAI's reported evaluations, not independently reproduced results.",
            "Low reasoning for the 86.6% COBOL migration result; 97.9% is higher-effort and must not be merged into the same condition.",
        ),
    },
)


def _hash_bytes(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_source(case: dict) -> str:
    return (
        f"Primary source: {case['url']}\n"
        f"Official publication date: {case['published']}\n"
        + "\n".join(f"- {row}" for row in case["facts"])
        + "\n"
        + "Source limitations: primary vendor report; clinical/enterprise deployment and independent reproduction not established by this input."
    )


def build_comparison():
    import pipeline as p
    import a_plus_editorial_orchestration as a_plus
    from content_generation_protocol import editorial_style_rules
    from local_skills.a_plus import PREWRITE_CONTRACT_ID

    # The actual Production build_decision_prompt function, wrapped by the
    # currently installed A+ LocalSkills policy, not hand-written style output.
    a_plus.install(p)
    all_pairs = []
    for case in CASES:
        output = {}
        for style in STYLES:
            p.AIIF_EDITORIAL_STYLE = style
            prompt = p.build_decision_prompt(
                name=case["name"],
                url=case["url"],
                stars=0,
                desc=case["description"],
                source="OfficialVendor",
                source_context=_canonical_source(case),
                grounding_status_hint="Source Native (offline curated)",
                evidence_metadata={
                    "required_qualifiers": list(case["required_qualifiers"]),
                    "primary_url": case["url"],
                    "official_publication_date": case["published"],
                },
                freshness={},
                evidence_result={
                    "state": "REVIEW",  # no actual Production Evidence Gate was run
                    "limitations_disclosed": True,
                    "numeric_claims_allowed": True,
                    "actor_attribution_allowed": True,
                },
            )
            voice = editorial_style_rules(style)
            assert prompt.count(voice) == 1, "Editorial policy not correctly routed"
            assert prompt.count(PREWRITE_CONTRACT_ID) == 1, "LocalSkills missing/duplicated"
            assert prompt.index(voice) < prompt.index(PREWRITE_CONTRACT_ID)
            assert prompt.index(PREWRITE_CONTRACT_ID) < prompt.index("【Output Contract｜完成稿のみ】")
            assert "=== MANAGEMENT DATA ===" in prompt
            assert p.SECTION_SPLIT_TOKEN in prompt
            output[style] = (prompt, voice)
        (classic, classic_voice), (p5, p5_voice) = [output[s] for s in STYLES]
        # Fail closed if ANYTHING except voice changed in the controlled pair.
        assert classic.replace(classic_voice, "<VOICE_POLICY>", 1) == p5.replace(
            p5_voice, "<VOICE_POLICY>", 1
        ), "Other-than-writer prompt drift"
        all_pairs.append((case, output))
    return p, all_pairs


def preflight() -> list[dict]:
    p, pairs = build_comparison()
    assert len(pairs) == 2 and len(pairs) * len(STYLES) == MAX_PROVIDER_CALLS
    assert MODEL in ("gemini-3-flash-preview", "gemini-3.6-flash", "gemini-3.8-flash")
    assert "lite" not in MODEL.lower()
    manifest = []
    for case, outputs in pairs:
        manifest.append({
            "case_id": case["id"],
            "primary_url": case["url"],
            "publication_date": case["published"],
            "input_sha256": _hash_bytes(_canonical_source(case)),
            "prompt_sha256": {s: _hash_bytes(outputs[s][0]) for s in STYLES},
            "common_prompt_except_style": "IDENTICAL",
            "local_skills_contract": "INJECTED_ONCE",
        })
    print("P5_AB_PREFLIGHT=PASS cases=2 pairs=2 max_provider_calls=4", flush=True)
    return manifest


def live() -> int:
    p, pairs = build_comparison()
    manifest = preflight()
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Missing GEMINI_API_KEY")
    OUT.mkdir(exist_ok=True)
    from google import genai
    from canonical_article_contract import aiif_editor_persona

    # Provider send budget is explicit. This test bypasses daily counters
    # while using the SAME shared GitHub Actions concurrency group.
    count = 0
    outcome = {"mode": "bounded_live_comparison", "model": MODEL,
               "max_provider_calls": MAX_PROVIDER_CALLS,
               "calls_started": 0, "calls_completed": 0,
               "cases": manifest, "status": "INCOMPLETE",
               "publication": False, "notion_write": False,
               "full_production_gates_executed": False}
    (OUT / "manifest.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"timeout": 120000})
    try:
        for case, output in pairs:
            for style in STYLES:
                prompt, _ = output[style]
                if count >= MAX_PROVIDER_CALLS:
                    raise RuntimeError("Provider call ceiling exceeded")
                count += 1
                outcome["calls_started"] = count
                (OUT / "manifest.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"P5_AB_PROVIDER_START case={case['id']} style={style} model={MODEL} count={count}/{MAX_PROVIDER_CALLS}", flush=True)
                response = client.models.generate_content(
                    model=MODEL,
                    contents=prompt,
                    config={"system_instruction": aiif_editor_persona(),
                            "max_output_tokens": 9000, "temperature": 0.5},
                )
                raw = str(getattr(response, "text", "") or "")
                if not raw.strip():
                    raise RuntimeError("Empty Gemini response; no retries or fallback")
                parsed = p._parse_gemini_response(raw)
                note = str(parsed.get("note_draft") or "").strip()
                title = str(parsed.get("title_text") or "").strip()
                case_dir = OUT / case["id"]
                case_dir.mkdir(exist_ok=True)
                (case_dir / f"{style}_full_raw.txt").write_text(raw, encoding="utf-8")
                (case_dir / f"{style}_article.md").write_text(f"# {title}\n\n{note}\n", encoding="utf-8")
                case_row = next(z for z in outcome["cases"] if z["case_id"] == case["id"])
                case_row[style] = {
                    "title": title,
                    "article_chars": len(note),
                    "has_management": "=== MANAGEMENT DATA ===" in raw,
                    "has_split": raw.count(p.SECTION_SPLIT_TOKEN) == 1,
                    "has_note_draft": len(note) > 300,
                    "has_decision": bool(parsed.get("decision_text")),
                    "has_score": int(parsed.get("score", 0)) > 0,
                    "sha256": _hash_bytes(raw),
                }
                outcome["calls_completed"] = count
                (OUT / "manifest.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
                if not all(case_row[style][flag] for flag in (
                        "has_management", "has_split", "has_note_draft",
                        "has_decision", "has_score")):
                    raise RuntimeError(f"Production output schema incomplete: {case['id']} {style}")
                print(f"P5_AB_ARTICLE_COMPLETE case={case['id']} style={style} chars={len(note)}", flush=True)
        outcome["status"] = "TECHNICAL_PASS"
        print("P5_AB_TECHNICAL_PASS pairs=2 provider_calls=4 blind_editorial_review_required", flush=True)
    except Exception as exc:
        outcome["status"] = "TECHNICAL_NO_GO"
        outcome["error_type"] = type(exc).__name__
        # Never print or store a potentially credential-bearing provider exception.
        print(f"P5_AB_STOP_NO_RETRY error_type={type(exc).__name__}", flush=True)
        return 1
    finally:
        outcome["calls_started"] = count
        (OUT / "manifest.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
        client.close()
    return 0


if __name__ == "__main__":
    argp = argparse.ArgumentParser()
    argp.add_argument("--mode", choices=("preflight", "live"), required=True)
    args = argp.parse_args()
    if args.mode == "preflight":
        preflight()
    else:
        raise SystemExit(live())
