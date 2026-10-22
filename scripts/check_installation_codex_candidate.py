"""Real Codex binary, synthetic loopback responder, network-none, no login."""
import argparse,json,subprocess
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
IMAGE=ROOT/'.runtime/p84-codex-image-542ef8046f154b6ab381eb9c54b2f4a2/image.json'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--image-receipt',type=Path,default=IMAGE)
    parser.add_argument('--multimodel',action='store_true')
    args=parser.parse_args()
    receipt=args.image_receipt.resolve()
    assert receipt.parent.parent==ROOT/'.runtime' and receipt.parent.name.startswith('p84-codex-image-') and receipt.name=='image.json' and not receipt.is_symlink()
    image=json.loads(receipt.read_text())
    assert ROOT==Path('F:/PAO-ACOS') and image['runtime_candidate'] is True
    folder=ROOT/'.runtime'/('installation-codex-protocol-'+uuid4().hex);folder.mkdir()
    state={'pass':False,'provider_calls':0,'auth_copied':False,'host_mounts':[],'cases':{},'image_receipt':str(receipt),'image':image['image']}
    try:
        cases=('normal','tool-injection','effort-high','effort-low')+(('model-a-high','model-b-low') if args.multimodel else ())
        for case in cases:
            command=['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL',
                '--security-opt=no-new-privileges','--pids-limit=64','--memory=1g','--cpus=2',
                '--tmpfs','/tmp:rw,noexec,nosuid,size=64m',image['image']]
            if case!='normal':command.append(case)
            result=subprocess.run(command,capture_output=True,timeout=60)
            (folder/(case+'.stdout.log')).write_bytes(result.stdout)
            (folder/(case+'.stderr.log')).write_bytes(result.stderr)
            value=json.loads(result.stdout.splitlines()[-1])
            assert result.returncode==0 and value['pass'] is True,case
            assert value['provider_inference_verified'] is False and value['uid']==65534
            if case.startswith('effort-'):
                assert all(row['reasoning']['effort']==case[7:] for row in value['requests'])
            if case.startswith('model-'):
                expected=('pao-synthetic-specialist','low') if case=='model-b-low' else ('gpt-5.4','high')
                assert all((row['model'],row['reasoning']['effort'])==expected for row in value['requests'])
            state['cases'][case]=value
        state['pass']=True
    finally:
        (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),'pass':state['pass'],'cases':list(state['cases']),'provider_calls':0}))
    raise SystemExit(0 if state['pass'] else 1)


if __name__=='__main__':main()
