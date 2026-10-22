"""One explicit native agy catalog read. No prompt, token reader or login proxy.

The CLI may use/refresh its own signed-in machine keyring. Never call this
automatically from GET health/status or treat it as provider approval.
"""
import hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
BINARY=Path('C:/Users/o0o_v/AppData/Local/agy/bin/agy.exe')
SHA='e137ee4f362b5b2f2c37141d4d1d1c12298f6b42873ca6867c618a5b945421df'

def main():
    assert ROOT==Path('F:/PAO-ACOS')
    assert not any(p.is_symlink() or p.is_junction() for p in (BINARY,*BINARY.parents))
    assert hashlib.sha256(BINARY.read_bytes()).hexdigest()==SHA
    folder=ROOT/'.runtime'/('antigravity-native-catalog-'+uuid4().hex);folder.mkdir()
    allowed=('SystemRoot','WINDIR','USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA','LOCALAPPDATA','TEMP','TMP','PATH','USERNAME','USERDOMAIN')
    env={k:os.environ[k] for k in allowed if k in os.environ}
    env['NO_COLOR']='1'
    result={'binary_sha256':SHA,'native_keyring_use_requested':True,'token_read_or_copied_by_PAO':False,
            'prompt_sent':False,'inference_called':False,'provider_support_confirmed':False,
            'serving_adapter_registered':False,'models':[]}
    with tempfile.TemporaryDirectory(prefix='cwd-',dir=folder) as cwd:
        try:
            # Installed 1.2.12 rejects --output-format for the models subcommand.
            # Probe its native text catalog instead; no inference retry.
            run=subprocess.run([str(BINARY),'models'],cwd=cwd,env=env,
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW)
            result.update(exit_code=run.returncode,stdout_bytes=len(run.stdout),stderr_bytes=len(run.stderr))
            if run.returncode:
                message=run.stderr.decode('utf-8',errors='replace').lower()
                # Diagnostic categories only: never expose raw auth diagnostics.
                patterns={'unsupported_flag':r'unknown (?:flag|argument)|flag provided but not defined',
                    'keyring':r'keyring|credential manager|credential.*store',
                    'windows_identity':r'mapping|security id|sid|lookup|user:',
                    'login_required':r'login|authenticate|sign in|not logged|oauth',
                    'api_configuration':r'gemini_api_key|modelprovider',
                    'network_tls':r'certificate|tls|network|dial tcp|timeout',
                    'permission_denied':r'access.*denied|permission',
                    'missing_configuration':r'not found|missing|no such|cannot find|does not exist'}
                result['error_categories']=[name for name,pattern in patterns.items() if re.search(pattern,message)]
                vocabulary=set('error fatal failed failure unable cannot could not to get create initialize start open read write load save fetch request connect response from the a an is are was no for on in at with without of and or please run use default active account selected select profile project directory folder file configuration config missing invalid unsupported unknown unrecognized provided defined flag flags command argument arguments format output json models auth login authentication signed keyring credential credentials windows user current system permission access denied database sqlite locked readonly read-only server process binary executable logging log state home environment initialization required supported agy path notfound startup message exit status expected got api model provider'.split())
                result['error_words']=[word for word in re.findall(r'[a-z]+(?:-[a-z]+)?',message) if word in vocabulary][:60]
            if run.returncode==0 and len(run.stdout)+len(run.stderr)<=262144:
                try:body=json.loads(run.stdout)
                except ValueError:
                    body=[]
                    for line in run.stdout.decode('utf-8',errors='strict').splitlines():
                        part=line.strip().split()[0] if line.strip() else ''
                        if re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9][a-z0-9._-]*)+',part):body.append(part)
                    result['catalog_format']='native_text'
                result['json_shape']=type(body).__name__
                if isinstance(body,dict):
                    # Field names only, never values from arbitrary diagnostic fields.
                    result['known_list_fields']=[key for key in ('models','data','items','result') if isinstance(body.get(key),list)]
                    lists=[body[key] for key in result['known_list_fields']]
                    body=lists[0] if len(lists)==1 else []
                if isinstance(body,list) and len(body)<=100:
                    for row in body:
                        values=[row] if isinstance(row,str) else [row.get(key) for key in ('slug','id','model','name')] if isinstance(row,dict) else []
                        slugs=[v for v in values if isinstance(v,str) and re.fullmatch(r'[a-z][a-z0-9._-]{1,119}',v)]
                        if slugs and slugs[0] not in result['models']:result['models'].append(slugs[0])
        except subprocess.TimeoutExpired:result['timed_out']=True
        except (ValueError,UnicodeError):result['output_rejected']=True
    result['catalog_observed']=bool(result['models'])
    result['binary_unchanged']=hashlib.sha256(BINARY.read_bytes()).hexdigest()==SHA
    with (folder/'receipt.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
    print(json.dumps({'folder':str(folder),**result}))

if __name__=='__main__':main()
