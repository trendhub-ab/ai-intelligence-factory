import json

from groq_plan_diagnostic import failed_generation_schema_diagnostic


SCHEMA={
    'type':'object',
    'properties':{
        'decision':{'type':'string','enum':['WATCH','WAIT']},
        'score':{'type':'integer','minimum':0,'maximum':100},
        'reasons':{'type':'array','items':{'type':'string'}},
    },
    'required':['decision','score','reasons'],
    'additionalProperties':False,
}


def test_structural_diagnostic_exposes_no_generated_values():
    raw=json.dumps({
        'decision':'UNSAFE_SECRET_VALUE',
        'score':'82',
        'extra_secret_key':'DO_NOT_PERSIST_THIS',
    })
    diag=failed_generation_schema_diagnostic(raw,SCHEMA)
    assert diag['present'] is True
    assert diag['json_parseable'] is True
    assert diag['schema_error_count'] >= 4
    serialized=json.dumps(diag,ensure_ascii=False)
    assert 'UNSAFE_SECRET_VALUE' not in serialized
    assert 'DO_NOT_PERSIST_THIS' not in serialized
    assert 'extra_secret_key' not in serialized
    assert any(i.get('missing_required')==['reasons'] for i in diag['issues'])
    assert any(i.get('path')=='$.score' and i.get('actual_type')=='string' for i in diag['issues'])
    assert any(i.get('path')=='$.decision' and i.get('allowed_enum')==['WATCH','WAIT'] for i in diag['issues'])
    assert any(i.get('extra_property_count')==1 for i in diag['issues'])


def test_unparseable_generation_reports_shape_not_content():
    raw='TOP SECRET non-json generation'
    diag=failed_generation_schema_diagnostic(raw,SCHEMA)
    assert diag['json_parseable'] is False
    assert diag['raw_char_count']==len(raw)
    assert diag['json_parse_error']=='JSONDecodeError'
    assert 'TOP SECRET' not in json.dumps(diag)


def test_absent_generation_is_safe():
    diag=failed_generation_schema_diagnostic(None,SCHEMA)
    assert diag=={'present':False,'json_parseable':False,'top_level_type':'null'}
