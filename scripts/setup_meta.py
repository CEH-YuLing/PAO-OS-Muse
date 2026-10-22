"""Enter Meta App Secret locally; never put credentials on the command line."""
import argparse
import getpass
import re
from cryptography.fernet import Fernet
from pao.config import ROOT, settings
from pao.integrations.meta.client import configured, MetaError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--app-id',required=True)
    parser.add_argument('--api-version',required=True,help='Supported version from your Meta App dashboard, e.g. vNN.0')
    parser.add_argument('--redirect-uri',default='http://localhost:3100/v1/integrations/meta/callback')
    args=parser.parse_args()
    if not args.app_id.isdecimal() or not re.fullmatch(r'v\d+\.\d+',args.api_version):
        raise SystemExit('Invalid App ID/API version; configuration unchanged')
    secret=getpass.getpass('Meta App Secret (hidden): ').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,256}',secret):raise SystemExit('Invalid secret format; configuration unchanged')
    config=settings()
    # Never rotate a key implicitly: existing ciphertext must remain decryptable.
    key=config.integration_encryption_key or Fernet.generate_key().decode()
    config.meta_enabled=True;config.meta_app_id=args.app_id;config.meta_app_secret=secret
    config.meta_graph_api_version=args.api_version;config.meta_redirect_uri=args.redirect_uri;config.integration_encryption_key=key
    try:configured()
    except MetaError as exc:raise SystemExit(str(exc)) from None
    values={'META_ENABLED':'true','META_APP_ID':args.app_id,'META_APP_SECRET':secret,
        'META_GRAPH_API_VERSION':args.api_version,'META_REDIRECT_URI':args.redirect_uri,'INTEGRATION_ENCRYPTION_KEY':key}
    path=ROOT/'.env'
    lines=path.read_text(encoding='utf-8').splitlines()
    lines=[line for line in lines if line.split('=',1)[0] not in values]
    path.write_text('\n'.join(lines+[f'{k}={v}' for k,v in values.items()])+'\n',encoding='utf-8')
    print('Meta configured locally. Restart API and worker, then open PAO on the redirect URI host and connect Meta. No ad changes made.')


if __name__=='__main__':main()
