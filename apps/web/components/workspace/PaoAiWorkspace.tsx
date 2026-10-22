"use client";

import {FormEvent, useEffect, useMemo, useRef, useState} from "react";
import {
  Bot, BrainCircuit, Check, ChevronRight, CircleStop, FileSearch, Gauge,
  MessageSquare, Mic, Plus, Send, Sparkles, Wrench,
  Trash2,
} from "lucide-react";
import {usePao} from "@/lib/PaoRuntimeContext";
import {scopedStorageKey} from "@/lib/tenant-storage.mjs";
import {featureLabel,runtimeLabel} from '@/lib/display-status.mjs';
import PaoAppShell from "./PaoAppShell";
import ExecutionPanel from "@/components/ExecutionPanel";
import ToolPanel from "@/components/ToolPanel";
import MemoryPanel from "@/components/MemoryPanel";
import VoicePanel from "@/components/VoicePanel";
import KnowledgeChat from "./KnowledgeChat";
import EnginePicker from "./EnginePicker";
import ChatManagement from "./ChatManagement";
import "./pao-ai.css";
import "./pao-ai-scroll.css";
import "./chat-controls.css";

const MODES = ["Ask","Analyze","Plan","Execute","Research"] as const;
type Mode = typeof MODES[number];
const MODE_LABEL:Record<Mode,string>={Ask:'Hỏi',Analyze:'Phân tích',Plan:'Lập kế hoạch',Execute:'Thực hiện',Research:'Nghiên cứu'};
type VoiceState = "standby"|"listening"|"processing"|"speaking";

const QUICK_COMMANDS = [
  ["Phân tích quảng cáo","Phân tích hiệu suất quảng cáo và chỉ ra vấn đề quan trọng nhất."],
  ["Lập kế hoạch chiến dịch","Lập kế hoạch tạo một chiến dịch quảng cáo mới."],
  ["Tạo báo cáo","Tạo bản tóm tắt hiệu suất kinh doanh mới nhất."],
  ["Tìm vấn đề","Kiểm tra hệ thống và tìm các vấn đề cần xử lý."],
  ["Soạn nội dung","Lập kế hoạch nội dung phù hợp với thương hiệu."],
  ["Nghiên cứu thị trường","Nghiên cứu thị trường và đối thủ cạnh tranh."],
  ["Phân tích khách hàng","Phân tích pipeline CRM và chất lượng lead."],
  ["Thiết kế quy trình","Thiết kế workflow tự động hóa cho nhiệm vụ này."],
] as const;

