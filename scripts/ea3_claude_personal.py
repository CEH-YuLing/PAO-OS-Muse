"""Operator-only native CLI profile preparation/login handoff, not a PAO runner.

Uses the original auth CLI directly in the user's console. Does not collect,
copy or inspect credential files; no model, tool, arbitrary command or logout.
The reserved profile is NOT enrolled into PAO inference until native review.
"""
import argparse,asyncio,hashlib,json,os,re,subprocess,sys,tempfile,traceback
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'.runtime/ea3-claude-native-20261020'
RECORD=FOLDER/'profile.json'
WID='ef221310-5afc-4c21-9f9e-4aa9bf4b3e79'
UID='165b1fa6-f443-4f66-bddb-51eb5b6e6fa5'
IMAGE='sha256:a9a5c8122ea1266e02ef9d499b1d253fcb04593bc22d1874eae6198e753371b8'
ISOLATION=ROOT/'.runtime/ea3-claude-isolation-03dab1bae7524c3aa7825c90478de0fb/receipt.json'
FRESH_PROFILE_BOOTSTRAP="import os,pathlib; p=pathlib.Path('/profile'); assert not any(p.iterdir()); os.chmod(p,0o700); c=p/'.claude'; c.mkdir(mode=0o700); os.chown(c,65534,65534); assert c.stat().st_uid==65534 and (c.stat().st_mode&0o777)==0o700; os.chown(p,65534,65534); assert p.stat().st_uid==65534 and (p.stat().st_mode&0o777)==0o700"
sys.path[:0]=[str(ROOT/'packages/client-adapters'),str(ROOT/'packages/cli-runtime'),str(ROOT/'apps/api')]
from pao_client_adapters.claude_profile import Profile,STAGE,auth_summary
from pao_cli_runtime.docker_transport import DockerTransport
from pao_cli_runtime.source_pin import library_digest

def adapters_digest():
    sha=hashlib.sha256()
    for p in sorted((ROOT/'packages/client-adapters/pao_client_adapters').glob('*.py')):
        assert not p.is_symlink();sha.update(p.name.encode()+b'\0'+p.read_bytes()+b'\0')
    return sha.hexdigest()

async def require_actor():
    from sqlalchemy import select,text
    from pao.db import Session,engine
    from pao.models import User,Member,Workspace
    try:
        async with Session() as db:
            await db.execute(text('SET TRANSACTION READ ONLY'))
            row=await db.execute(select(User.active,Member.role,User.auth_version,Workspace.lifecycle_version)
                .join(Member,Member.user_id==User.id).join(Workspace,Workspace.id==Member.workspace_id)
                .where(User.id==UID,Workspace.id==WID))
            value=row.one()
            assert value.active is True and value.role in ('owner','admin')
            return {'auth_version':value.auth_version,'membership_epoch':value.lifecycle_version,'actor_role':value.role}
    finally:await engine.dispose()

def docker(args,env,*,allow_one=False,timeout=25):
    run=subprocess.run([*DockerTransport.docker(),*args],env=env,stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,
                       creationflags=0x08000000 if os.name=='nt' else 0)
    if len(run.stdout)+len(run.stderr)>262144 or run.returncode not in ((0,1) if allow_one else (0,)):
        raise RuntimeError('claude_candidate_docker_operation_failed')
    return run

def inspect(kind,target,env):
    rows=json.loads(docker([kind,'inspect',target] if kind!='container' else ['inspect',target],env).stdout)
    assert isinstance(rows,list) and len(rows)==1
    return rows[0]

def write_new(name,value):
    path=FOLDER/name
    assert path.parent==FOLDER and not path.exists()
    with path.open('x',encoding='utf-8') as out:json.dump(value,out,indent=2,ensure_ascii=False)

def check(profile,env):
    profile.check_image(inspect('image',profile.image_id,env))
    profile.check_volume(inspect('volume',profile.volume,env))
    busy=docker(['ps','--filter','label=pao.claude.profile_id='+profile.profile_id,'--format','{{.ID}}'],env)
    assert busy.stdout.strip()==b'', 'claude_candidate_profile_busy'

def operation(profile,action,env,*,interactive=False):
    check(profile,env)
    op=str(uuid4());cid=None;clean=False
    try:
        cid=docker(profile.command(op,action),env).stdout.decode().strip()
        assert re.fullmatch(r'[0-9a-f]{64}',cid)
        if interactive:
            print('Đăng nhập trực tiếp bằng CLI Claude chính thức trong cửa sổ này.',flush=True)
            print('Nếu CLI yêu cầu mở đường dẫn/dán mã, thao tác tại đây; không gửi mã hoặc mật khẩu trong chat.',flush=True)
            print('Chỉ đăng nhập hồ sơ riêng. Chưa bật model trong PAO và chưa gửi yêu cầu suy luận.',flush=True)
            code=subprocess.call([*DockerTransport.docker(),'start','--attach','--interactive',cid],env=env)
            return {'native_login_exit_code':code,'inference_called':False}
        run=docker(['start','--attach',cid],env,allow_one=True,timeout=30)
        return auth_summary(run.stdout,run.returncode)
    finally:
        if cid:
            exact=inspect('container',cid,env)
            assert exact['Id']==cid and exact['Config']['Labels']['pao.claude.operation_id']==op
            assert all(exact['Config']['Labels'].get(k)==v for k,v in profile.labels.items())
            docker(['rm','--force',cid],env)
            clean=True
        if not clean:raise RuntimeError('claude_candidate_cleanup_unknown')

