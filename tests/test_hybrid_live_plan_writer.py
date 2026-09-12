import json

from hybrid_live_plan_writer import build_live_writer_fixture

INPUT='tests/fixtures/groq/article_parity_B0049_input.json'
PLAN='tests/fixtures/groq/two_pass_v3_plan_safe_report.json'


def test_live_fixture_metadata_distinguishes_live_groq_plan(tmp_path):
    out=tmp_path/'live-fixture.json'
    fixture=build_live_writer_fixture(INPUT, PLAN, str(out))
    assert fixture['plan_provider']=='groq'
    assert fixture['plan_source']=='live_groq_report'
    assert fixture['provider_calls_expected']=={'groq_live':1,'gemini_live_max':2}
    assert fixture['validation_scope']=='live_groq_plan_to_bounded_gemini_writer'
    assert fixture['business_writes']==0
    assert fixture['persist_results'] is False
    saved=json.loads(out.read_text(encoding='utf-8'))
    assert saved['plan_source']=='live_groq_report'
