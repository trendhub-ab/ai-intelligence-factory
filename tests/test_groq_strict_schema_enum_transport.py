from ai_provider import GenerationRequest, GroqProvider, ProviderError


def _schema():
    return {
        'type':'object',
        'properties':{
            'decision':{'enum':['NOW','TRY','WATCH','WAIT','AVOID']},
            'score':{'type':'integer','minimum':0,'maximum':100},
        },
        'required':['decision','score'],
        'additionalProperties':False,
    }


def test_string_enum_gets_transport_type_without_mutating_original():
    schema=_schema()
    provider=GroqProvider(lambda _: None,validate_schema=lambda *_:None,token_budget=7000)
    payload,_=provider.prepare(GenerationRequest('test',100,schema,'medium'))
    sent=payload['response_format']['json_schema']['schema']
    assert sent['properties']['decision']=={
        'enum':['NOW','TRY','WATCH','WAIT','AVOID'],
        'type':'string',
    }
    assert 'type' not in schema['properties']['decision']
    assert sent['properties']['score']['minimum']==0
    assert sent['properties']['score']['maximum']==100


def test_non_string_untyped_enum_fails_closed_before_transport():
    schema=_schema()
    schema['properties']['decision']={'enum':[1,2,3]}
    provider=GroqProvider(lambda _: (_ for _ in ()).throw(AssertionError('must not send')),validate_schema=lambda *_:None)
    try:
        provider.prepare(GenerationRequest('test',100,schema))
    except ProviderError as exc:
        assert exc.kind=='strict_schema_invalid'
    else:
        raise AssertionError('expected strict_schema_invalid')
