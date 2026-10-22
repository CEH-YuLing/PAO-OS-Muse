"""Restore a private primary dump only into a UUID internal-network clone.

No provider, host keys, tools, migration, primary restore, published port or
outbound network for the archive reader. Preserve the private dump and receipts.
"""
import asyncio,json,os,re,secrets,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from check_m2_restore import CONTAINER,inspect
from check_p11_migration import snapshot

def main():
    source_url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and source_url.host=='127.0.0.1' and source_url.port==15432 and source_url.database=='pao_acos_local'
    image=sys.argv[1];assert re.fullmatch(r'pao-s6-linux:[0-9a-f]{32}',image)
    image_rid=image.split(':')[1]
    def docker(*args,**kwargs):
        return subprocess.run(['docker',*args],check=True,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,**kwargs).stdout.strip()
    assert docker('image','inspect',image,'--format','{{index .Config.Labels "pao.s6.runid"}}')==image_rid
    rid=uuid4().hex;folder=ROOT/'.runtime'/('phase3-cold-'+rid);folder.mkdir()
    before=asyncio.run(snapshot(source_url));baseline=asyncio.run(inspect(source_url))
    (folder/'primary-before.json').write_text(json.dumps(before),encoding='utf-8')
    dump=folder/'database.dump'
    with dump.open('xb') as stream:
        subprocess.run(['docker','exec',CONTAINER,'pg_dump','-U','pao','-d','pao_acos_local','-Fc'],check=True,stdout=stream,stderr=subprocess.PIPE)
    network='pao-cold-'+rid;database='pao_cold_'+rid[:16];password=secrets.token_hex(24);admin_password=secrets.token_hex(24)
    owned=[];network_created=False
    result={'pass':False,'source_image':image,'run_id':rid,'production_accepted':False,'provider_calls':False,'primary_restore_attempted':False}
    try:
        docker('network','create','--internal','--label','pao.phase3.cold='+rid,network);network_created=True
        pg=docker('run','-d','--label','pao.phase3.cold='+rid,'--network',network,'--network-alias','postgres','--memory','768m',
            '-e','POSTGRES_USER=pao_cold_admin','-e','POSTGRES_PASSWORD='+admin_password,'-e','POSTGRES_DB='+database,'pgvector/pgvector:pg17')
        owned.append(pg)
        for _ in range(50):
            if subprocess.run(['docker','exec',pg,'pg_isready','-U','pao_cold_admin','-d',database],capture_output=True).returncode==0:break
            time.sleep(.3)
        else:raise RuntimeError('cold_clone_not_ready')
        docker('cp',str(dump),pg+':/tmp/restore.dump')
        docker('exec',pg,'pg_restore','-U','pao_cold_admin','-d',database,'--no-owner','--no-privileges','--exit-on-error','/tmp/restore.dump')
        sql=f"CREATE ROLE pao_archive_reader LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; GRANT CONNECT ON DATABASE {database} TO pao_archive_reader; GRANT USAGE ON SCHEMA public TO pao_archive_reader; GRANT SELECT ON ALL TABLES IN SCHEMA public TO pao_archive_reader; ALTER ROLE pao_archive_reader SET default_transaction_read_only=on;"
        docker('exec','-i',pg,'psql','-U','pao_cold_admin','-d',database,'-v','ON_ERROR_STOP=1',input=sql)
        code=(Path(__file__).parent/'phase3_cold_reader.py').read_text(encoding='utf-8')
        reader=docker('create','--label','pao.phase3.cold='+rid,'--network',network,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m',
            '-e',f'DATABASE_URL=postgresql+asyncpg://pao_archive_reader:{password}@postgres:5432/{database}',
            '-e','JWT_SECRET=synthetic-cold-only-not-a-real-authentication-key-00000',
            '--entrypoint','python',image,'-c',code)
        owned.append(reader)
        output=docker('start','-a',reader);receipt=json.loads(output)
        assert receipt['pass'] and receipt['tables']==len(baseline['counts']) and receipt['archive_hashes']==baseline['artifact_hashes']
        result.update(archive_reader=receipt,internal_network=True,readonly_clone_role=True,source_archive_hashes_match=True)
        result['pass']=True
    finally:
        for cid in reversed(owned):
            assert docker('inspect',cid,'--format','{{index .Config.Labels "pao.phase3.cold"}}')==rid
            docker('rm','-f','-v',cid)
        if network_created:
            assert docker('network','inspect',network,'--format','{{index .Labels "pao.phase3.cold"}}')==rid
            docker('network','rm',network)
        after=asyncio.run(snapshot(source_url));(folder/'primary-after.json').write_text(json.dumps(after),encoding='utf-8')
        result.update(primary_unchanged=before==after,owned_resources_removed=True)
        result['pass']=result['pass'] and result['primary_unchanged']
        (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({**result,'evidence':str(folder)}),flush=True)
    if not result['pass']:raise SystemExit(1)

if __name__=='__main__':main()
