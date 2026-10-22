import hashlib,io,json,zipfile
from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from pao.db import Session
from pao.models import BrainFile,BrainNote,BrainImportPlan,now
from pao.modules.brains import portable,files
from test_brain_manager import create,brains_on
from test_brain_files import upload
from test_brain_notes import add

def archive(content=b'Hello',extra=None,compression=zipfile.ZIP_STORED,symlink=False,mutate=None):
    path=f'files/{uuid4()}.txt';item={'kind':'file','path':path,'name':'safe.txt','mime':'text/plain','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    manifest={'format':portable.FORMAT,'name':'Portable','items':[item]}
    if mutate:mutate(manifest)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=compression) as z:
        if symlink:
            info=zipfile.ZipInfo(path);info.create_system=3;info.external_attr=(0o120777<<16);z.writestr(info,content)
        else:z.writestr(path,content)
        z.writestr('manifest.json',json.dumps(manifest))
        if extra:z.writestr(extra,b'not executed')
    return output.getvalue()

async def preview(client,identity,bid,raw):
    return await client.post(f'/v1/brains/{bid}/imports/preview',headers={**identity['owner'],'Content-Type':'application/zip'},content=raw)
def confirmation(plan):return {'sha256':plan['sha256'],'brain_revision':plan['brain_revision'],'confirmed':True}

async def test_portable_roundtrip_dry_run_explicit_confirmation_idempotent_content(client,identity,brains_on):
    source=(await create(client,identity,'Source'))['id'];target=(await create(client,identity,'Target'))['id'];h=identity['owner']
    await upload(client,identity,source,content=b'Original')
    await add(client,identity,source,'\ufeffUnicode note')
    exported=await client.get(f'/v1/brains/{source}/export',headers=h)
    assert exported.status_code==200 and exported.headers['x-archive-sha256']==hashlib.sha256(exported.content).hexdigest()
    assert len(portable.read_archive(exported.content))==2
    result=await preview(client,identity,target,exported.content);assert result.status_code==200,result.text
    plan=result.json();assert len(plan['add'])==2 and plan['confirmation_required'] and not plan['overwrite']
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainFile).where(BrainFile.brain_id==target))==0
        assert await db.scalar(select(func.count()).select_from(BrainNote).where(BrainNote.brain_id==target))==0
    url=f"/v1/brains/{target}/imports/{plan['plan_id']}/confirm"
    assert (await client.post(url,headers=h,json={**confirmation(plan),'confirmed':False})).status_code==422
    confirmed=await client.post(url,headers=h,json=confirmation(plan));assert confirmed.status_code==200,confirmed.text
    assert len(confirmed.json()['files'])==len(confirmed.json()['notes'])==1
    assert (await client.post(url,headers=h,json=confirmation(plan))).status_code==409
    again=(await preview(client,identity,target,exported.content)).json()
    assert again['add']==[] and len(again['skip'])==2
    contents=portable.read_archive((await client.get(f'/v1/brains/{target}/export',headers=h)).content)
    assert sorted(content for _,content in contents)==sorted(content for _,content in portable.read_archive(exported.content))

async def test_plan_revision_actor_expiry_and_hash_guards(client,identity,brains_on):
    bid=(await create(client,identity))['id'];h=identity['owner'];raw=archive()
    plan=(await preview(client,identity,bid,raw)).json();url=f"/v1/brains/{bid}/imports/{plan['plan_id']}/confirm"
    assert (await client.post(url,headers=identity['other'],json=confirmation(plan))).status_code==404
    assert (await client.post(url,headers=h,json={**confirmation(plan),'sha256':'0'*64})).status_code==409
    await upload(client,identity,bid)
    assert (await client.post(url,headers=h,json=confirmation(plan))).status_code==409
    expired=(await preview(client,identity,bid,raw)).json()
    async with Session.begin() as db:
        row=await db.get(BrainImportPlan,expired['plan_id']);row.expires_at=now()-timedelta(seconds=1)
    assert (await client.post(f"/v1/brains/{bid}/imports/{expired['plan_id']}/confirm",headers=h,json=confirmation(expired))).status_code==409

@pytest.mark.parametrize('case',['traversal','script','symlink','bomb','hash','unknown','duplicate-json','too-many','prefix'])
def test_zip_safety_never_extracts_or_executes(case):
    if case=='traversal':raw=archive(extra='../escape.txt')
    elif case=='script':raw=archive(extra='install.py')
    elif case=='symlink':raw=archive(symlink=True)
    elif case=='bomb':raw=archive(content=b'x'*100000,compression=zipfile.ZIP_DEFLATED)
    elif case=='hash':raw=archive(mutate=lambda m:m['items'][0].update(sha256='0'*64))
    elif case=='unknown':raw=archive(mutate=lambda m:m.update(credentials='not accepted'))
    elif case=='prefix':raw=b'EXE'+archive()
    elif case=='too-many':
        raw=bytearray(archive());end=raw.rfind(b'PK\x05\x06');raw[end+8:end+12]=b'\xff\xff\xff\xff';raw=bytes(raw)
    else:
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as z:z.writestr('manifest.json','{"format":"one","format":"two","name":"X","items":[]}')
        raw=output.getvalue()
    with pytest.raises(HTTPException) as error:portable.read_archive(raw)
    assert error.value.status_code in (415,422)

async def test_import_quota_atomic_rollback_keeps_plan_unused(client,identity,brains_on,monkeypatch):
    bid=(await create(client,identity))['id'];h=identity['owner'];plan=(await preview(client,identity,bid,archive(content=b'12345'))).json()
    monkeypatch.setattr(files,'BRAIN_QUOTA_BYTES',4)
    response=await client.post(f"/v1/brains/{bid}/imports/{plan['plan_id']}/confirm",headers=h,json=confirmation(plan))
    assert response.status_code==409
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainFile))==0
        assert (await db.get(BrainImportPlan,plan['plan_id'])).consumed_at is None

async def test_staged_plan_count_bounded(client,identity,brains_on):
    bid=(await create(client,identity))['id']
    for _ in range(3):assert (await preview(client,identity,bid,archive())).status_code==200
    assert (await preview(client,identity,bid,archive())).status_code==409
