import pytest
from pao.modules.installation_ai.catalog import normalize,selection
from pao.modules.cli_connections.catalog import models

def test_catalog_preserves_many_models_and_native_effort_order():
    rows=models({'data':[{'model':'fixture-A','isDefault':True,'displayName':'Fixture A','supportedReasoningEfforts':[
        {'reasoningEffort':'high'},{'reasoningEffort':'low'}],'defaultReasoningEffort':'low'},
        {'model':'fixture-B','isDefault':False}],'nextCursor':None})
    catalog=normalize(rows)
    assert len(catalog)==2 and catalog[0]['reasoning_efforts']==['high','low']
    assert selection(catalog,'fixture-A','high')=={'model':'fixture-A','reasoning_effort':'high'}
    assert selection(catalog,'fixture-B')=={'model':'fixture-B','reasoning_effort':None}
    with pytest.raises(ValueError):selection(catalog,'fixture-B','high')
    with pytest.raises(ValueError):selection(catalog,'not-listed')

@pytest.mark.parametrize('rows',[[],['x','x'],[{'model':'model','reasoning_efforts':['low','low']}],
    [{'model':'model','reasoning_efforts':['high'],'default_effort':'low'}],['../invalid'],[{'model':'model','display_name':'bad\nname'}],
    [{'model':'model','reasoning_efforts':[{}]}]])
def test_invalid_catalog_is_rejected(rows):
    with pytest.raises(ValueError):normalize(rows)


async def test_native_catalog_paginates_without_inference_or_unbounded_cursor():
    from pao.modules.cli_connections.catalog import CatalogTransport
    class Fake(CatalogTransport):
        def __init__(self):self.sent=[];self.page=0
        async def open(self):pass
        async def authorize(self):pass
        async def rpc(self,ident,method,params):
            assert method=='account/read' and params=={'refreshToken':False}
            return {'account':{'type':'chatgpt'}}
        async def send(self,value):self.sent.append(value)
        async def receive(self):
            self.page+=1
            return {'id':2+self.page,'result':{'data':[{'model':'fixture-'+str(self.page),'isDefault':self.page==1}],
                'nextCursor':'opaque-next' if self.page==1 else None}}
    value=Fake();result=await value.read()
    assert [row['model'] for row in result]==['fixture-1','fixture-2']
    assert [row['method'] for row in value.sent]==['model/list','model/list']
    assert value.sent[1]['params']['cursor']=='opaque-next'
