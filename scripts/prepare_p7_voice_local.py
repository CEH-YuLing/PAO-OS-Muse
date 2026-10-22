"""Public pinned model download/local synthetic smoke; never edits .env or opens mic."""
import argparse,asyncio,hashlib,json,os,time,unicodedata,re
from pathlib import Path
from pao.config import ROOT,settings
from pao.voice import engine

FILES=['config.json','model.bin','tokenizer.json','vocabulary.txt']

def download():
    from huggingface_hub import HfApi,snapshot_download
    target=ROOT/'.runtime/models/faster-whisper-small';target.mkdir(parents=True,exist_ok=True)
    info=HfApi().model_info('Systran/faster-whisper-small',token=False,files_metadata=True)
    selected=[f for f in info.siblings if f.rfilename in FILES]
    assert len(selected)==4 and sum(f.size or 0 for f in selected)<600_000_000
    snapshot_download(repo_id=info.id,revision=info.sha,token=False,local_dir=target,cache_dir=ROOT/'.runtime/hf-cache',allow_patterns=FILES,max_workers=2)
    hashes={}
    for item in selected:
        path=target/item.rfilename;assert path.is_file() and path.stat().st_size==item.size
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        if item.lfs:assert sha==item.lfs.sha256
        hashes[item.rfilename]={'bytes':item.size,'sha256':sha}
    report={'provider':'public Systran faster-whisper model','revision':info.sha,'files':hashes,'env_modified':False,'audio_uploaded':False}
    (ROOT/'.runtime/p7-voice-model.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'model_verified':True,'revision':info.sha,'bytes':sum(f.size or 0 for f in selected),'env_modified':False}))

def words(value):
    return re.findall(r'\w+',unicodedata.normalize('NFC',value).lower())

def distance(expected,actual):
    row=list(range(len(actual)+1))
    for i,word in enumerate(expected,1):
        nextrow=[i]
        for j,other in enumerate(actual,1):nextrow.append(min(row[j]+1,nextrow[-1]+1,row[j-1]+(word!=other)))
        row=nextrow
    return row[-1]

async def smoke():
    cfg=settings();cfg.voice_enabled=True  # This process only, .env unchanged.
    state=engine.status();assert state['stt_ready'] and state['tts_ready']
    cases=['Xin chào PAO. Đây là kiểm tra giọng nói cục bộ.','Tóm tắt công việc hôm nay.','Dừng công việc và chờ tôi xác nhận.']
    results=[]
    for index,text in enumerate(cases):
        audio,tts_ms=await engine.synthesize(text);assert audio.startswith(b'RIFF') and len(audio)>1000
        transcript,language,stt_ms=await engine.transcribe(audio,'.wav')
        expected,actual=words(text),words(transcript)
        results.append({'case':index+1,'expected':text,'transcript':transcript,'tts_ms':tts_ms,'stt_ms':stt_ms,'word_error_rate':distance(expected,actual)/max(1,len(expected)),'language':language,'audio_bytes':len(audio)})
    report={'synthetic_audio_only':True,'real_microphone_accepted':False,'noise_accepted':False,'raw_audio_saved':False,'audio_uploaded':False,'env_modified':False,'cases':results}
    (ROOT/'.runtime/p7-voice-synthetic-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'synthetic_engine_exercised':True,'cases':len(results),'nonempty_transcripts':sum(bool(r['transcript']) for r in results),'stt_latency_ms':[r['stt_ms'] for r in results],'word_error_rates':[r['word_error_rate'] for r in results],'real_microphone_accepted':False,'audio_uploaded':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');p.add_argument('--smoke',action='store_true');a=p.parse_args()
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    if a.download:download()
    if a.smoke:asyncio.run(smoke())
