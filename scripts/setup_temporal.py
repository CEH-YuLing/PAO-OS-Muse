"""Enable or disable the local Temporal gate without touching other secrets."""
import argparse
from pathlib import Path
from pao.config import ROOT
parser=argparse.ArgumentParser();parser.add_argument('--enable',action='store_true');parser.add_argument('--disable',action='store_true');args=parser.parse_args()
if args.enable==args.disable:raise SystemExit('Choose exactly one of --enable or --disable')
env=ROOT/'.env';lines=env.read_text(encoding='utf-8').splitlines();updates={'TEMPORAL_ENABLED':'true' if args.enable else 'false','TEMPORAL_ADDRESS':'127.0.0.1:7233','TEMPORAL_NAMESPACE':'default','TEMPORAL_TASK_QUEUE':'pao-automation'};seen=set();out=[]
for line in lines:
    key=line.split('=',1)[0] if '=' in line else ''
    if key in updates:out.append(f'{key}={updates[key]}');seen.add(key)
    else:out.append(line)
for key,value in updates.items():
    if key not in seen:out.append(f'{key}={value}')
env.write_text('\n'.join(out)+'\n',encoding='utf-8');print(f"Temporal enabled={args.enable}; restart API and worker processes.")
