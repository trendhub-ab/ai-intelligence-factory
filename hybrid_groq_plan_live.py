"""One-call Hybrid Groq Decision Plan runner using JSON Object Mode + local strict validation."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from ai_provider import GenerationRequest, GroqProvider, ProviderError
from groq_rate_policy import policy_for_model
from groq_remote_budget import reserve_remote, reconcile_remote
from groq_validation import NoRedirect, schema_validator
from hybrid_groq_plan import MODE, validate_hybrid_plan_text


def run_live(fixture_path: str, report_path: str) -> dict:
    fixture=json.loads(Path(fixture_path).read_text(encoding='utf-8'))
    if fixture.get('structured_output_mode') != MODE:
        raise ProviderError('hybrid_plan_mode_required')
    model=str(fixture['model'])
    policy=policy_for_model(model)
    request=GenerationRequest(
        fixture['prompt'],
        int(fixture['max_output_tokens']),
        fixture['schema'],
        fixture.get('reasoning_effort','medium'),
        fixture['structured_output_mode'],
    )
    provider=GroqProvider(
        lambda _: None,
        validate_schema=schema_validator(fixture['schema']),
        request_budget=1,
        token_budget=policy.safe_tpm,
        model=model,
    )
    payload,estimate=provider.prepare(request)
    if payload.get('response_format') != {'type':'json_object'}:
        raise ProviderError('hybrid_plan_json_object_transport_missing')
    if model.startswith('openai/gpt-oss-') and payload.get('reasoning_format') != 'hidden':
        raise ProviderError('hybrid_plan_reasoning_format_missing')

    key=os.environ.get('GROQ_API_KEY','').strip()
    token=os.environ.get('GROQ_LEDGER_GITHUB_TOKEN','').strip()
    experiment=os.environ.get('AIIF_GROQ_EXPERIMENT','').strip()
    if not key or not token or not experiment:
        raise ProviderError('groq_key_and_persistent_ledger_required')
    opener=urllib.request.build_opener(NoRedirect())

    def transport(payload):
        reserve_remote(token,experiment,estimate,opener,policy.name)
        req=urllib.request.Request(
            'https://api.groq.com/openai/v1/chat/completions',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization':'Bearer '+key,
                'Content-Type':'application/json',
                'User-Agent':'AI-Intelligence-Factory/1.0',
                'Accept':'application/json',
            },
            method='POST',
        )
        try:
            with opener.open(req,timeout=60) as response:
                return response.status,dict(response.headers),json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code,dict(exc.headers),{}

    provider.transport=transport
    result=provider.generate(request)
    actual=result.prompt_tokens+result.completion_tokens
    reconcile_remote(token,experiment,actual,opener,policy.name)
    plan=validate_hybrid_plan_text(result.text)
    report={
        'mode':'hybrid_groq_plan_json_object_local_strict',
        'provider':'groq',
        'model':model,
        'rate_policy':policy.name,
        'stage':'article',
        'pass':'decision_plan',
        'candidate_id':fixture.get('candidate_id'),
        'structured_output_mode':MODE,
        'provider_calls':1,
        'reserved_token_estimate':estimate,
        'actual_tokens':actual,
        'ledger_reconciled':True,
        'local_schema_validated':True,
        'semantic_plan_validated':True,
        'business_writes':0,
        'persist_results':False,
        'result':asdict(result),
    }
    Path(report_path).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report
