import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.db import Session
from pao.models import BrainNote,BrainNoteVersion
from pao.modules.brains import files
from test_brain_manager import create,brains_on
from test_brain_files import upload

async def add(client,identity,bid,content='First'):
    response=await client.post(f'/v1/brains/{bid}/notes',headers=identity['owner'],json={'title':'Note','content':content})
    assert response.status_code==201,response.text
    return response

async def test_notes_etag_versions_conflict_trash_restore(client,identity,brains_on):
    bid=(await create(client,identity))['id'];h=identity['owner'];first=await add(client,identity,bid)
    row=first.json();base=f"/v1/brains/{bid}/notes/{row['id']}";tag=first.headers['etag']
    assert (await client.patch(base,headers=h,json={'title':'Edit','content':'Second'})).status_code==428
    second=await client.patch(base,headers={**h,'If-Match':tag},json={'title':'Edit','content':'Second'})
    assert second.status_code==200 and second.json()['content_version']==2
    assert (await client.patch(base,headers={**h,'If-Match':tag},json={'title':'Stale','content':'Bad'})).status_code==412
    assert (await client.get(base+'/versions/1',headers=h)).json()['content']=='First'
    assert (await client.get(base+'/versions/0',headers=h)).status_code==422
    for path in (base,base+'/versions/1',f'/v1/brains/{bid}/notes'):
        assert (await client.get(path,headers=identity['other'])).status_code==404
    trashed=await client.delete(base,headers={**h,'If-Match':second.headers['etag']})
    assert trashed.status_code==200 and trashed.json()['content_version']==2
    tag3=f'"note-{row["id"]}-r3"'
    assert (await client.patch(base,headers={**h,'If-Match':tag3},json={'title':'No','content':'No'})).status_code==409
    assert (await client.post(base+'/restore',headers={**h,'If-Match':tag3})).json()['revision']==4
    assert (await client.get(base,headers=h)).json()['content']=='Second'
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainNoteVersion))==2

async def test_note_versions_are_database_immutable(client,identity,brains_on):
    bid=(await create(client,identity))['id'];row=(await add(client,identity,bid)).json()
    async with Session() as db:
        with pytest.raises(DBAPIError):
            await db.execute(text('UPDATE brain_note_versions SET content=:content,size=4 WHERE note_id=:id'),{'content':'evil','id':row['id']})
        await db.rollback()
    assert (await client.get(f"/v1/brains/{bid}/notes/{row['id']}",headers=identity['owner'])).json()['content']=='First'

async def test_note_quota_counts_versions_and_files_and_trash(client,identity,brains_on,monkeypatch):
    bid=(await create(client,identity))['id'];h=identity['owner']
    monkeypatch.setattr(files,'BRAIN_QUOTA_BYTES',10)
    first=await add(client,identity,bid,'12345');row=first.json();base=f"/v1/brains/{bid}/notes/{row['id']}"
    second=await client.patch(base,headers={**h,'If-Match':first.headers['etag']},json={'title':'Second','content':'67890'})
    assert second.status_code==200
    assert (await upload(client,identity,bid,content=b'x')).status_code==409
    await client.delete(base,headers={**h,'If-Match':second.headers['etag']})
    assert (await upload(client,identity,bid,content=b'x')).status_code==409
    assert (await client.post(f'/v1/brains/{bid}/notes',headers=h,json={'title':'No quota','content':'x'})).status_code==409
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainNote))==1

async def test_invalid_unicode_rolls_back_note_metadata(client,identity,brains_on):
    bid=(await create(client,identity))['id']
    response=await client.post(f'/v1/brains/{bid}/notes',headers={**identity['owner'],'Content-Type':'application/json'},
        content=b'{"title":"Note","content":"\\ud800"}')
    assert response.status_code==422
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainNote))==0

async def test_validation_does_not_reflect_private_content(client,identity,brains_on):
    bid=(await create(client,identity))['id']
    response=await client.post(f'/v1/brains/{bid}/notes',headers=identity['owner'],json={
        'title':'Note','content':'private-content','unexpected':'private-token'})
    assert response.status_code==422
    assert 'private-content' not in response.text and 'private-token' not in response.text

@pytest.mark.parametrize('chunked',[False,True])
@pytest.mark.parametrize('mime',['application/json','application/vendor.note+json','text/plain'])
async def test_note_json_size_is_bounded_before_parsing(client,identity,brains_on,chunked,mime):
    bid=(await create(client,identity))['id']
    headers={**identity['owner'],'Content-Type':mime}
    async def chunks():
        for _ in range(4):yield b'x'*200000
    content=chunks() if chunked else b'x'*800000
    response=await client.post(f'/v1/brains/{bid}/notes',headers=headers,content=content)
    assert response.status_code==413,response.text
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainNote))==0
