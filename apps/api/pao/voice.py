"""Local-only STT/TTS adapters. Raw audio and transcript are never persisted."""
import asyncio,os,shutil,tempfile,time
from pathlib import Path
from .config import ROOT,settings

class VoiceError(Exception): pass

def local_path(value:str)->Path:
    path=Path(value);return path if path.is_absolute() else ROOT/path

class LocalVoiceEngine:
    def __init__(self):self.model=None;self.lock=asyncio.Lock()
    def status(self):
        cfg=settings();model=local_path(cfg.voice_stt_model_path)
        try:import faster_whisper  # noqa:F401
        except ImportError:stt=False
        else:stt=model.is_dir()
        if cfg.voice_tts_provider=='windows_sapi':tts=os.name=='nt' and shutil.which('powershell.exe') is not None
        else:tts=bool(cfg.voice_tts_executable and cfg.voice_tts_model_path and local_path(cfg.voice_tts_executable).is_file() and local_path(cfg.voice_tts_model_path).is_file())
        return {'enabled':cfg.voice_enabled,'stt_ready':stt,'tts_ready':tts,'stt_device':cfg.voice_stt_device,'stt_compute_type':cfg.voice_stt_compute_type,'tts_provider':cfg.voice_tts_provider,'max_seconds':cfg.voice_max_seconds}
    async def transcribe(self,data:bytes,suffix:str):
        cfg=settings();state=self.status()
        if not cfg.voice_enabled or not state['stt_ready']:raise VoiceError('stt_not_ready')
        async with self.lock:
            if self.model is None:
                from faster_whisper import WhisperModel
                self.model=await asyncio.to_thread(WhisperModel,str(local_path(cfg.voice_stt_model_path)),device=cfg.voice_stt_device,compute_type=cfg.voice_stt_compute_type,local_files_only=True,cpu_threads=4,num_workers=1)
            fd,name=tempfile.mkstemp(suffix=suffix,dir=ROOT/'.runtime');os.close(fd);Path(name).write_bytes(data)
            started=time.monotonic()
            try:
                import av
                with av.open(name) as container:
                    if container.duration is not None: audio_seconds=float(container.duration/av.time_base)
                    else: audio_seconds=sum(frame.samples/frame.sample_rate for frame in container.decode(audio=0))
                if audio_seconds>cfg.voice_max_seconds+.5:raise VoiceError('audio_too_long')
                segments,info=await asyncio.to_thread(self.model.transcribe,name,language='vi',beam_size=3,vad_filter=True,vad_parameters={'min_silence_duration_ms':500})
                # faster-whisper segments are lazy; decode off the event loop.
                text=await asyncio.to_thread(lambda:' '.join(item.text.strip() for item in segments if item.text.strip()).strip())
                return text,getattr(info,'language','vi'),int((time.monotonic()-started)*1000)
            finally:Path(name).unlink(missing_ok=True)
    async def synthesize(self,text:str):
        cfg=settings();state=self.status()
        if not cfg.voice_enabled or not state['tts_ready']:raise VoiceError('tts_not_ready')
        fd,out=tempfile.mkstemp(suffix='.wav',dir=ROOT/'.runtime');os.close(fd);Path(out).unlink(missing_ok=True)
        started=time.monotonic()
        try:
            if cfg.voice_tts_provider=='windows_sapi':
                fd,source=tempfile.mkstemp(suffix='.txt',dir=ROOT/'.runtime');os.close(fd);Path(source).write_text(text,encoding='utf-8')
                command=[shutil.which('powershell.exe'),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/sapi_tts.ps1'),source,out]
            else:
                source='';command=[str(local_path(cfg.voice_tts_executable)),'--model',str(local_path(cfg.voice_tts_model_path)),'--output_file',out]
            process=await asyncio.create_subprocess_exec(*command,stdin=asyncio.subprocess.PIPE if cfg.voice_tts_provider=='piper' else None,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
            try:_,stderr=await asyncio.wait_for(process.communicate(text.encode('utf-8') if cfg.voice_tts_provider=='piper' else None),timeout=60)
            except TimeoutError:process.kill();await process.wait();raise VoiceError('tts_timeout')
            except asyncio.CancelledError:
                if process.returncode is None:process.kill();await process.wait()
                raise
            if process.returncode or not Path(out).is_file():raise VoiceError('tts_failed')
            return Path(out).read_bytes(),int((time.monotonic()-started)*1000)
        finally:
            Path(out).unlink(missing_ok=True)
            if 'source' in locals() and source:Path(source).unlink(missing_ok=True)

engine=LocalVoiceEngine()
