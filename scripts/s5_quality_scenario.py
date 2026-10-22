"""Real local quality gate. Not a fixture gateway or a public application route."""
import asyncio,json,os,re
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy import select
from httpx import AsyncClient,ASGITransport
from pao.config import ROOT,settings
assert re.fullmatch('pao_s5_quality_[0-9a-f]{32}',make_url(settings().database_url).database)
assert not settings().meta_enabled and not settings().google_ads_enabled
from pao.main import app
from pao.db import Session
from pao.models import User,LlmAttempt,Run
from pao.auth import issue_token
from pao.runtime import execute_run


async def main():
    wid=os.environ['PAO_S5_QUALITY_WORKSPACE'];base=f'/v1/workspaces/{wid}/business-planning'
    async with Session() as db:actor=await db.scalar(select(User).where(User.email=='owner@example.test'))
    headers={'Authorization':'Bearer '+issue_token(actor.id)}
    schema={'type':'object','properties':{'text':{'type':'string','minLength':60,'maxLength':4096}},'required':['text'],'additionalProperties':False}
    async with app.router.lifespan_context(app),AsyncClient(transport=ASGITransport(app=app),base_url='http://test',headers=headers) as client:
        async def api(method,path,body=None):
            response=await client.request(method,path,json=body)
            if response.status_code>=300:raise AssertionError('Quality API denied: '+path.rsplit('/',1)[-1]+' '+str(response.status_code))
            return response.json()
        async def publish(kind,slug,payload):
            data=await api('POST','/v1/studio/definitions',{'workspace_id':wid,'kind':kind,'slug':slug,'name':slug,'payload':payload})
            path='/v1/studio/definitions/'+data['definition']['id']+'/versions/'+data['version']['id']
            fixture='Dữ liệu mẫu chỉ kiểm cấu trúc, không phải suy luận hoặc kết quả kinh doanh thực tế.'
            if kind!='agents':await api('POST',path+'/fixture',{'input':{'text':fixture},'expected_output':{'text':fixture}})
            for action in ('validate','review','publish'):data=await api('POST',path+'/actions/'+action,{'revision':data['definition']['revision'],'self_review':True})
            return data['version']['id']
        agent=await publish('agents','s5-quality-agent',{'instruction':'Soạn bản nháp trung thực từ dữ liệu được cung cấp. Nêu rõ điều chưa biết, không bịa số liệu hoặc ưu đãi.'})
        skill=await publish('skills','s5-quality-draft',{'agent_version_id':agent,'input_schema':schema,'output_schema':schema,
            'instruction':'Đọc JSON tham chiếu trong input.text. Trả đúng một JSON object với trường text gồm ít nhất hai câu tiếng Việt hoàn chỉnh. Câu một nêu tên sản phẩm và giá đúng toàn bộ chữ số nguồn. Câu hai nêu rõ chưa có thông tin khuyến mãi. Kiểm tra từng chữ số trước khi trả lời; không được viết dở hoặc cắt ngang giá. Không thêm ưu đãi, lợi ích hoặc số liệu không có nguồn. Không nói đã đăng bài. Không viết suy nghĩ.',
            'timeout_seconds':120,'token_budget':8192,'output_tokens':512,'exit_criteria':['non_empty:text']})
        catalogue=await api('GET','/v1/engines?workspace_id='+wid)
        models=next(v['models'] for v in catalogue['engines'] if v['provider']=='ollama')
        installed='qwen3:4b-instruct-2507-q4_K_M';assert installed in models
        await api('PUT',base+'/routing',{'expected_revision':0,'request_key':str(uuid4()),'content':{
            'targets':[{'key':'local','provider':'ollama','model':installed}],'default_target':'local',
            'limits':{'token_budget':8192,'output_tokens':512,'timeout_seconds':120},
            'specialists':[{'kind':kind,'skill_version_id':skill} for kind in ('analyst','content')]}})
        profile=await api('PUT',base+'/profile',{'expected_revision':0,'request_key':str(uuid4()),'content':{
            'description':'Dữ liệu thử tổng hợp, không phải khách hàng thật','products':['Mẫu A: giá 250000 VND; chưa có thông tin khuyến mãi'],
            'audience':'Người mua thử nghiệm','brand_voice':'Rõ ràng và trung thực','objectives':['Soạn bản nháp, không đăng thật'],
            'resources':'Chủ doanh nghiệp duyệt nội dung','currency':'VND','timezone':'Asia/Ho_Chi_Minh'}})
        path=base+'/plans/'+str(uuid4())
        plan=await api('PUT',path,{'expected_revision':0,'request_key':str(uuid4()),'profile_id':profile['id'],'profile_revision':1,'content':{
            'title':'Nghiệm thu local bằng dữ liệu tổng hợp','month':'2026-10-01','campaign_brief':'Soạn bản nháp, không đăng hoặc quảng cáo thật',
            'deliverables':[{'key':'research','title':'Tóm tắt dữ kiện sản phẩm','specialist':'analyst','due_date':'2026-10-23',
                'brief':'Tóm tắt sản phẩm, giá và thông tin khuyến mãi còn thiếu.','acceptance':['Đúng tên, đúng giá, không bịa khuyến mãi'],'depends_on':[]},
                {'key':'content','title':'Bản nháp nội dung','specialist':'content','due_date':'2026-10-24','brief':'Soạn bản nháp Facebook trung thực từ dữ kiện đã duyệt.',
                'acceptance':['Đúng giá và nêu dữ liệu còn thiếu; không đăng thật'],'depends_on':['research']}]}})
        reviewed=await api('POST',path+'/review',{'request_key':str(uuid4()),'revision':1,'content_hash':plan['content_hash'],
            'decision':'approve','self_review':True,'acknowledge_missing':True})
        await api('POST',path+'/materialize',{'request_key':str(uuid4()),'revision':1,'review_id':reviewed['id'],'content_hash':plan['content_hash'],'confirm_drafts_only':True})
        outcomes=[]
        for item in ('research','content'):
            job=await api('POST',path+'/jobs',{'request_key':str(uuid4()),'routing_revision':1,'plan_revision':1,'item_key':item,'confirm_model_call':True})
            await execute_run({},job['run_id'])
            result=await api('GET',base+'/jobs/'+job['id'])
            if result['status']!='completed':
                (ROOT/'.runtime/s5-local-quality.json').write_text(json.dumps({'pass':False,'stage':item,'error_code':result['error_code'],'provider':'ollama','model':installed}),encoding='utf-8')
                raise AssertionError('Real local generation did not complete: '+str(result['error_code']))
            text=result['artifact']['text'];folded=text.casefold();compact=re.sub(r'[\s.,]','',folded)
            quality={'product_correct':'mẫu a' in folded,'price_correct':'250000' in compact,
                'missing_promotion_explicit':'khuyến mãi' in folded and ('chưa' in folded or 'không có' in folded),
                'no_publish_claim':'đã đăng' not in folded,'no_invented_discount':not re.search(r'\d+\s*%',text)}
            outcomes.append({'step':item,'quality':quality,'text':text})
            if not all(quality.values()):
                (ROOT/'.runtime/s5-local-quality.json').write_text(json.dumps({'pass':False,'outcomes':outcomes},ensure_ascii=False),encoding='utf-8')
                raise AssertionError('Local quality rubric failed; no auto approval')
            await api('POST',base+'/jobs/'+job['id']+'/review',{'request_key':str(uuid4()),'decision':'approve','artifact_hash':result['artifact_hash'],'confirm_review':True})
        async with Session() as db:
            attempts=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.workspace_id==wid)))
            assert len(attempts)==2 and all(a.status=='completed' and a.usage_state=='reported' for a in attempts)
        result={'pass':True,'real_local_inference':True,'synthetic_business_data':True,'provider':'ollama','model':installed,
            'distinct_live_models':1,'two_model_assignment':'separate_fixture_gate','steps':outcomes,'reported_usage':True,
            'cloud_calls':False,'external_actions':False,'primary_rollout':False}
        (ROOT/'.runtime/s5-local-quality.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='steps'}))


if __name__=='__main__':asyncio.run(main())
