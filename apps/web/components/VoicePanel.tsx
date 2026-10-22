"use client";
import {useEffect,useRef,useState} from "react";
import {scopedStorageKey} from "@/lib/tenant-storage.mjs";
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;
type VoiceState="standby"|"listening"|"processing"|"speaking";
type Status={enabled:boolean;turns_enabled:boolean;stt_ready:boolean;tts_ready:boolean;max_seconds:number};
type Turn={id:string;session_id:string;status:string;version:number;transcript:string|null;run_id:string|null};
export default function VoicePanel({actor,api,apiRaw,workspace,sessionId,active,runId,runStatus,response,onTranscript,onCancel,onState}:{actor:string;api:Api;apiRaw:(path:string,init?:RequestInit)=>Promise<Response>;workspace:string;sessionId:string;active:boolean;runId?:string;runStatus?:string;response:string;onTranscript:(text:string,turn?:{id:string;version:number})=>Promise<boolean>;onCancel:()=>Promise<void>;onState:(state:VoiceState|null)=>void}){
  const [status,setStatus]=useState<Status|null>(null),[turn,setTurn]=useState<Turn|null>(null),[consent,setConsent]=useState(false),[muted,setMuted]=useState(false),[barge,setBarge]=useState(false);
  const [recording,setRecording]=useState(false),[processing,setProcessing]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const generation=useRef(0),currentTurn=useRef<Turn|null>(null),request=useRef<AbortController|null>(null),recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),context=useRef<AudioContext|null>(null),frame=useRef(0);
  const audio=useRef<HTMLAudioElement|null>(null),audioUrl=useRef(""),spoken=useRef(""),stateCallback=useRef(onState);stateCallback.current=onState;
  const storage=scopedStorageKey(actor,workspace,"voice",sessionId);
  function state(value:VoiceState|null){stateCallback.current(value)}
  function save(value:Turn){currentTurn.current=value;setTurn(value);sessionStorage.setItem(storage,value.id)}
  function stopAudio(){if(audio.current){audio.current.pause();audio.current.src="";audio.current=null}if(audioUrl.current){URL.revokeObjectURL(audioUrl.current);audioUrl.current=""}}
  function stopMic(){cancelAnimationFrame(frame.current);if(recorder.current){recorder.current.onstop=null;if(recorder.current.state!=="inactive")recorder.current.stop();recorder.current=null}stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;void context.current?.close();context.current=null}
  function invalidate(cancelServer=true){generation.current++;request.current?.abort();request.current=null;stopAudio();stopMic();const old=currentTurn.current;currentTurn.current=null;if(old&&cancelServer)void api(`/v1/voice/turns/${old.id}/cancel`,"POST").catch(()=>{});state(null)}
  useEffect(()=>{let live=true;void api<Status>("/v1/voice/status").then(x=>{if(live)setStatus(x)}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[api]);
  useEffect(()=>{
    invalidate(false);setTurn(null);setRecording(false);setProcessing(false);setNotice("");setError("");
    sessionStorage.removeItem(`pao.voice.turn.${workspace}.${sessionId}`); // Do not import unscoped legacy hints.
    const ticket=generation.current,id=sessionStorage.getItem(storage);
    if(id)void api<Turn>(`/v1/voice/turns/${id}`).then(value=>{if(ticket!==generation.current||value.session_id!==sessionId)return;save(value);if(value.run_id)spoken.current=value.run_id;setNotice("Đã khôi phục turn; không tự thu âm, gửi lại hoặc phát audio.")}).catch(()=>{sessionStorage.removeItem(storage)});
    return()=>invalidate();
  },[actor,sessionId,workspace,api,storage]);
  async function cancel(){invalidate();setTurn(null);setRecording(false);setProcessing(false);setNotice("Đã hủy voice turn; kết quả đến muộn bị bỏ qua.");if(active)await onCancel()}
  async function watchBarge(ticket:number){
    if(!barge||muted||!consent)return;
    try{const media=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,channelCount:1}});if(ticket!==generation.current){media.getTracks().forEach(t=>t.stop());return}stream.current=media;
      const ctx=new AudioContext();context.current=ctx;const analyser=ctx.createAnalyser();analyser.fftSize=512;ctx.createMediaStreamSource(media).connect(analyser);const values=new Uint8Array(analyser.fftSize);let loudAt=0;
      const check=()=>{if(ticket!==generation.current||!audio.current){stopMic();return}analyser.getByteTimeDomainData(values);const rms=Math.sqrt(values.reduce((s,v)=>s+((v-128)/128)**2,0)/values.length),now=performance.now();if(rms>.045){if(!loudAt)loudAt=now;if(now-loudAt>250){void start();return}}else loudAt=0;frame.current=requestAnimationFrame(check)};frame.current=requestAnimationFrame(check);
    }catch(e){if(ticket===generation.current)setError(`Không nghe ngắt lời: ${(e as Error).message}`)}
  }
  async function speak(value:Turn){
    if(!status?.tts_ready||muted||!consent||value.run_id!==runId)return;
    const ticket=generation.current;request.current?.abort();const abort=new AbortController();request.current=abort;state("processing");
    try{const res=await apiRaw(`/v1/voice/turns/${value.id}/speech`,{method:"POST",signal:abort.signal});const blob=await res.blob();if(ticket!==generation.current||abort.signal.aborted)return;stopAudio();const url=URL.createObjectURL(blob);audioUrl.current=url;const player=new Audio(url);audio.current=player;
      player.onplay=()=>{if(ticket===generation.current){state("speaking");void watchBarge(ticket)}};
      player.onended=()=>{if(ticket===generation.current){stopAudio();stopMic();state(null)}};
      player.onerror=()=>{if(ticket===generation.current){stopAudio();stopMic();state(null);setError("Không phát được audio local.")}};await player.play();
    }catch(e){if(ticket===generation.current&&!abort.signal.aborted){state(null);setError((e as Error).message)}}
  }
  useEffect(()=>{if(turn&&turn.run_id===runId&&runId&&runStatus==="completed"&&response&&spoken.current!==runId){spoken.current=runId;void speak(turn)}},[turn,runId,runStatus,response]);
  async function start(){
    if(!sessionId||!consent||muted||!status?.enabled||!status.turns_enabled||!status.stt_ready)return;
    invalidate();const ticket=generation.current;setTurn(null);setError("");setNotice("");setRecording(false);setProcessing(true);if(active)await onCancel();
    if(ticket!==generation.current)return;const abort=new AbortController();request.current=abort;
    try{const media=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,channelCount:1}});if(ticket!==generation.current){media.getTracks().forEach(t=>t.stop());return}stream.current=media;
      const res=await apiRaw("/v1/voice/turns",{method:"POST",signal:abort.signal,headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId,request_key:crypto.randomUUID(),consent_ephemeral_audio:true,consent_transcript_storage:true})});const value=await res.json() as Turn;
      if(ticket!==generation.current){void api(`/v1/voice/turns/${value.id}/cancel`,"POST").catch(()=>{});return}save(value);
      const mime=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")?"audio/ogg;codecs=opus":"audio/webm";
      const item=new MediaRecorder(media,{mimeType:mime}),chunks:Blob[]=[];recorder.current=item;
      item.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};item.onerror=()=>{if(ticket===generation.current){invalidate();setRecording(false);setProcessing(false);setError("Không thu được microphone.")}};
      item.onstop=async()=>{if(ticket!==generation.current)return;const blob=new Blob(chunks,{type:item.mimeType});stopMic();setRecording(false);setProcessing(true);state("processing");try{const result=await apiRaw(`/v1/voice/turns/${value.id}/audio`,{method:"POST",signal:abort.signal,headers:{"Content-Type":blob.type.split(";")[0]},body:blob});const ready=await result.json() as Turn;if(ticket!==generation.current)return;save(ready);setNotice("Kiểm tra bản chép lời rồi xác nhận gửi; không tự duyệt công cụ.");state(null)}catch(e){if(ticket===generation.current&&!abort.signal.aborted){setError((e as Error).message);state(null)}}finally{if(ticket===generation.current)setProcessing(false)}};
      item.start(250);setRecording(true);setProcessing(false);state("listening");const ctx=new AudioContext();context.current=ctx;const analyser=ctx.createAnalyser();analyser.fftSize=512;ctx.createMediaStreamSource(media).connect(analyser);const values=new Uint8Array(analyser.fftSize);let heard=false,last=performance.now(),began=last;
      const watch=()=>{if(ticket!==generation.current||item.state==="inactive")return;analyser.getByteTimeDomainData(values);const rms=Math.sqrt(values.reduce((s,v)=>s+((v-128)/128)**2,0)/values.length),now=performance.now();if(rms>.025){heard=true;last=now}if((heard&&now-last>1200)||now-began>status.max_seconds*1000){item.stop();return}frame.current=requestAnimationFrame(watch)};frame.current=requestAnimationFrame(watch);
    }catch(e){if(ticket===generation.current&&!abort.signal.aborted){invalidate();setRecording(false);setProcessing(false);setError((e as Error).message)}}
  }
  async function submit(){if(!turn?.transcript||turn.status!=="ready"||active)return;const value=turn,text=turn.transcript,ticket=generation.current;setProcessing(true);setError("");try{const sent=await onTranscript(text,{id:value.id,version:value.version});if(ticket!==generation.current)return;if(sent){const result=await api<Turn>(`/v1/voice/turns/${value.id}`);if(ticket===generation.current)save(result)}else setError("Chưa gửi được. Thử lại cùng turn, không tạo lượt mới.")}catch(e){if(ticket===generation.current)setError((e as Error).message)}finally{if(ticket===generation.current)setProcessing(false)}}
  return <section className="pao-voice" aria-label="Voice local"><div className="pao-toolbar"><span>Voice · P7 · {status?.enabled&&status.turns_enabled&&status.stt_ready?"READY":"OFF"}</span><button disabled={!sessionId||!consent||muted||!status?.enabled||!status.turns_enabled||!status.stt_ready||processing} onClick={()=>recording?recorder.current?.stop():void start()}>{recording?"Dừng nghe":"Nói với PAO"}</button><button onClick={()=>void cancel()}>Hủy voice turn</button></div>
    <label><input type="checkbox" checked={consent} onChange={e=>{setConsent(e.target.checked);if(!e.target.checked)void cancel()}}/>Tôi đồng ý xử lý audio tạm local và lưu bản chép lời (nháp 24h; sau gửi theo lịch sử chat). Không lưu raw audio.</label>
    <label><input type="checkbox" checked={muted} onChange={e=>{setMuted(e.target.checked);if(e.target.checked)void cancel()}}/>Tắt mic và âm thanh</label>
    <label><input type="checkbox" checked={barge} onChange={e=>{setBarge(e.target.checked);if(!e.target.checked&&!recording)stopMic()}}/>Nghe ngắt lời khi PAO đọc (dùng mic; VAD local)</label>
    <p className="pao-muted">Không tự reconnect microphone. Bấm Nói để ngắt lượt; STT đến muộn không được gửi. Mic thật/độ ồn/TTS tiếng Việt chưa nghiệm thu.</p>
    {turn?.status==="ready"&&<><p aria-label="Bản chép lời">{turn.transcript}</p><button disabled={processing||active||muted||!consent} onClick={()=>void submit()}>Xác nhận gửi bản chép lời</button></>}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </section>
}
