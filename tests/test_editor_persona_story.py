"""Writer payload contracts; all provider sends terminate in a recording SDK fake."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import canonical_article_contract as cac
import pipeline


@pytest.mark.parametrize('kind', ['deep_dive', 'quality_retry'])
@pytest.mark.parametrize('grounded', [False, True])
def test_writer_uses_system_persona_and_one_send_without_changing_tools(monkeypatch, kind, grounded):
    sent = []
    configs = []
    response = SimpleNamespace(text='=== MANAGEMENT DATA ===\nfixture final output')

    def create(**kwargs):
        configs.append(kwargs)
        return SimpleNamespace(send_message=lambda prompt: sent.append(prompt) or response)

    monkeypatch.setattr(pipeline, 'client', SimpleNamespace(chats=SimpleNamespace(create=create)))
    monkeypatch.setattr(pipeline, '_consume_gemini_request', lambda *a, **k: 'fixture-audit')
    monkeypatch.setattr(pipeline, 'GEMINI_USAGE_AUDIT', Mock())
    monkeypatch.setattr(pipeline, '_READY_RESCUE_ACTIVE', False, raising=False)
    monkeypatch.setattr(pipeline, '_should_use_url_context', lambda *a: grounded)
    monkeypatch.setattr(pipeline, 'ENABLE_GOOGLE_SEARCH_GROUNDING', grounded)
    monkeypatch.setattr(pipeline, '_extract_usage_metadata', lambda *a: None)
    monkeypatch.setattr(pipeline, 'extract_grounding_metadata', lambda *a: {'fixture': True})

    def pool(prompt, config, request_kind, **kwargs):
        return pipeline._generate_via_chat('gemini-3.7-flash', prompt, config=config,
                                          request_kind=request_kind), 'gemini-3.7-flash'

    monkeypatch.setattr(pipeline, '_call_deep_dive_pool', pool)
    prompt = pipeline.build_decision_prompt('fixture', 'https://example.com/source', 0, 'fixture',
                                          source_context='Evidence: primary facts and limits')
    prompt = cac.ensure_final_reader_check(prompt)
    result, meta = pipeline.call_gemini_grounded_deep_dive(
        prompt, {}, {'sufficient': True, 'primary_url': 'https://example.com/source'}, request_kind=kind)
    assert result is response and meta == {'fixture': True}
    assert sent == [prompt]
    assert len(configs) == 1
    config = configs[0]['config']
    assert 'AIIF Editor Persona' in config.get('system_instruction', '')
    assert 'AIIF Editor Persona' not in prompt
    assert config['max_output_tokens'] == pipeline.GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS
    assert config.get('tools', []) == ([{'url_context': {}}, {'google_search': {}}] if grounded else [])
    assert prompt.count('AIIF_EDITORIAL_STORY_BRIEF_V1') == 1
    assert prompt.count('AIIF_INTERNAL_SELF_EDIT_V1') == 1
    assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert 'SURPRISE' in prompt and 'TENSION' in prompt and 'HUMAN STAKE' in prompt
    assert 'QUESTION' in prompt and 'PAYOFF' in prompt
    assert 'SOURCE BOUNDARY' in prompt and 'Evidence-to-Decision' in prompt


def test_non_writer_sdk_payload_does_not_acquire_persona(monkeypatch):
    payloads = []
    monkeypatch.setattr(pipeline, 'client', SimpleNamespace(chats=SimpleNamespace(
        create=lambda **k: payloads.append(k) or SimpleNamespace(send_message=lambda p: 'ok'))))
    monkeypatch.setattr(pipeline, '_consume_gemini_request', lambda *a, **k: 'fixture-audit')
    monkeypatch.setattr(pipeline, 'GEMINI_USAGE_AUDIT', Mock())
    monkeypatch.setattr(pipeline, '_READY_RESCUE_ACTIVE', False, raising=False)
    config = {'response_mime_type': 'application/json'}
    assert pipeline._generate_via_chat('gemini-3.7-flash', 'screen', config=config, request_kind='screening') == 'ok'
    assert payloads == [{'model': 'gemini-3.7-flash', 'config': config}]


def test_provider_fallback_keeps_persona_without_new_retry_owner():
    from tests.test_run398_gemini_503_fallback import make_pipeline
    import gemini_provider_resilience
    p, calls, _ = make_pipeline()
    gemini_provider_resilience.install(p)
    config = {'system_instruction': cac.aiif_editor_persona(), 'max_output_tokens': 9000,
              'tools': [{'url_context': {}}]}
    result, selected = p._call_model_pool('writer', config, 'deep_dive', 0,
                                         ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.5-flash'],
                                         deep_dive=True)
    assert selected == 'gemini-3.5-flash'
    assert [model for model, _ in calls] == ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.5-flash']
    for _, sent_config in calls:
        assert sent_config['system_instruction'] == config['system_instruction']
        assert sent_config['tools'] == config['tools']
        assert sent_config['max_output_tokens'] == 9000
    assert 'thinking_config' not in config


def test_complete_production_stack_assembles_story_once_in_isolated_process():
    import os
    import subprocess
    import sys
    code = r'''
import socket
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network forbidden'))
import pipeline as p
import production_pipeline
production_pipeline.install_runtime_layers(p)
for feedback in ('', 'Fact: preserve original claim scope'):
    prompt = p.build_decision_prompt('fixture', 'https://example.com/source', 0, 'fixture',
        source_context='Source-native evidence', quality_feedback=feedback,
        previous_article='Existing scoped article' if feedback else '')
    for marker in ('AIIF_EDITORIAL_STORY_BRIEF_V1', 'AIIF_INTERNAL_SELF_EDIT_V1',
                   'AIIF_CANONICAL_ARTICLE_CONTRACT_V1', 'AIIF_CANONICAL_FINAL_READER_CHECK_V1'):
        assert prompt.count(marker) == 1, (marker, prompt.count(marker))
    for quota in ('原則1〜3箇所', '原則2〜3個', '硬い説明が2段落続いたら', '3,200字はSoft Ceiling'):
        assert quota not in prompt, quota
    assert 'SOURCE BOUNDARY' in prompt and 'Evidence-to-Decision' in prompt
print('production prompt assembly verified')
'''
    env = dict(os.environ, GEMINI_API_KEY='', GH_PAT='', NOTION_API_KEY='',
               GEMINI_PERSISTENT_DAILY_COUNTER='false')
    result = subprocess.run([sys.executable, '-c', code], env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'production prompt assembly verified' in result.stdout


def test_writer_prompt_marks_public_summary_dual_use():
    prompt = pipeline.build_decision_prompt(
        "fixture",
        "https://example.com/source",
        0,
        "fixture",
        source_context="Evidence: primary facts and limits",
    )
    prompt = cac.ensure_final_reader_check(prompt)
    assert "公開Reader Summaryの入力候補" in prompt
    assert "Source Summary / What / Why Important / Decision Reason / Action" in prompt
    assert "公開Reader Summaryへ再利用されるMANAGEMENT DATA" in prompt
    assert "だから読者にとって何が変わるか" in prompt
    assert "技術説明だけの段落が連続" in prompt
    assert "正確な区別に不要なのに繰り返していない" in prompt