export default function PaoAiWorkspace() {
  const runtime = usePao();
  const membership = runtime.activeWorkspace;
  const actorId = runtime.me?.id, workspaceId = runtime.workspaceId, scopeRevision = runtime.scopeRevision;
  const role = membership?.role || "viewer";
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<Mode>("Ask");
  const [voiceState, setVoiceState] = useState<VoiceState>("standby");
  const [creating, setCreating] = useState(false);
  const [knowledgeBusy,setKnowledgeBusy] = useState(false);
  const [engineBusy,setEngineBusy] = useState(false);
  const [chatBusy,setChatBusy] = useState(false);
  const [commandResult,setCommandResult] = useState("");
  const [contextTab, setContextTab] = useState<"context"|"activity">("context");
  const [voiceMobile,setVoiceMobile]=useState(false);
  const [voiceEnabled,setVoiceEnabled]=useState<boolean|null>(null);
  const statusApi=runtime.api;
  useEffect(()=>{let live=true;setVoiceEnabled(null);if(actorId&&workspaceId)void statusApi<{enabled:boolean}>('/v1/voice/status').then(value=>{if(live)setVoiceEnabled(typeof value.enabled==='boolean'?value.enabled:null)}).catch(()=>{});return()=>{live=false}},[statusApi,actorId,workspaceId,scopeRevision]);
  const messageEnd = useRef<HTMLDivElement | null>(null);
  const selectedSession = useMemo(
    () => runtime.sessions.find(session => session.id === runtime.sessionId) || null,
    [runtime.sessions, runtime.sessionId],
  );

  useEffect(() => {
    if (!runtime.sessionId && runtime.sessions.length && !runtime.busy) {
      void runtime.selectSession(runtime.sessions[0].id);
    }
  }, [runtime.sessionId, runtime.sessions, runtime.busy]);
  useEffect(() => {
    if (!actorId || !workspaceId) return;
    const key = scopedStorageKey(actorId, workspaceId, "prompt"), pending = sessionStorage.getItem(key);
    if (pending) {setDraft(pending); sessionStorage.removeItem(key);}
    const receive = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail?.actor === actorId && detail?.workspace === workspaceId &&
          detail?.revision === scopeRevision && typeof detail?.text === "string") setDraft(detail.text);
    };
    window.addEventListener("pao:prompt", receive);
    return () => window.removeEventListener("pao:prompt", receive);
  }, [actorId, workspaceId, scopeRevision]);
  useEffect(() => {messageEnd.current?.scrollIntoView({behavior:"smooth",block:"end"});}, [runtime.messages, runtime.response, runtime.state]);

  async function createConversation() {
    setCreating(true);
    try {await runtime.newSession();}
    finally {setCreating(false);}
  }
  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || !runtime.sessionId || (runtime.active && text!=="/stop") || knowledgeBusy || engineBusy || chatBusy) return;
    if (/^\/(help|status|brain|tasks|memory|model|usage|compact|export|stop|goal)(\s|$)/i.test(text)) {
      setChatBusy(true);setCommandResult("");
      try {const result=await runtime.api(`/v1/sessions/${runtime.sessionId}/commands`,"POST",{text});setCommandResult(JSON.stringify(result,null,2));setDraft("");window.dispatchEvent(new Event("pao:chat-config"))}
      catch(reason){setCommandResult((reason as Error).message)}finally{setChatBusy(false)}
      return;
    }
    const prompt = mode === "Ask" ? text : `[${mode} mode] ${text}`;
    setDraft("");
    const sent = await runtime.send(prompt);
    if (!sent) setDraft(text);
  }
  const liveMessage = runtime.active || (runtime.response && !runtime.messages.some(message => message.run_id === runtime.runId && message.role === "assistant"))
    ? runtime.response : "";

  return <PaoAppShell pageTitle="PAO AI" pageSubtitle="Bộ não điều phối — hỏi, phân tích, lập kế hoạch và thực thi có kiểm soát."
    pageActions={<ChatManagement key={`chat:${runtime.sessionId||'none'}`} onBusy={setChatBusy} placement="header"/>}>
    <div className="pao-ai-layout">
      <aside className="pao-ai-conversations">
        <header><div><p>LỊCH SỬ TRAO ĐỔI</p><h2>Hội thoại</h2></div><button type="button" aria-label="Hội thoại mới" onClick={() => void createConversation()} disabled={creating}><Plus size={17}/></button></header>
        <button className="pao-new-conversation" type="button" onClick={() => void createConversation()} disabled={creating}><Plus size={15}/>{creating ? "Đang tạo…" : "Hội thoại mới"}</button>
        <div className="pao-conversation-list">
          {runtime.sessions.map(session => <div key={session.id} className={`pao-conversation-row${session.id === runtime.sessionId ? " active" : ""}`}>
            <button type="button" className="pao-conversation-select" onClick={() => void runtime.selectSession(session.id)}>
              <MessageSquare size={15}/><span><strong>{session.title || "Hội thoại mới"}</strong><small>{new Intl.DateTimeFormat("vi-VN",{day:"2-digit",month:"2-digit"}).format(new Date(session.created_at))}</small></span>{session.id === runtime.sessionId && <ChevronRight size={14}/>}
            </button>
            <button type="button" className="pao-conversation-delete" aria-label="Xóa hội thoại" title={`Xóa ${session.title || "hội thoại"}`} disabled={runtime.busy || (session.id === runtime.sessionId && runtime.active)} onClick={() => {if(window.confirm("Xóa hội thoại này khỏi danh sách? Dữ liệu audit sẽ được lưu để bảo đảm an toàn.")) void runtime.deleteSession(session.id)}}><Trash2 size={13}/></button>
          </div>)}
          {!runtime.sessions.length && <div className="pao-conversation-empty"><MessageSquare size={22}/><p>Chưa có hội thoại.</p><span>Tạo hội thoại đầu tiên để bắt đầu.</span></div>}
        </div>
        <footer><i className={runtime.connected ? "online" : ""}/><span>{runtime.connected ? "SSE đã kết nối" : runtime.connection === "idle" ? "PAO sẵn sàng" : "Đang kết nối…"}</span></footer>
      </aside>

      <section className="pao-ai-chat">
        <header className="pao-ai-chat-header">
          <div className="pao-ai-identity"><span><Sparkles size={18}/></span><div><h2>PAO AI</h2><p>Trợ lý điều hành · Ưu tiên local</p></div></div>
          <button className="pao-mobile-voice" aria-label="Mở giọng nói local" onClick={()=>{setContextTab("activity");setVoiceMobile(true)}}><Mic size={17}/></button>
          <div className="pao-ai-mode" aria-label="Chế độ PAO">{MODES.map(item => <button key={item} type="button" aria-pressed={mode===item} onClick={() => setMode(item)}>{MODE_LABEL[item]}</button>)}</div>
          <div className={`pao-ai-runtime ${runtime.state}`}><i/><span>{runtimeLabel(voiceState !== "standby" ? voiceState : runtime.state)}</span></div>
          <div className="pao-ai-model-control"><EnginePicker key={`engine:${runtime.sessionId||'none'}`} onBusy={setEngineBusy} placement="header"/></div>
        </header>

        <div className="pao-ai-messages" aria-live="polite">
          {!runtime.sessionId ? <section className="pao-ai-welcome">
            <span><BrainCircuit size={30}/></span><p>PAO · TRỢ LÝ ĐIỀU HÀNH</p><h2>Bạn muốn PAO xử lý việc gì?</h2><div className="pao-quick-grid">{QUICK_COMMANDS.map(([label,prompt]) => <button key={label} type="button" onClick={() => setDraft(prompt)}><Sparkles size={14}/>{label}</button>)}</div>
            <button className="pao-welcome-create" type="button" onClick={() => void createConversation()}><Plus size={15}/> Tạo hội thoại để bắt đầu</button>
          </section> : <>
            {!runtime.messages.length && <section className="pao-ai-welcome compact"><span><BrainCircuit size={26}/></span><p>{selectedSession?.brand_id ? "NGỮ CẢNH NHÃN HÀNG" : "NGỮ CẢNH DOANH NGHIỆP"}</p><h2>Hỏi PAO bất cứ điều gì</h2><div className="pao-quick-grid">{QUICK_COMMANDS.slice(0,4).map(([label,prompt]) => <button key={label} type="button" onClick={() => setDraft(prompt)}><Sparkles size={14}/>{label}</button>)}</div></section>}
            {runtime.messages.map(message => <article key={message.id} className={`pao-ai-message ${message.role}`}>
              <div className="pao-message-avatar">{message.role === "assistant" ? <Sparkles size={15}/> : runtime.me?.email.slice(0,1).toUpperCase()}</div>
              <div><header><strong>{message.role === "assistant" ? "PAO" : "Bạn"}</strong><time>{new Intl.DateTimeFormat("vi-VN",{hour:"2-digit",minute:"2-digit"}).format(new Date(message.created_at))}</time></header><p>{message.content}</p></div>
            </article>)}
            {liveMessage && <article className="pao-ai-message assistant live"><div className="pao-message-avatar"><Sparkles size={15}/></div><div><header><strong>PAO</strong><span>{runtime.state}</span></header><p>{liveMessage}<i className="pao-caret"/></p></div></article>}
            {runtime.active && !liveMessage && <article className="pao-ai-thinking"><span/><span/><span/><p>{runtime.activeAgents.length ? `${runtime.activeAgents.join(", ")} đang xử lý` : "Chief of Staff đang suy luận"}</p></article>}
            <div ref={messageEnd}/>
          </>}
        </div>

        <div className="pao-ai-composer">
          <KnowledgeChat key={runtime.sessionId||"none"} onBusy={setKnowledgeBusy}/>
          {commandResult&&<pre aria-label="Kết quả lệnh chat" style={{maxHeight:150,overflow:"auto",whiteSpace:"pre-wrap"}}>{commandResult}</pre>}
          {runtime.active && <div className="pao-active-run"><span><i/>{runtime.activeAgents.join(", ") || "PAO"} đang xử lý</span><button type="button" onClick={() => void runtime.cancel()}><CircleStop size={14}/> Dừng</button></div>}
          <form onSubmit={submit}>
            <textarea aria-label="Nội dung yêu cầu PAO" placeholder={runtime.sessionId ? `${mode} với PAO…` : "Tạo hoặc chọn hội thoại trước"} value={draft} onChange={event => setDraft(event.target.value)} disabled={!runtime.sessionId || chatBusy || knowledgeBusy || engineBusy} rows={2} onKeyDown={event => {if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();void submit();}}}/>
          <div><span><Sparkles size={13}/>{MODE_LABEL[mode]} · {selectedSession?.memory_enabled === false ? "Bộ nhớ tắt" : "Bộ nhớ bật"}</span><div><button type="button" aria-label="Nhập bằng giọng nói" disabled={!runtime.sessionId||chatBusy||knowledgeBusy||engineBusy} onClick={()=>setContextTab("activity")}><Mic size={17}/></button><button className="pao-send" type="submit" aria-label="Gửi yêu cầu" disabled={!runtime.sessionId||!draft.trim()||(runtime.active&&draft.trim()!=="/stop")||chatBusy||knowledgeBusy||engineBusy}><Send size={17}/></button></div></div>
          </form>
          <p>PAO có thể mắc lỗi. Hành động quan trọng luôn yêu cầu phê duyệt.</p>
        </div>
      </section>

      <aside className={`pao-ai-context${voiceMobile?" is-voice-mobile":""}`}>
        {voiceMobile&&<button className="pao-mobile-voice-close" onClick={()=>{setVoiceMobile(false);setContextTab("context")}}>Đóng giọng nói local</button>}
        <header><button type="button" aria-pressed={contextTab==="context"} onClick={()=>setContextTab("context")}>Ngữ cảnh</button><button type="button" aria-pressed={contextTab==="activity"} onClick={()=>setContextTab("activity")}>Hoạt động</button></header>
        {contextTab === "context" ? <div className="pao-context-body">
          <section><p>NGỮ CẢNH HIỆN TẠI</p><div className="pao-context-chip"><BrainCircuit size={15}/><span><strong>PAO AI</strong><small>{membership?.name}</small></span><Check size={14}/></div></section>
          <section><p>HỘI THOẠI</p><dl><div><dt>Hội thoại</dt><dd>{selectedSession?.title || "Chưa chọn"}</dd></div><div><dt>Bộ nhớ</dt><dd>{selectedSession ? selectedSession.memory_enabled ? "Bật" : "Tắt" : "—"}</dd></div><div><dt>Lượt chạy</dt><dd>{runtimeLabel(runtime.run?.status || "idle")}</dd></div><div><dt>Trợ lý</dt><dd>{runtime.activeAgents.length || 0} đang xử lý</dd></div></dl></section>
          <section><p>CẤU HÌNH TRONG NGỮ CẢNH</p>{[
            ['Hội thoại',runtime.connected?'Đã kết nối':'Chưa kết nối',runtime.connected],
            ['Bộ nhớ',selectedSession?(selectedSession.memory_enabled?'Bật trong hội thoại':'Tắt trong hội thoại'):'Chưa chọn hội thoại',Boolean(selectedSession?.memory_enabled)],
            ['Công cụ',runtime.runId?'Theo quyền lượt chạy':'Chưa có lượt chạy',Boolean(runtime.runId)],
            ['Giọng nói',featureLabel(voiceEnabled),voiceEnabled===true],
          ].map(([label,state,on])=><div className="pao-layer" key={String(label)}><i className={on?'on':''}/><span>{label}</span><small>{state}</small></div>)}<p>Bật tính năng không thay cho kiểm tra dịch vụ hoặc thiết bị thật.</p></section>
          <section><p>GỢI Ý YÊU CẦU</p><div className="pao-context-commands">{QUICK_COMMANDS.map(([label,prompt])=><button key={label} type="button" onClick={()=>setDraft(prompt)}>{label}<ChevronRight size={13}/></button>)}</div></section>
        </div> : <div className="pao-context-body activity">
          {!runtime.runId && <div className="pao-context-empty"><Gauge size={22}/><p>Chưa có lượt chạy trong hội thoại này.</p></div>}
          {runtime.runId && <><ExecutionPanel api={runtime.api} runId={runtime.runId} active={runtime.active}/><ToolPanel api={runtime.api} runId={runtime.runId} role={role}/></>}
          {selectedSession && <MemoryPanel key={selectedSession.id} api={runtime.api} session={selectedSession} canWrite={role!=="viewer"}/>}
          {membership && <VoicePanel actor={runtime.me!.id} api={runtime.api} apiRaw={runtime.apiRaw} workspace={membership.id} sessionId={runtime.sessionId} active={runtime.active} runId={runtime.runId} runStatus={runtime.run?.status} response={runtime.response} onTranscript={runtime.send} onCancel={runtime.cancel} onState={state=>setVoiceState(state||"standby")}/>}
        </div>}
      </aside>
    </div>
    {runtime.error && <div className="pao-ai-error" role="alert">{runtime.error}{runtime.connection==="disconnected"&&<button type="button" onClick={runtime.reconnect}>Kết nối lại</button>}</div>}
  </PaoAppShell>;
}
