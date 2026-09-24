"""One-shot private comparison. Run only in isolated Actions runner with GEMINI_API_KEY.
No Notion, note, Telegram, GH write credentials; no production persistence.
"""
import copy
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pipeline
import production_pipeline

OUT = Path('evidence_only_private_result')
OUT.mkdir(exist_ok=True)
URL = 'https://www.together.ai/blog/canary-rollouts-upgrade-models-in-production-without-downtime'
REPO = {
    'nameWithOwner': 'Canary rollouts: upgrade models in production without downtime — Together AI',
    'description': 'Together AI rollout strategies for dedicated inference',
    'url': URL, 'primaryUrl': URL, 'source': 'X', 'stargazerCount': 0,
}
trace = {'main_sha': os.environ.get('GITHUB_SHA', ''), 'source_url': URL,
         'parsed_stages': [], 'fact_gates': [], 'publication_gates': [], 'rescues': []}

def record_error(exc):
    trace['exception'] = {'type': type(exc).__name__, 'message': str(exc)[:1000]}

def wrap(name, target, save):
    original = getattr(pipeline, name)
    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        save(args, kwargs, result)
        return result
    setattr(pipeline, name, wrapped)
    return original

def save_parsed(args, kwargs, result):
    parsed = result[0]
    trace['parsed_stages'].append({'title': parsed.get('title_text', ''), 'article': parsed.get('note_draft', '')})

def save_fact(args, kwargs, result):
    trace['fact_gates'].append({'ok': result[0], 'failures': result[1],
                                'article_sha256': hashlib.sha256(str(args[0].get('note_draft','')).encode()).hexdigest()})

def save_publication(args, kwargs, result):
    trace['publication_gates'].append({'state': result[0], 'issues': result[1],
                                       'article_sha256': hashlib.sha256(str(args[0].get('note_draft','')).encode()).hexdigest()})

def save_rescue(args, kwargs, result):
    parsed, changes = result
    trace['rescues'].append({'changes': changes, 'loss': parsed.get('_rescue_loss'),
                              'title': parsed.get('title_text',''), 'article': parsed.get('note_draft','')})

logging.basicConfig(filename=OUT/'runner.log', level=logging.INFO, force=True)
try:
    if not os.environ.get('GEMINI_API_KEY'):
        raise RuntimeError('GEMINI_API_KEY is absent in runner')
    production_pipeline.install_runtime_layers(pipeline)
    # Run260 prepends its default pool even when the env lists only two models.
    # Keep this isolated run to the user-selected non-3.6 fallback pool.
    pipeline.DEEP_DIVE_MODEL_POOL = ['gemini-3.7-flash', 'gemini-3.8-flash']
    pipeline.DEEP_DIVE_MODEL_CANDIDATES = list(pipeline.DEEP_DIVE_MODEL_POOL)
    pipeline.DEEP_DIVE_MODEL_BUDGET.budget = 4  # two models plus at most one quality retry
    trace['model_pool'] = list(pipeline.DEEP_DIVE_MODEL_POOL)
    trace['api_send_cap'] = 4
    # Resolve all Evidence once; both paths use the same frozen in-memory snapshot.
    evidence = pipeline.prepare_source_context(REPO)
    evidence_result = pipeline.assess_evidence_sufficiency(evidence)
    if evidence_result['state'] == pipeline.EVIDENCE_SUPPLEMENT_REQUIRED:
        pipeline.supplement_source_evidence(evidence)
        evidence_result = pipeline.assess_evidence_sufficiency(evidence)
    trace['evidence'] = {
        'state': evidence_result['state'],
        'primary_source_resolved': evidence.get('primary_source_resolved'),
        'verification_context_sha256': hashlib.sha256((evidence.get('verification_context') or evidence.get('context','')).encode()).hexdigest(),
        'writer_context_sha256': hashlib.sha256(evidence.get('context','').encode()).hexdigest(),
        'document_urls': [d.get('url','') if isinstance(d, dict) else str(d)[:200] for d in evidence.get('evidence_documents',[])],
        'writer_context_chars': len(evidence.get('context','')),
        'verification_context_chars': len(evidence.get('verification_context') or evidence.get('context','')),
    }
    if evidence_result['state'] != pipeline.EVIDENCE_SUFFICIENT or not evidence.get('primary_source_resolved'):
        raise RuntimeError('Evidence preflight did not resolve sufficient primary source')
    (OUT/'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))
    frozen = copy.deepcopy(evidence)
    pipeline.prepare_source_context = lambda repo: copy.deepcopy(frozen)
    wrap('_apply_deterministic_structure_polish', pipeline, save_parsed)
    wrap('validate_fact_gate', pipeline, save_fact)
    wrap('validate_publication_readiness_gate', pipeline, save_publication)
    wrap('_apply_deterministic_publication_rescue', pipeline, save_rescue)
    result = pipeline.generate_intelligence_report(REPO, persist_results=False)
    trace['return_status'] = result[1] if isinstance(result, tuple) else 'NO_RESULT'
    trace['return_manuscript'] = result[0] if isinstance(result, tuple) else ''
except Exception as exc:
    record_error(exc)
    logging.exception('Experiment failed')
finally:
    (OUT/'trace.json').write_text(json.dumps(trace, ensure_ascii=False, indent=2))
    if trace['parsed_stages']:
        (OUT/'B_writer_gate_before.md').write_text(trace['parsed_stages'][0]['article'])
    if trace['rescues']:
        (OUT/'A_after_rescue.md').write_text(trace['rescues'][-1]['article'])
    elif trace['parsed_stages']:
        (OUT/'A_after_gates.md').write_text(trace['parsed_stages'][-1]['article'])
