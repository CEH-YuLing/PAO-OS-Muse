"""Private deployment wrapper; explicit file secrets, no implicit migration/provider activation."""
import asyncio,json,os,re,sys
from pathlib import Path
from urllib.parse import urlsplit
from sqlalchemy.engine import make_url

KEYS={'DATABASE_URL','REDIS_URL','JWT_SECRET','INTEGRATION_ENCRYPTION_KEY'}
OFF=('META_ENABLED','META_WRITE_ENABLED','GOOGLE_ADS_ENABLED','TELEGRAM_ENABLED','TELEGRAM_SCOPED_RUNTIME_ENABLED',
 'CHANNELS_ENABLED','CHANNEL_AUTOREPLY_ENABLED','CHANNEL_RETENTION_ENABLED','TEMPORAL_ENABLED','WORKFLOW_DISPATCH_ENABLED',
 'WORKFLOW_WORKER_ENABLED','GOAL_RUNNER_ENABLED','STUDIO_SCHEDULE_DISPATCH_ENABLED','BUSINESS_EVENTS_ENABLED',
 'BUSINESS_EVENT_DELIVERY_ENABLED','ADS_AUTOPILOT_GLOBAL_ENABLED','META_AUTOPILOT_ENABLED','META_INSTALLATION_CONFIG_ENABLED',
 'VOICE_ENABLED','TOOLS_ENABLED','AGENT_RUNTIME_ENABLED')
def validate(value,mode):
    from cryptography.fernet import Fernet
    if not isinstance(value,dict) or set(value)!=KEYS or not all(isinstance(v,str) and v for v in value.values()):raise ValueError('runtime_secret_shape')
    db=make_url(value['DATABASE_URL']);redis=urlsplit(value['REDIS_URL'])
    role='pao_migrator' if mode in ('migrate','grant') else 'pao_app'
    if (db.drivername!='postgresql+asyncpg' or db.host!='postgres' or db.port!=5432 or db.username!=role or not db.password
        or not re.fullmatch(r'pao_service_[a-z0-9_]{1,40}',db.database or '')):raise ValueError('dedicated_database_role_required')
    if redis.scheme!='redis' or redis.hostname!='redis' or redis.port!=6379 or redis.path!='/0' or not redis.password:raise ValueError('dedicated_redis_required')
    if len(value['JWT_SECRET'])<48 or 'REPLACE' in value['JWT_SECRET']:raise ValueError('private_jwt_required')
    Fernet(value['INTEGRATION_ENCRYPTION_KEY'].encode())
    return db
async def check_database(value,mode):
    import asyncpg
    db=make_url(value['DATABASE_URL']);connection=await asyncpg.connect(host=db.host,port=db.port,user=db.username,password=db.password,database=db.database,timeout=10)
    try:
        role=await connection.fetchrow('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        if not role or any(role.values()):raise ValueError('privileged_runtime_role')
        if mode in ('api','worker'):
            if await connection.fetchval('SELECT version_num FROM alembic_version')!='0071':raise ValueError('reviewed_schema_required')
            owns=await connection.fetchval("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)")
            if owns or await connection.fetchval("SELECT has_schema_privilege(current_user,'public','CREATE')"):raise ValueError('runtime_ddl_denied')
        if mode=='grant':await connection.execute(Path('/app/infra/production/grants.sql').read_text())
    finally:await connection.close()
def main():
    mode=sys.argv[1] if len(sys.argv)==2 else ''
    if mode not in ('api','worker','migrate','grant'):raise ValueError('explicit_mode_required')
    if Path('/app/.env').exists():raise ValueError('image_env_file_forbidden')
    value=json.loads(Path('/run/secrets/pao_config').read_text())
    validate(value,mode)
    for key in OFF:os.environ[key]='false'
    os.environ.update(value);os.environ.update(PAO_ROOT='/app',PYTHONPATH='/app/apps/api',PYTHONDONTWRITEBYTECODE='1')
    asyncio.run(check_database(value,mode))
    if mode=='grant':return
    command={'api':[sys.executable,'-m','uvicorn','pao.main:app','--host','0.0.0.0','--port','8000','--no-proxy-headers','--no-access-log'],
      'worker':[sys.executable,'-m','arq','pao.runtime.WorkerSettings'],
      'migrate':[sys.executable,'-m','alembic','upgrade','0071']}[mode]
    os.execvpe(command[0],command,os.environ)
if __name__=='__main__':
    try:main()
    except Exception:print('PAO startup rejected; verify private config, dedicated roles, grants and schema. No secret values are logged.',file=sys.stderr);sys.exit(1)
