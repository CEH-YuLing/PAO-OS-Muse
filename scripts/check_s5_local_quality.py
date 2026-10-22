"""Own empty database, synthetic data, real local inference, no cloud or downloads."""
import asyncio,json,os,re,secrets,subprocess,sys
import shutil
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from check_p11_migration import CONTAINER
from run_s3_browser import seed


def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    name='pao_s5_quality_'+uuid4().hex;assert re.fullmatch('pao_s5_quality_[0-9a-f]{32}',name)
    previous=ROOT/'.runtime/s5-local-quality.json'
    if previous.exists():shutil.copy2(previous,ROOT/'.runtime'/('s5-local-quality-history-'+uuid4().hex+'.json'))
    created=False
    def docker(*args):subprocess.run(['docker','exec',CONTAINER,*args],check=True,timeout=90)
    try:
        docker('createdb','-U','pao',name);created=True;target=url.set(database=name).render_as_string(hide_password=False)
        env={**os.environ,'DATABASE_URL':target,'REDIS_URL':urlunsplit(urlsplit(settings().redis_url)._replace(path='/15')),
            'JWT_SECRET':'synthetic-quality-'+secrets.token_hex(24),'BUSINESS_PLANNING_ENABLED':'true',
            'ENGINE_CONTRACT_ENABLED':'true','CHAT_FEATURES_ENABLED':'true','STUDIO_ENABLED':'true',
            'META_ENABLED':'false','GOOGLE_ADS_ENABLED':'false','META_WRITE_ENABLED':'false','META_AUTOPILOT_ENABLED':'false',
            'ADS_AUTOPILOT_GLOBAL_ENABLED':'false','TELEGRAM_ENABLED':'false','TELEGRAM_SCOPED_RUNTIME_ENABLED':'false',
            'CHANNELS_ENABLED':'false','TEMPORAL_ENABLED':'false','MEMORY_ENABLED':'false','TOOLS_ENABLED':'false','AGENT_RUNTIME_ENABLED':'false'}
        subprocess.run([sys.executable,'-m','alembic','upgrade','0070'],cwd=ROOT,env=env,check=True,timeout=120)
        a,b=asyncio.run(seed(target));env['PAO_S5_QUALITY_WORKSPACE']=a
        subprocess.run([sys.executable,'scripts/s5_quality_scenario.py'],cwd=ROOT,env=env,check=True,timeout=360)
    finally:
        if created:docker('dropdb','-U','pao',name);print('Removed only owned S5 quality database; result retained; primary untouched.')


if __name__=='__main__':main()
