import json
import httpx
import pytest
from pao.gateway import AnthropicGateway, GeminiGateway, OllamaGateway, OpenAICompatibleGateway


async def test_gateway_filters_thinking_and_requires_done(monkeypatch):
    real_client = httpx.AsyncClient
    def respond(request):
        body = json.loads(request.content)
        assert body['think'] is False
        assert body['options']['num_predict'] == 512
        return httpx.Response(200, text='\n'.join([
            json.dumps({'message': {'thinking': 'PRIVATE_INTERNAL_TEXT', 'content': 'Hello'}}),
            json.dumps({'done': True, 'eval_count': 1}),
        ]))
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs))
    chunks = [c async for c in OllamaGateway().stream([{'role': 'user', 'content': 'hello'}])]
    assert ''.join(c.text for c in chunks) == 'Hello'
    assert chunks[-1].usage == {'eval_count': 1}


async def test_gateway_rejects_truncated_ndjson(monkeypatch):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text='{"message":{"content":"partial"}}\n')), **kwargs))
    with pytest.raises(RuntimeError, match='incomplete_stream'):
        _ = [c async for c in OllamaGateway().stream([])]


@pytest.mark.parametrize('vector', [[1.0]*12, [0.0]*768, [float('nan')]+[1.0]*767])
async def test_embedding_rejects_invalid_provider_vectors(monkeypatch, vector):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=json.dumps({'embeddings':[vector]}))), **kwargs))
    with pytest.raises(ValueError):
        await OllamaGateway().embed('Business fact')


async def test_extraction_requires_schema_and_ignores_thinking(monkeypatch):
    real_client = httpx.AsyncClient
    def respond(request):
        body = json.loads(request.content)
        assert body['format']['additionalProperties'] is False
        return httpx.Response(200, json={'done':True, 'message': {
            'thinking':'PRIVATE', 'content':json.dumps({'facts':[{'key':'market','value':'Malaysia','importance':4}]})}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs))
    facts = await OllamaGateway().extract('My market is Malaysia')
    assert facts.facts[0].value == 'Malaysia'


async def test_extraction_rejects_unvalidated_output(monkeypatch):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            'done':True,'message':{'content':'{"facts":[{"key":"market","value":"Malaysia","importance":99}]}'}})), **kwargs))
    with pytest.raises(ValueError):
        await OllamaGateway().extract('My market is Malaysia')


async def test_openai_compatible_stream(monkeypatch):
    real_client=httpx.AsyncClient
    def respond(request):
        assert request.headers['authorization']=='Bearer cloud-secret'
        return httpx.Response(200,text='data: '+json.dumps({'choices':[{'delta':{'content':'PAO '},'finish_reason':None}]})+'\n\n'
            +'data: '+json.dumps({'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}],'usage':{'total_tokens':4}})+'\n\n'
            +'data: [DONE]\n\n')
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(respond),**kwargs))
    gateway=OpenAICompatibleGateway('openai','cloud-secret','gpt-test','https://api.openai.test/v1')
    chunks=[x async for x in gateway.stream([{'role':'user','content':'test'}])]
    assert ''.join(x.text for x in chunks)=='PAO OK' and chunks[-1].usage['total_tokens']==4


async def test_anthropic_stream(monkeypatch):
    real_client=httpx.AsyncClient
    body='\n'.join(['event: content_block_delta','data: '+json.dumps({'type':'content_block_delta','delta':{'type':'text_delta','text':'PAO'}}),'event: message_stop','data: {"type":"message_stop"}'])
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(lambda request:httpx.Response(200,text=body)),**kwargs))
    chunks=[x async for x in AnthropicGateway('key','claude-test').stream([{'role':'user','content':'test'}])]
    assert ''.join(x.text for x in chunks)=='PAO'


async def test_gemini_stream(monkeypatch):
    real_client=httpx.AsyncClient
    body='data: '+json.dumps({'candidates':[{'content':{'parts':[{'text':'PAO'}]},'finishReason':'STOP'}]})+'\n\n'
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(lambda request:httpx.Response(200,text=body)),**kwargs))
    chunks=[x async for x in GeminiGateway('key','gemini-test').stream([{'role':'user','content':'test'}])]
    assert ''.join(x.text for x in chunks)=='PAO'
