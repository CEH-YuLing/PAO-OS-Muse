"""Isolated UI API: temp config, pao_test, no Meta transport allowed."""
import os,tempfile
from pathlib import Path
from cryptography.fernet import Fernet
import uvicorn
from pao.config import settings
from pao.main import app
from pao.integrations.meta import app_config
from pao.integrations.meta.client import MetaClient

config=settings()
assert config.database_url.endswith('/pao_test')
async def forbidden(*args,**kwargs):
    raise AssertionError('External Meta transport forbidden in settings UI acceptance')
MetaClient._request=forbidden
for name in ('META_ENABLED','META_APP_ID','META_APP_SECRET','META_GRAPH_API_VERSION','META_REDIRECT_URI',
             'INTEGRATION_ENCRYPTION_KEY',*app_config.SAFE_FLAGS):os.environ.pop(name,None)
for name in ('meta_enabled','meta_write_enabled','meta_autopilot_enabled','ads_autopilot_global_enabled'):
    setattr(config,name,False)
with tempfile.TemporaryDirectory(prefix='pao-meta-app-ui-') as directory:
    app_config.ENV_PATH=Path(directory)/'.env'
    app_config.ENV_PATH.write_text('META_APP_ID=123\nMETA_GRAPH_API_VERSION=v26.0\n'
                                  'META_REDIRECT_URI=http://127.0.0.1:3200/v1/integrations/meta/callback\n'
                                  'INTEGRATION_ENCRYPTION_KEY='+Fernet.generate_key().decode()+'\n')
    uvicorn.run(app,host='127.0.0.1',port=18100,access_log=False)
