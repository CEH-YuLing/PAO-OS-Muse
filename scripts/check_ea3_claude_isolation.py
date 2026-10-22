"""Owned-container, network-none metadata/preauth tests. Never real login."""
import argparse,json,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]

def docker(*args,timeout=20):
    return subprocess.check_output(['docker',*args],stdin=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=timeout)

def main():
    assert ROOT==Path('F:/PAO-ACOS')
    parser=argparse.ArgumentParser();parser.add_argument('--image-receipt',type=Path,required=True);args=parser.parse_args()
    path=args.image_receipt
    assert path.is_absolute() and path.name=='image.json' and path.parent.parent==ROOT/'.runtime'
    assert path.parent.name.startswith('ea3-claude-image-') and not path.is_symlink()
    receipt=json.loads(path.read_text());assert receipt['pass'] and receipt['version']=='2.1.220'
    image=receipt['image'];assert re.fullmatch(r'sha256:[0-9a-f]{64}',image)
    info=json.loads(docker('image','inspect',image))[0]
    assert info['Id']==image and info['Config']['User']=='65534:65534'
    assert info['Config']['Labels']['pao.claude.binary-sha256']==receipt['binary_sha256']
    run_id=uuid4().hex;folder=ROOT/'.runtime'/('ea3-claude-isolation-'+run_id);folder.mkdir()
    state={'pass':False,'provider_calls':0,'real_login_started':False,'native_PAO_job':False,
           'image':image,'fixture_cases':[],'all_owned_containers_removed':False}
    try:
        for mode in ('normal','timeout'):
            label=run_id+'-'+mode;cid=None;removed=False
            case={'mode':mode,'pass':False}
            try:
                command=['create','--pull=never','--name','pao-ea3-'+label,'--label','pao.ea3.check='+label,
                    '--network=none','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=128m,uid=65534,gid=65534',
                    '--tmpfs','/profile:rw,noexec,nosuid,size=32m,uid=65534,gid=65534',
                    '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32','--memory=768m',
                    '--cpus=1','--user=65534:65534',image]
                if mode=='timeout':command+=['--fixture-hang']
                cid=docker(*command).decode().strip();assert re.fullmatch(r'[0-9a-f]{64}',cid)
                created=json.loads(docker('inspect',cid))[0];host=created['HostConfig']
                assert created['Id']==cid and created['Config']['Labels']['pao.ea3.check']==label
                assert host['NetworkMode']=='none' and host['ReadonlyRootfs'] is True
                assert not host['Binds'] and not created['Mounts']
                assert host['CapDrop']==['ALL'] and host['Privileged'] is False
                assert 'no-new-privileges' in host['SecurityOpt'] and host['PidsLimit']==32
                assert host['Memory']==768*1024*1024 and host['NanoCpus']==1000000000
                assert created['Config']['User']=='65534:65534'
                case['host_mounts']=[];case['network']='none';case['nonroot_readonly_caps_pass']=True
                try:
                    run=subprocess.run(['docker','start','--attach',cid],stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=55 if mode=='normal' else 3)
                    # This fixture has only an empty scratch profile and no
                    # network/host mounts. Retain bounded failure evidence.
                    assert len(run.stdout)+len(run.stderr)<262144
                    (folder/(mode+'.stdout')).write_bytes(run.stdout)
                    (folder/(mode+'.stderr')).write_bytes(run.stderr)
                    case['exit_code']=run.returncode
                    assert mode=='normal' and run.returncode==0
                    value=json.loads(run.stdout.decode())
                    assert value['pass'] and value['binary_sha256']==receipt['binary_sha256']
                    case.update(pass_fixture=value,pass_case=True)
                except subprocess.TimeoutExpired:
                    assert mode=='timeout'
                    case.update(timeout_observed=True,pass_case=True)
            finally:
                if cid:
                    exact=json.loads(docker('inspect',cid))[0]
                    assert exact['Id']==cid and exact['Config']['Labels']['pao.ea3.check']==label
                    docker('rm','--force',cid)
                    remaining=docker('ps','-a','--filter','label=pao.ea3.check='+label,'--format','{{.ID}}')
                    assert remaining.strip()==b'';removed=True
                case.update(owned_container_removed=removed)
                case['pass']=bool(case.get('pass_case') and removed)
                state['fixture_cases'].append(case)
        state['all_owned_containers_removed']=all(c['owned_container_removed'] for c in state['fixture_cases'])
        state['pass']=all(c['pass'] for c in state['fixture_cases']) and len(state['fixture_cases'])==2
        assert state['pass']
    finally:
        state['all_owned_containers_removed']=bool(state['fixture_cases']) and all(c['owned_container_removed'] for c in state['fixture_cases'])
        with (folder/'receipt.json').open('x',encoding='utf-8') as out:json.dump(state,out,indent=2)
        print(json.dumps({'folder':str(folder),**state}),flush=True)

if __name__=='__main__':main()
