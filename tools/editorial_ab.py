"""Label-blind, zero-I/O scoring of frozen article fixtures (NOT a publication gate).

Run: python tools/editorial_ab.py [--output report.json]
No pipeline/provider imports, model calls, source fetching or persistence adapters.
Scores are deterministic proxies, not measured reader behavior or semantic fact proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import canonical_article_contract as canonical
import content_generation_protocol as protocol
from editorial_naturalness import ai_style_composite_signals, find_fabricated_personal_experience
from reader_experience_signals import reader_experience_signals

FIXTURES = ROOT / 'tests/fixtures/editorial_ab'
METRIC_SIGNALS = {
    'Human Appeal': ('reader_delight', 'article_specific_angle'),
    'Opening pull': ('curiosity_pull', 'opening_non_engineer_access'),
    'Narrative continuity': ('narrative_understanding_progression', 'narrative_pull'),
    'Reader Proximity': ('reader_proximity', 'plain_language_bridge'),
    'Term comprehension': ('jargon_translation', 'non_engineer_core_clarity'),
    'Completion motivation': ('return_pull', 'narrative_pull'),
    'Decision clarity': ('explicit_reader_decision_action', 'caveat_or_concrete_action'),
}


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def opening(article, limit=700):
    """Actual lead/first section; fixtures use content-specific Markdown headings."""
    parts = re.split(r'^#{1,6}\s+.+$', article, flags=re.M)
    return next((p.strip()[:limit] for p in parts if p.strip()), '')


def score_article(article, evidence):
    # Reject absent evidence instead of returning a vacuous 100% retention score.
    for key in ('text', 'facts', 'required_evidence'):
        if not evidence.get(key):
            raise ValueError('Evidence text, facts and qualifiers are required')
    for anchor in evidence['facts'] + evidence['required_evidence']:
        if not isinstance(anchor, str) or not anchor.strip() or anchor not in evidence['text']:
            raise ValueError('Every fixture anchor must occur in the shared source text')
    signals = reader_experience_signals(article, opening)
    style = ai_style_composite_signals(article, [])
    metrics = {name: round(100 * sum(signals[k] is True or signals[k] == 'GOOD' for k in keys) / len(keys), 2)
               for name, keys in METRIC_SIGNALS.items()}
    metrics['Low AI odor'] = max(0, 100 - 20 * style['score'])
    metrics['Evidence retention'] = round(100 * sum(x in article for x in evidence['required_evidence']) / len(evidence['required_evidence']), 2)
    metrics['Fact retention'] = round(100 * sum(x in article for x in evidence['facts']) / len(evidence['facts']), 2)
    sentences = [s.strip() for s in re.split(r'(?<=[。！？!?])|\n', article) if s.strip()]
    duplicates = sum(len(s) * (n - 1) for s, n in Counter(sentences).items() if n > 1)
    metrics['Low unnecessary prose'] = round(max(0, 100 * (1 - duplicates / max(1, len(article))) - 5 * len(signals['generic_headings'])), 2)
    numbers = set(re.findall(r'\d+(?:[.,]\d+)*', article))
    source_numbers = set(re.findall(r'\d+(?:[.,]\d+)*', evidence['text']))
    unsupported_numbers = sorted(numbers - source_numbers)
    fabricated = find_fabricated_personal_experience(article)
    eligible = (metrics['Evidence retention'] == metrics['Fact retention'] == 100
                and not unsupported_numbers and not fabricated)
    return {
        'metrics': metrics, 'eligible': eligible,
        'editorial_proxy_mean': round(sum(v for k, v in metrics.items() if k not in ('Evidence retention', 'Fact retention')) / 9, 2),
        'characters': len(article), 'duplicate_characters': duplicates,
        'unsupported_number_tokens': unsupported_numbers, 'fabricated_experience_signals': fabricated,
        'article_sha256': digest(article),
        'diagnostic_scope': 'Exact fixture anchors and lexical proxies only; semantic fact review and Production gates still required.',
    }


def compare(case):
    if not case.get('conditions'):
        raise ValueError('Shared article conditions are required')
    # Neither the scorer nor the metrics receive a writer identity or prompt version.
    old = score_article(case['old'], case['evidence'])
    new = score_article(case['new'], case['evidence'])
    if old['eligible'] != new['eligible']:
        winner = 'old' if old['eligible'] else 'new'
    elif not old['eligible']:
        winner = 'needs_review'
    else:
        delta = new['editorial_proxy_mean'] - old['editorial_proxy_mean']
        winner = 'tie' if abs(delta) < 0.01 else ('new' if delta > 0 else 'old')
    return {'id': case['id'], 'old': old, 'new': new, 'winner': winner,
            'shared_input_sha256': digest(json.dumps({'evidence': case['evidence'], 'conditions': case['conditions']}, ensure_ascii=False, sort_keys=True))}


def prompt_arguments(case, style_fn, fact_fn):
    class FixedDate:
        @staticmethod
        def now(tz):
            return datetime(2026, 9, 20, tzinfo=timezone.utc)
    return dict(name=case['id'], url=case['evidence']['url'], stars=0, desc='Offline synthetic editorial fixture',
                source='GitHub', source_context=case['evidence']['text'],
                evidence_metadata={'required_qualifiers': case['evidence']['required_evidence']},
                engagement_labels={'GitHub': 'Stars'}, max_evidence_total_chars=24000,
                truncate_source_context=lambda x: x, source_fact_discipline=fact_fn,
                human_editorial_style_rules=style_fn,
                article_display_variant=lambda _: {'style': 'observation', 'opening': 'fact', 'tone': 'calm'},
                section_split_token='=== ARTICLE START ===', datetime_cls=FixedDate, jst=timezone.utc)


def build_prompt_pair(case):
    """Frozen old/current canonical prompts with identical source and format inputs.

    These are prompt payloads, not generated drafts. Production wrappers are tested
    separately. This offline command can never invoke either Writer.
    """
    if not re.fullmatch(r'[a-z0-9_-]+', case['id']):
        raise ValueError('Invalid fixture id')
    snapshot = json.loads((FIXTURES / (case['id'] + '_prompt.json')).read_text())
    expected = digest(json.dumps({'evidence': case['evidence'], 'conditions': case['conditions']}, ensure_ascii=False, sort_keys=True))
    if snapshot['shared_input_sha256'] != expected or digest(snapshot['prompt']) != snapshot['prompt_sha256']:
        raise ValueError('Frozen baseline does not match evidence/conditions or prompt hash')
    prompt = protocol.build_decision_prompt(**prompt_arguments(case, protocol._human_editorial_style_rules, protocol._source_fact_discipline))
    return {'old': {'system_instruction': None, 'prompt': snapshot['prompt']},
            'new': {'system_instruction': canonical.aiif_editor_persona(), 'prompt': canonical.ensure_final_reader_check(prompt)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    corpus = json.loads((FIXTURES / 'cases.json').read_text())
    results = []
    for case in corpus['cases']:
        result = compare(case)
        payloads = build_prompt_pair(case)
        result['prompts'] = {label: {'sha256': digest(p['prompt']), 'characters': len(p['prompt']),
                                    'system_characters': len(p['system_instruction'] or '')}
                             for label, p in payloads.items()}
        results.append(result)
    report = {'scope': corpus['provenance'], 'base_sha': corpus['base_sha'],
              'model_calls': 0, 'network_calls': 0, 'production_quality_improvement_proven': False,
              'limitations': ['Synthetic authored fixtures are not outputs sampled from old/new models.',
                             'All editorial scores are lexical proxies; continuity, interest and completion require reader review.',
                             'Retention uses exact source anchors, not semantic entailment; no Ready/publication decision is made.'],
              'results': results}
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
