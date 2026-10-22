"""Disposable S5 browser fixture only. Never imported by the production app."""
import asyncio,json,os,re
from sqlalchemy.engine import make_url
from fastapi import Depends,Header,HTTPException
from pydantic import BaseModel
from pao.config import settings

assert os.environ.get('PAO_S5_BROWSER_TEST')=='1'
assert re.fullmatch('pao_s5_browser_[0-9a-f]{32}',make_url(settings().database_url).database)
assert make_url(settings().database_url).host=='127.0.0.1'
assert len(os.environ.get('PAO_S5_BROWSER_KEY',''))>=32
from pao.main import app
from pao.auth import principal
from pao.db import Session
from pao.models import Run,ChatSession
from pao.gateway import Chunk
from pao.runtime import execute_run
from pao.modules.engines import service


async def catalogue():return ['qwen3:4b','qwen3:8b']
service.local_models=catalogue


class Drain(BaseModel):
    run_id:str


@app.post('/_s5_fixture/drain')
async def drain(body:Drain,who=Depends(principal),x_fixture_key:str=Header()):
    import secrets
    if not secrets.compare_digest(x_fixture_key,os.environ['PAO_S5_BROWSER_KEY']):raise HTTPException(404)
    async with Session() as db:
        row=await db.get(Run,body.run_id)
        chat=await db.get(ChatSession,row.session_id) if row else None
        if not row or not chat or chat.user_id!=who.id:raise HTTPException(404)
        model=row.engine_snapshot['model']
    class Fixture:
        provider_name='ollama'
        model_name=model
        async def stream(self,messages,max_tokens=None):
            yield Chunk(text=json.dumps({'text':'Bản nháp mô phỏng để duyệt. Chưa có số liệu thực tế.'},ensure_ascii=False),usage={'input_tokens':300,'output_tokens':40})
    await execute_run({'gateway':Fixture()},body.run_id)
    return {'fixture_only':True,'model_calls':False}


if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=18102,access_log=False)
