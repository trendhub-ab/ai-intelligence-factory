"""Advisory diagnostics must improve existing retries without reducing eligibility."""
from types import SimpleNamespace

import editorial_naturalness as en
from a_plus_editorial_orchestration import install


def repetitive_article():
    return '\n\n'.join(
        f'## 比較条件{i}\n公式資料の条件{i}を確認した。つまり、比較範囲を揃える必要があります。私なら条件{i}のログを比較します。'
        for i in range(1, 4)
    )


def diagnose(text):
    detector = getattr(en, 'naturalness_v2_signals', None)
    assert callable(detector), 'provider-free advisory v2 detector is missing'
    return detector(text)


def test_multiple_repeated_habits_produce_located_advice():
    result = diagnose(repetitive_article())
    assert result['repair_recommended'] is True
    assert result['repeated_self_closings'] == [1, 2, 3]
    assert result['repeated_meta_summaries'] == [1, 2, 3]


def test_single_natural_decision_and_one_habit_alone_need_no_repair():
    assert not diagnose('## 計測条件\nつまり、測定条件が違います。私なら遅延を比較します。')['repair_recommended']
    text = '\n\n'.join(f'## 条件{i}\n私なら条件{i}を比較します。' for i in range(3))
    assert not diagnose(text)['repair_recommended']


def test_quotes_code_and_source_sections_are_not_authorial_habits():
    text = '\n\n'.join(
        f'## 条件{i}\n> つまり、条件次第です。私なら比較します。\n\n'
        '```text\nつまり、条件次第です。私なら比較します。\n```\n'
        '「つまり、条件次第です。私なら比較します。」と原資料にある。'
        for i in range(3)
    ) + '\n## Sources / Evidence\n' + repetitive_article().replace('## ', '### ')
    assert not diagnose(text)['repair_recommended']


def test_retry_contract_targets_only_detected_habits_and_preserves_evidence():
    builder = getattr(en, 'build_naturalness_retry_contract', None)
    assert callable(builder), 'targeted retry contract is missing'
    assert builder('自然な短文です。') == ''
    contract = builder(repetitive_article())
    for required in ('私なら', 'メタ要約', '1, 2, 3', 'Fact', 'Evidence', 'Decision', '情報量'):
        assert required in contract
    assert '自然な単発表現' in contract


def runtime(article, allowed=True):
    calls = []
    parsed = {'note_draft': article}
    def provider(prompt, repo, source_info, **kwargs):
        calls.append((prompt, kwargs))
        return SimpleNamespace(text='unchanged provider result'), {'grounding_status': 'test'}
    p = SimpleNamespace(
        build_decision_prompt=lambda **kw: 'base prompt',
        _parse_gemini_response=lambda *a, **kw: parsed,
        should_attempt_dynamic_retry=lambda *a, **kw: (allowed, 'existing policy'),
        call_gemini_grounded_deep_dive=provider,
        generate_intelligence_report=lambda: None,
    )
    install(p)
    p._parse_gemini_response('response')
    p.build_decision_prompt(previous_article=article)
    return p, calls


def test_existing_retry_receives_advice_with_exactly_one_provider_call():
    p, calls = runtime(repetitive_article())
    assert p.should_attempt_dynamic_retry([], {}) == (True, 'existing policy')
    result = p.call_gemini_grounded_deep_dive('retry prompt', {}, {}, request_kind='quality_retry')
    assert len(calls) == 1
    assert 'naturalness-v2' in calls[0][0]
    assert '1, 2, 3' in calls[0][0]
    assert result[0].text == 'unchanged provider result'


def test_initial_call_and_clean_retry_are_unchanged():
    for article, kind in [(repetitive_article(), 'deep_dive'), ('自然な短文です。', 'quality_retry')]:
        p, calls = runtime(article)
        p.call_gemini_grounded_deep_dive('original', {}, {}, request_kind=kind)
        assert len(calls) == 1
        assert calls[0][0] == 'original'


