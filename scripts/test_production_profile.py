"""Offline rejection tests; never reads a real key or opens a database."""
import importlib.util,json,sys,tempfile
from pathlib import Path
from cryptography.fernet import Fernet
import pytest,yaml
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_entry',ROOT/'infra/production/entrypoint.py');entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
def config(role='pao_app'):
 return {'DATABASE_URL':f'postgresql+asyncpg://{role}:synthetic@postgres:5432/pao_service_test',
 'REDIS_URL':'redis://:synthetic@redis:6379/0','JWT_SECRET':'synthetic-test-only-'+'x'*48,'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode()}
def test_valid_role_separation():
 assert entry.validate(config(),'api').username=='pao_app'
 assert entry.validate(config('pao_migrator'),'migrate').username=='pao_migrator'
 for mode in ('api','worker'):
  with pytest.raises(ValueError):entry.validate(config('pao_migrator'),mode)
@pytest.mark.parametrize('key,value',[
 ('DATABASE_URL','postgresql+asyncpg://pao:secret@127.0.0.1:15432/pao_acos_local'),
 ('DATABASE_URL','postgresql+asyncpg://pao_app:secret@postgres:5432/pao_test'),
 ('DATABASE_URL','postgresql+asyncpg://pao_app@postgres:5432/pao_service_test'),
 ('REDIS_URL','redis://:secret@redis:6379/15'),('REDIS_URL','redis://127.0.0.1:6379/0'),
 ('JWT_SECRET','short'),('INTEGRATION_ENCRYPTION_KEY','invalid')])
def test_bad_config_rejected(key,value):
 data=config();data[key]=value
 with pytest.raises(Exception):entry.validate(data,'api')
def test_unknown_secret_fields_rejected():
 data=config();data['META_ENABLED']='true'
 with pytest.raises(ValueError):entry.validate(data,'api')
def test_example_is_not_a_deployable_secret():
 with pytest.raises(Exception):entry.validate(json.loads((ROOT/'infra/production/runtime.example.json').read_text()),'api')
def test_compose_has_no_public_app_database_ports_or_shared_migration_secret():
 data=yaml.safe_load((ROOT/'infra/production/compose.private.yaml').read_text());services=data['services']
 for name in ('api','worker','postgres','redis','web'):assert not services[name].get('ports')
 assert services['proxy']['ports']==['127.0.0.1:18443:8443']
 for name in ('api','worker','web','proxy'):assert services[name]['read_only'] and services[name]['cap_drop']==['ALL']
 assert 'setcap -r /usr/bin/caddy' in (ROOT/'infra/production/proxy.Dockerfile').read_text()
 for name in ('api','worker'):assert services[name]['secrets']==[{'source':'runtime_config','target':'pao_config'}]
 assert services['migrate']['profiles']==['operations']
 assert services['migrate']['secrets']==[{'source':'migration_config','target':'pao_config'}]
def test_archive_carries_only_reviewed_infra_not_arbitrary_sql_or_secrets():
 sys.path.insert(0,str(ROOT/'scripts'));from backup_acos_checkpoint import source_archive
 from zipfile import ZipFile
 with tempfile.TemporaryDirectory() as folder:
  root=Path(folder);p=root/'infra/production';p.mkdir(parents=True)
  for name in ('roles.sql','grants.sql','Caddyfile','Caddyfile.public.example'):(p/name).write_text('reviewed source')
  source_archive(root,root/'source.zip')
  with ZipFile(root/'source.zip') as archive:assert sorted(archive.namelist())==['infra/production/Caddyfile','infra/production/Caddyfile.public.example','infra/production/grants.sql','infra/production/roles.sql']
  (p/'actual-secrets.sql').write_text('must not be copied');(p/'runtime.json').write_text('must not be copied')
  with pytest.raises(ValueError):source_archive(root,root/'blocked.zip')
  assert not (root/'blocked.zip').exists()
def test_reviewed_infra_cannot_follow_a_linked_parent(tmp_path,monkeypatch):
 sys.path.insert(0,str(ROOT/'scripts'));from backup_acos_checkpoint import source_supplements
 directory=tmp_path/'infra/production';directory.mkdir(parents=True);(directory/'roles.sql').write_text('fixture')
 original=Path.is_symlink
 monkeypatch.setattr(Path,'is_symlink',lambda p:p==directory or original(p))
 with pytest.raises(ValueError):source_supplements(tmp_path)
