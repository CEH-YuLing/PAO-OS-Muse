"""Bounded official Muse exec probe; synthetic input only, no raw trace persisted."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts'),str(ROOT/'packages/cli-runtime')]
from pao.modules.cli_connections.muse_client import binary,discover
from pao.modules.cli_connections.muse_profile import environment,PROFILE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
    native=asyncio.run(discover())
    assert native['account_state']=='accountLogin'
    run=ROOT/'.runtime'/('muse-exec-probe-'+uuid4().hex);run.mkdir()
    work=run/'workspace';work.mkdir()
    # Keep only Muse's own approved login configuration, not previous run data.
    env=environment()
    for key,relative in [('HOME','home'),('USERPROFILE','home'),('APPDATA','appdata'),
                         ('LOCALAPPDATA','localappdata'),('XDG_DATA_HOME','data'),('MUSE_HOME','data/muse'),('TEMP','tmp'),('TMP','tmp')]:
        target=run/relative;target.mkdir(parents=True,exist_ok=True);env[key]=str(target)
    settings=PROFILE/'.config/muse/settings.json'
    cfg=json.loads(settings.read_text()) if settings.exists() else {}
    assert not cfg.get('hooks') and not cfg.get('managed_hooks_path') and not cfg.get('mcpServers')
    assert not (PROFILE/'.config/muse/AGENTS.md').exists()
    env['MUSE_TRANSPORT_TRACE']='1'
    command=[str(binary()),'exec','--provider','meta' if args.live else 'echo',
        '--preset','empty','--json','--no-session-log','--disable-shell','--disable-write',
        '--disable-web-tools','--disable-reminders','--disable-request-user-input','--no-foreign-personal-context',
        '--approval-mode','untrusted','--approval-judge','off','--max-model-steps','1',
        '--model','muse-spark-1.3','--reasoning-effort','minimal',
        'This is a synthetic connection test. Do not use tools, read files, or access business data. Reply exactly PAO_MUSE_NATIVE_OK.']
    p=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
    records=[];terminal=None;usage_keys=[]
    for line in p.stdout.splitlines():
        try:v=json.loads(line)
        except ValueError:continue
        payload=v.get('payload',{});kind=v.get('payload_type')
        if kind=='run.terminal.completed':terminal=payload
        if 'usage' in str(payload).lower():usage_keys.append({'kind':kind,'keys':list(payload)})
        records.append({'kind':kind,'keys':list(payload)})
    # Do not emit stderr/body. Only non-sensitive key names and observed tool count.
    trace=[]
    for line in p.stderr.decode(errors='replace').splitlines():
        start=line.find('{')
        if start<0:continue
        try:v=json.loads(line[start:])
        except ValueError:continue
        if isinstance(v,dict):
            item={'keys':list(v),'tools_present':'tools' in v,'tools_count':len(v['tools']) if isinstance(v.get('tools'),list) else None}
            if 'instructions' in v:item.update(instructions_chars=len(v['instructions']),model=v.get('model'),max_output_tokens=v.get('max_output_tokens'))
            response=v.get('response')
            if isinstance(response,dict) and isinstance(response.get('usage'),dict):
                usage=response['usage'];item['usage']={k:usage[k] for k in ('input_tokens','output_tokens','total_tokens') if type(usage.get(k)) is int}
            trace.append(item)
    text=(terminal or {}).get('text','')
    receipt={'exit':p.returncode,'live':args.live,'provider_calls_requested':int(args.live),
        'isolated_run_data':True,'raw_trace_persisted':False,'terminal':(terminal or {}).get('terminal'),
        'marker_exact':text.strip()=='PAO_MUSE_NATIVE_OK','echo_marker':'PAO_MUSE_NATIVE_OK' in text,
        'records':records,'usage_events':usage_keys,'trace_shapes':trace,'stderr_bytes':len(p.stderr)}
    (run/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps({'folder':str(run),**receipt}))


if __name__=='__main__':main()
