"""Download the explicitly selected local STT model and update only voice keys."""
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download
from pao.config import ROOT

parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');parser.add_argument('--enable',action='store_true');args=parser.parse_args()
target=ROOT/'.runtime/models/faster-whisper-small'
if args.download:
    target.mkdir(parents=True,exist_ok=True)
    snapshot_download(repo_id='Systran/faster-whisper-small',local_dir=target,allow_patterns=['*.json','*.txt','*.model','model.bin'])
required=['config.json','model.bin','tokenizer.json','vocabulary.txt']
missing=[name for name in required if not (target/name).is_file()]
if missing:raise SystemExit('Voice model chưa đủ: '+', '.join(missing)+'. Chạy với --download.')
env=ROOT/'.env';lines=env.read_text(encoding='utf-8').splitlines();updates={'VOICE_STT_MODEL_PATH':'.runtime/models/faster-whisper-small','VOICE_STT_DEVICE':'cpu','VOICE_STT_COMPUTE_TYPE':'int8','VOICE_TTS_PROVIDER':'windows_sapi'}
if args.enable:updates['VOICE_ENABLED']='true'
seen=set();out=[]
for line in lines:
    key=line.split('=',1)[0] if '=' in line else ''
    if key in updates:out.append(f'{key}={updates[key]}');seen.add(key)
    else:out.append(line)
for key,value in updates.items():
    if key not in seen:out.append(f'{key}={value}')
env.write_text('\n'.join(out)+'\n',encoding='utf-8');print(f'Voice model ready at {target}; enabled={args.enable}')