def initialize(image_receipt,env,authority):
    assert not RECORD.exists(), 'Profile already reserved; use status/login instead of creating another'
    assert not (FOLDER/'pending-reservation.json').exists(), 'Incomplete reservation exists; inspect and recover it instead of duplicating a profile'
    assert image_receipt.is_absolute() and image_receipt.name=='image.json' and image_receipt.parent.parent==ROOT/'.runtime'
    assert image_receipt.parent.name.startswith('ea3-claude-image-') and not image_receipt.is_symlink()
    image=json.loads(image_receipt.read_text());gate=json.loads(ISOLATION.read_text())
    assert image['pass'] and image['image']==IMAGE and gate['pass'] and gate['image']==IMAGE
    device=json.loads((ROOT/'.runtime/cli-device.json').read_text())
    assert library_digest()==device['host_runtime_sha256']
    profile=Profile(WID,UID,str(uuid4()),device['device_id'],str(uuid4()),IMAGE,image['binary_sha256'],image['version'])
    profile.check_image(inspect('image',IMAGE,env))
    write_new('pending-reservation.json',{'stage':STAGE,'profile':asdict(profile),'authority_at_reservation':authority,
                                        'login_started':False,'native_connection_enrolled':False})
    args=['volume','create','--driver','local']
    for key,value in profile.labels.items():args+=['--label',key+'='+value]
    args+=[profile.volume]
    volume=docker(args,env).stdout.decode().strip();assert volume==profile.volume
    profile.check_volume(inspect('volume',volume,env))
    op=str(uuid4());cid=None
    try:
        # Only this newly generated, empty, label-verified Docker volume.
        bootstrap=FRESH_PROFILE_BOOTSTRAP
        cid=docker(['create','--pull=never','--label','pao.claude.bootstrap='+op,'--network=none','--read-only',
                    '--cap-drop=ALL','--cap-add=CHOWN','--security-opt=no-new-privileges','--pids-limit=16',
                    '--user=0:0','--mount','type=volume,source='+volume+',target=/profile','--entrypoint','python',
                    IMAGE,'-B','-c',bootstrap],env).stdout.decode().strip()
        assert re.fullmatch(r'[0-9a-f]{64}',cid)
        docker(['start','--attach',cid],env)
    finally:
        if cid:
            exact=inspect('container',cid,env)
            assert exact['Id']==cid and exact['Config']['Labels']['pao.claude.bootstrap']==op
            docker(['rm','--force',cid],env)
    status=operation(profile,'status',env)
    assert status['state']=='not_authenticated'
    record={'stage':STAGE,'profile':asdict(profile),'authority_at_reservation':authority,
            'adapter_source_sha256':adapters_digest(),'created_at':datetime.now(timezone.utc).isoformat(),
            'native_connection_enrolled':False,'provider_inference_verified':False}
    write_new('profile.json',record);write_new('initial-auth-status.json',status)
    print(json.dumps({'stage':STAGE,'reserved':True,'auth_state':status['state'],
                      'native_connection_enrolled':False,'provider_calls':0,'volume_retained':True}))

def main():
    assert ROOT==Path('F:/PAO-ACOS') and os.name=='nt'
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['initialize','status','login'])
    parser.add_argument('--image-receipt',type=Path);args=parser.parse_args()
    authority=asyncio.run(require_actor())
    with tempfile.TemporaryDirectory(prefix='ea3-docker-client-',dir=FOLDER) as folder:
        env={'SystemRoot':os.environ['SystemRoot'],'HOME':folder,'USERPROFILE':folder,'APPDATA':folder,
             'LOCALAPPDATA':folder,'TMP':folder,'TEMP':folder,'DOCKER_CONFIG':folder}
        if args.action=='initialize':
            assert args.image_receipt;initialize(args.image_receipt,env,authority);return
        assert RECORD.is_file() and not RECORD.is_symlink()
        record=json.loads(RECORD.read_text(encoding='utf-8'))
        assert record['stage']==STAGE and record['adapter_source_sha256']==adapters_digest()
        assert record['authority_at_reservation']==authority
        profile=Profile(**record['profile'])
        assert profile.workspace_id==WID and profile.actor_id==UID
        lock=FOLDER/'profile-operation.lock'
        with lock.open('x',encoding='ascii') as out:out.write(str(uuid4()))
        clean=False
        try:
            result=operation(profile,args.action,env,interactive=args.action=='login')
            if args.action=='login':result.update(auth_status=operation(profile,'status',env))
            clean=True
            name='status-'+uuid4().hex+'.json';write_new(name,result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
        finally:
            if clean:lock.unlink()
            # Unknown cleanup intentionally preserves the fence; never retry.

if __name__=='__main__':
    try:main()
    except Exception as error:
        # Native auth output is deliberately not captured. Setup failures retain
        # only source frame locations/type, never raw DB/provider exception text.
        frames=[{'file':str(Path(f.filename).relative_to(ROOT)),'line':f.lineno,'function':f.name}
                for f in traceback.extract_tb(error.__traceback__) if Path(f.filename).is_relative_to(ROOT)]
        write_new('setup-error-'+uuid4().hex+'.json',{'error_type':type(error).__name__,'source_frames':frames,
                                                   'native_connection_enrolled':False})
        print('Claude setup paused; see the credential-free setup error receipt.',file=sys.stderr)
        raise SystemExit(1)
