import hashlib
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import BrainFile,Brain
from pao.modules.brains import files
from test_brain_manager import create,brains_on

async def upload(client,identity,bid,name='source.md',content=b'# private source',mime='text/markdown',headers=None):
    return await client.post(f'/v1/brains/{bid}/files',params={'name':name},
        headers={**(headers or identity['owner']),'Content-Type':mime},content=content)


async def test_file_roundtrip_private_plain_preview_trash_restore(client,identity,brains_on):
    bid=(await create(client,identity))['id'];h=identity['owner']
    source=b'<script>window.mustNotRun=1</script>'
    result=await upload(client,identity,bid,content=source)
    assert result.status_code==201,result.text
    row=result.json();fid=row['id']
    assert 'content' not in row and row['sha256']==hashlib.sha256(source).hexdigest()
    base=f'/v1/brains/{bid}/files/{fid}'
    download=await client.get(base+'/download',headers=h)
    assert download.content==source and download.headers['content-disposition'].startswith('attachment;')
    assert download.headers['x-content-type-options']=='nosniff'
    assert 'sandbox' in download.headers['content-security-policy']
    assert download.headers['etag']=='"'+row['sha256']+'"'
    assert (await client.get(base+'/preview',headers=h)).json()['format']=='plain_text'
    for path in (base+'/download',base+'/preview',f'/v1/brains/{bid}/files'):
        assert (await client.get(path,headers=identity['other'])).status_code==404
    trash=await client.delete(base+'?revision=1',headers=h)
    assert trash.status_code==200 and trash.json()['trashed_at']
    assert (await client.get(base+'/download',headers=h)).status_code==409
    assert (await client.post(base+'/restore?revision=1',headers=h)).status_code==409
    restored=await client.post(base+'/restore?revision=2',headers=h)
    assert restored.status_code==200 and restored.json()['sha256']==row['sha256']
    assert (await client.get(base+'/download',headers=h)).content==source


@pytest.mark.parametrize('name',['../secret.txt','C:\\secret.txt','CON.txt','CON .txt','a\n.txt','a\x00.txt','folder/file.txt','file.txt.',' file.txt','evil.html','tool.py','archive.zip','／escape.txt'])
async def test_unsafe_names_rejected_without_orphan(client,identity,brains_on,name):
    bid=(await create(client,identity))['id']
    assert (await upload(client,identity,bid,name=name,mime='text/plain')).status_code in (415,422)
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainFile))==0
        assert (await db.get(Brain,bid)).revision==1


@pytest.mark.parametrize('payload,mime',[(b'\xff','text/plain'),(b'\x00','text/plain'),(b'%PDF-1.7','application/pdf'),(b'\x89PNG','image/png')])
async def test_binary_and_unsupported_types_are_not_persisted(client,identity,brains_on,payload,mime):
    bid=(await create(client,identity))['id']
    assert (await upload(client,identity,bid,name='source.txt',mime=mime,content=payload)).status_code==415
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainFile))==0


async def test_upload_limit_and_quota_include_trash(client,identity,brains_on,monkeypatch):
    bid=(await create(client,identity))['id']
    assert (await upload(client,identity,bid,content=b'x'*(files.MAX_FILE_BYTES+1))).status_code==413
    monkeypatch.setattr(files,'BRAIN_QUOTA_BYTES',4)
    row=(await upload(client,identity,bid,content=b'1234')).json()
    assert (await upload(client,identity,bid,content=b'x')).status_code==409
    await client.delete(f"/v1/brains/{bid}/files/{row['id']}?revision=1",headers=identity['owner'])
    assert (await upload(client,identity,bid,content=b'x')).status_code==409
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BrainFile))==1


async def test_original_source_immutable_at_database(client,identity,brains_on):
    bid=(await create(client,identity))['id'];row=(await upload(client,identity,bid)).json()
    async with Session() as db:
        with pytest.raises(DBAPIError):
            await db.execute(text('UPDATE brain_files SET content=:content,size=:size WHERE id=:id'),
                             {'content':b'changed','size':7,'id':row['id']})
        await db.rollback()
    assert (await client.get(f"/v1/brains/{bid}/files/{row['id']}/download",headers=identity['owner'])).content==b'# private source'


async def test_archive_blocks_upload_but_keeps_read(client,identity,brains_on):
    bid=(await create(client,identity))['id'];row=(await upload(client,identity,bid)).json()
    assert (await client.patch(f'/v1/brains/{bid}',headers=identity['owner'],json={'revision':2,'archived':True})).status_code==200
    assert (await upload(client,identity,bid)).status_code==409
    assert (await client.get(f"/v1/brains/{bid}/files/{row['id']}/download",headers=identity['owner'])).status_code==200