def test_advice_cannot_authorize_retry_or_leak_into_next_article():
    p, calls = runtime(repetitive_article(), allowed=False)
    assert p.should_attempt_dynamic_retry([], {}) == (False, 'existing policy')
    assert calls == []
    p.generate_intelligence_report()
    p.call_gemini_grounded_deep_dive('next article', {}, {}, request_kind='quality_retry')
    assert calls[0][0] == 'next article'


def test_uniform_sections_are_advisory_only_with_repeated_grand_closings():
    sections = [f'## 検証条件{i}\n' + f'公式資料では条件{i}の測定方法と対象範囲を公開しています。' * 4 + 'これは未来を変える大きな転換点です。' for i in range(5)]
    result = diagnose('\n\n'.join(sections))
    assert result['uniform_sections'] is True
    assert result['repeated_grand_closings'] == [1, 2, 3, 4, 5]
    assert result['repair_recommended'] is True
    assert not diagnose('\n\n'.join(s.replace('これは未来を変える大きな転換点です。', '') for s in sections))['repair_recommended']


def test_ready_yield_guard_preserves_existing_detector_outputs():
    # Frozen from main before v2: advisory diagnostics cannot change eligibility.
    cases = [('', 0, False), ('興味深い機能です。', 0, False), (repetitive_article(), 3, False)]
    for article, score, high in cases:
        diagnose(article)
        result = en.ai_style_composite_signals(article, [])
        assert (result['score'], result['high']) == (score, high)


def test_retry_advice_uses_actual_previous_article_after_polish():
    p, calls = runtime(repetitive_article())
    polished = '## 新しい導入\n公開された仕様です。\n\n' + repetitive_article()
    p.build_decision_prompt(previous_article=polished)
    p.call_gemini_grounded_deep_dive('polished retry', {}, {}, request_kind='quality_retry')
    assert '節 2, 3, 4:' in calls[0][0]
    assert '節 1, 2, 3:' not in calls[0][0]
    p.build_decision_prompt(previous_article='整理済みの自然な記事です。')
    p.call_gemini_grounded_deep_dive('clean retry', {}, {}, request_kind='quality_retry')
    assert calls[1][0] == 'clean retry'


def test_provider_failure_keeps_existing_local_fallback(monkeypatch):
    import a_plus_editorial_orchestration as layer
    calls = []
    class NoAvailableModelError(Exception):
        pass
    def unavailable(*args, **kwargs):
        calls.append(kwargs['request_kind'])
        raise NoAvailableModelError()
    seed = {
        'note_draft': repetitive_article(), 'source_summary_text': '公式発表。',
        'what_text': '仕様変更。', 'why_important_text': '比較条件が変わる。',
        'decision_text': 'TRY', 'decision_reason_text': '限定検証が可能。',
        'action_text': '限定環境で比較。', 'score': 82,
    }
    p = SimpleNamespace(
        build_decision_prompt=lambda **kw: 'base prompt',
        _parse_gemini_response=lambda *a, **kw: seed,
        should_attempt_dynamic_retry=lambda *a, **kw: (True, 'existing policy'),
        call_gemini_grounded_deep_dive=unavailable,
        generate_intelligence_report=lambda: None,
    )
    # The renderer is an external boundary here; its real compiler has its own tests.
    monkeypatch.setattr(layer, 'render_provider_compatible_fallback', lambda *a, **kw: ('local manuscript', {}))
    install(p)
    p._parse_gemini_response('response')
    p.build_decision_prompt(previous_article=seed['note_draft'])
    p.should_attempt_dynamic_retry([], {'state': 'SUFFICIENT'})
    response, grounding = p.call_gemini_grounded_deep_dive('retry', {}, {}, request_kind='quality_retry')
    assert response.text == 'local manuscript'
    assert grounding['a_plus_local_fallback'] is True
    assert calls == ['quality_retry']
