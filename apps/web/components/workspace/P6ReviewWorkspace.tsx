"use client";
import {FormEvent,useCallback,useEffect,useState} from "react";
import Link from "next/link";
import {usePao} from "@/lib/PaoRuntimeContext";
import PaoAppShell from "./PaoAppShell";
import StudioSchedulePanel from "./StudioSchedulePanel";
import GoalSchedulePanel from "./GoalSchedulePanel";
import ArtifactLearningPanel from "./ArtifactLearningPanel";
import OutcomeObservationPanel from "./OutcomeObservationPanel";
import "./automation.css";
type Item={id:string;source:string;status:string;source_hash:string;read:boolean;acknowledged:boolean;notification:boolean};
type Delivery={id:string;status:string;recipient_id:string;attempts:number;error_code:string|null;delivered_at:string|null};
type Proposal={id:string;candidate:string;source_id:string;fingerprint:string;status:string};
type Named={id:string;name?:string;title?:string};
type Message={id:string;role:string;content:string;status:string};

export default function P6ReviewWorkspace(){
  const runtime=usePao(),workspace=runtime.activeWorkspace?.id;
  const [tab,setTab]=useState("inbox"),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const [enabled,setEnabled]=useState(false),[items,setItems]=useState<Item[]>([]);
  const [brains,setBrains]=useState<Named[]>([]),[sessions,setSessions]=useState<Named[]>([]);
  const [brain,setBrain]=useState(""),[session,setSession]=useState(""),[messages,setMessages]=useState<Message[]>([]);
  const [source,setSource]=useState(""),[candidate,setCandidate]=useState(""),[proposals,setProposals]=useState<Proposal[]>([]);
  const [output,setOutput]=useState<unknown>(null);
  const [recipients,setRecipients]=useState<Record<string,string>>({}),[deliveries,setDeliveries]=useState<Record<string,Delivery[]>>({});
  const load=useCallback(async()=>{
    if(!workspace)return;setError("");
    try{
      const status=await runtime.api<{enabled:boolean}>(`/v1/results/status?workspace_id=${workspace}`);
      setEnabled(status.enabled);setItems(status.enabled?await runtime.api<Item[]>(`/v1/results?workspace_id=${workspace}`):[]);
      const [b,s]=await Promise.all([runtime.api<Named[]>(`/v1/brains?workspace_id=${workspace}`),runtime.api<Named[]>(`/v1/sessions?workspace_id=${workspace}`)]);
      setBrains(b);setSessions(s);
    }catch(e){setError((e as Error).message)}
  },[runtime.api,workspace]);
  useEffect(()=>{void load()},[load]);
  async function run(action:()=>Promise<void>){setBusy(true);setError("");try{await action()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function selectBrain(id:string){setBrain(id);setProposals([]);if(id)await run(async()=>setProposals(await runtime.api<Proposal[]>(`/v1/learning/brains/${id}/proposals`)))}
  async function selectSession(id:string){setSession(id);setMessages([]);setSource("");setCandidate("");if(id)await run(async()=>{
    const value=await runtime.api<{messages:Message[]}>(`/v1/sessions/${id}`);setMessages(value.messages.filter(m=>m.role==="user"&&m.status==="completed"));
  })}
  async function review(row:Proposal,decision:"promote"|"reject"|"revert"){
    if(!window.confirm(decision==="promote"?"Lưu trích đoạn này thành ghi chú dữ liệu? Không sửa policy, code hoặc skill.":decision==="revert"?"Thu hồi ghi chú do đề xuất tạo? Ghi chú đã sửa sẽ không bị ghi đè.":"Từ chối đề xuất này?"))return;
    await run(async()=>{const value=await runtime.api<Proposal>(`/v1/learning/proposals/${row.id}/review`,"POST",{fingerprint:row.fingerprint,decision});setProposals(old=>old.map(p=>p.id===value.id?value:p))});
  }
  async function propose(event:FormEvent){event.preventDefault();await run(async()=>{
    const value=await runtime.api<Proposal>(`/v1/learning/brains/${brain}/proposals`,"POST",{source_id:source,candidate});setProposals(old=>[value,...old.filter(p=>p.id!==value.id)]);
  })}
  async function schedule(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);
    await run(async()=>{const mode=String(form.get("mode")),now=new Date();setOutput(await runtime.api(`/v1/schedules/preview?workspace_id=${workspace}`,"POST",{
      kind:"studio_workflow",mode,timezone:String(form.get("timezone")),cron:mode==="cron"?String(form.get("cron")):null,
      once_at:mode==="once"?new Date(String(form.get("once_at"))).toISOString():null,
      after:new Date(now.getTime()-86400000).toISOString(),now:now.toISOString(),misfire:String(form.get("misfire")),grace_seconds:300,fold:"first"}));
    });
  }
  async function outcome(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);
    await run(async()=>setOutput(await runtime.api(`/v1/ads/actions/${encodeURIComponent(String(form.get("action_id")))}/outcomes`)));
  }
  async function deliveryList(row:Item){const value=await runtime.api<Delivery[]>(`/v1/results/${row.id}/deliveries`);setDeliveries(old=>({...old,[row.id]:value}))}
  async function deliver(row:Item){
    const recipient=recipients[row.id]||runtime.me?.id;
    if(!recipient||!window.confirm("Giao thông báo trong PAO cho thành viên này? Không gửi email/Telegram, không đánh dấu người nhận đã đọc và không chạy Goal."))return;
    await run(async()=>{await runtime.api(`/v1/results/${row.id}/deliveries`,"POST",{source_hash:row.source_hash,recipient_id:recipient,destination:"in_app"});await deliveryList(row)});
  }
  return <PaoAppShell pageTitle="P6 · Kết quả và duyệt" pageSubtitle="Dữ liệu có nguồn; chưa bật Goal runner hay gửi ra ngoài.">
    <section className="au-command"><Link href="/automation">← Automation</Link><Link href="/automation/goals">Goal runner dry-run</Link><button disabled={busy} onClick={()=>void load()}>Làm mới</button></section>
    <nav className="au-tabs" aria-label="P6 review">{[["inbox","Kết quả"],["learning","Learning có duyệt"],["artifact-learning","Học tài liệu"],["schedules","Xem trước lịch"],["goal-schedules","Lịch Goal"],["outcomes","Outcome"]].map(([id,title])=><button key={id} aria-pressed={tab===id} onClick={()=>{setTab(id);setOutput(null);setError("")}}>{title}</button>)}</nav>
    {error&&<p role="alert" className="au-message error">{error}</p>}
    {tab==="inbox"&&<section className="au-panel" aria-label="Result inbox"><h2>Kết quả dry-run</h2><p>Đọc/xác nhận riêng từng người; không chứng minh thành công nghiệp vụ.</p>
      {!enabled&&<p role="status">Inbox chưa bật trên backend này.</p>}{enabled&&!items.length&&<p>Chưa có kết quả terminal.</p>}
      {items.map(row=><article key={row.id}><h3>{row.status} · {row.id}</h3><p>Nguồn: {row.source}. <Link href={row.source==="goal_dry_run"?`/automation/goals?execution=${row.id}`:"/automation"}>Mở nguồn kết quả</Link></p><p>{row.acknowledged?"Đã xác nhận":row.read?"Đã đọc":"Chưa đọc"}</p>
        {row.notification&&<p>Thông báo đã giao cho bạn trong PAO.</p>}
        <button disabled={busy||row.read} onClick={()=>void run(async()=>{await runtime.api(`/v1/results/${row.id}/receipt`,"POST",{source_hash:row.source_hash,action:"read"});await load()})}>Đánh dấu đã đọc</button>
        <button disabled={busy||row.acknowledged} onClick={()=>void run(async()=>{await runtime.api(`/v1/results/${row.id}/receipt`,"POST",{source_hash:row.source_hash,action:"ack"});await load()})}>Xác nhận đã xem</button>
        <label>Thành viên nhận (UUID; mặc định chính bạn)<input style={{width:"100%",maxWidth:620,boxSizing:"border-box"}} aria-label={`Result recipient ${row.id}`} value={recipients[row.id]||runtime.me?.id||""} disabled={busy} onChange={e=>setRecipients(old=>({...old,[row.id]:e.target.value}))}/></label>
        <button disabled={busy||runtime.activeWorkspace?.role==="viewer"} onClick={()=>void deliver(row)}>Giao thông báo trong PAO</button>
        <button disabled={busy} onClick={()=>void run(()=>deliveryList(row))}>Xem trạng thái giao</button>
        {deliveries[row.id]?.map(d=><p key={d.id} aria-label={`Result delivery ${d.id}`}>{d.status} · người nhận {d.recipient_id} · lần xử lý {d.attempts} · {d.error_code||"Không có lỗi"}. {d.status==="failed"?"Không tự retry. Khôi phục quyền/nguồn rồi gửi lại đúng người nhận, tối đa 5 lần.":d.status==="pending"?"Đã lưu job, chưa giao; worker sẽ kiểm lại nguồn và quyền.":"Đã giao in-app, không đồng nghĩa đã đọc."}</p>)}
      </article>)}
    </section>}
    {tab==="learning"&&<section className="au-panel"><h2>Đề xuất ghi chú từ hội thoại</h2><p>Chỉ trích đoạn nguyên văn của người dùng. Mỗi đề xuất cần duyệt; không tự học vào code/policy/skill.</p>
      <label>Brain <select aria-label="Brain" value={brain} onChange={e=>void selectBrain(e.target.value)} disabled={busy}><option value="">Chọn Brain</option>{brains.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
      <label>Hội thoại <select aria-label="Hội thoại" value={session} onChange={e=>void selectSession(e.target.value)} disabled={busy}><option value="">Chọn hội thoại</option>{sessions.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
      <form onSubmit={propose}><label>Nguồn <select aria-label="Nguồn" value={source} onChange={e=>{setSource(e.target.value);setCandidate(messages.find(m=>m.id===e.target.value)?.content.slice(0,2000)||"")}} disabled={busy}><option value="">Chọn tin nhắn nguồn</option>{messages.map(m=><option key={m.id} value={m.id}>{m.content.slice(0,80)}</option>)}</select></label>
        <label>Trích đoạn <textarea aria-label="Trích đoạn" value={candidate} onChange={e=>setCandidate(e.target.value)} maxLength={2000} required/></label><button disabled={busy||!brain||!source||candidate.length<3}>Tạo đề xuất, chưa lưu kiến thức</button>
      </form>
      {proposals.map(row=><article key={row.id}><p>Trạng thái: {row.status}</p><p>Nguồn: {row.source_id}</p><pre>{row.candidate}</pre>
        {row.status==="pending"&&<><button disabled={busy} onClick={()=>void review(row,"promote")}>Duyệt lưu ghi chú</button><button disabled={busy} onClick={()=>void review(row,"reject")}>Từ chối</button></>}
        {row.status==="promoted"&&<button disabled={busy} onClick={()=>void review(row,"revert")}>Hoàn tác ghi chú</button>}
      </article>)}
    </section>}
    {tab==="schedules"&&<><StudioSchedulePanel/><section className="au-panel"><h2>Xem trước policy lịch, không tạo lịch</h2><p>Form dưới chỉ mô phỏng thời gian; lịch bền vững dùng panel phía trên.</p><form onSubmit={schedule}>
      <label>Loại <select name="mode"><option value="cron">Cron</option><option value="once">Một lần</option></select></label>
      <label>Múi giờ <input name="timezone" defaultValue="Asia/Ho_Chi_Minh" required/></label><label>Cron 5 trường <input name="cron" defaultValue="0 9 * * *"/></label>
      <label>Thời điểm một lần <input name="once_at" type="datetime-local"/></label><label>Quá hạn <select name="misfire"><option value="coalesce">Gộp lần quá hạn</option><option value="skip">Bỏ qua ngoài grace window</option></select></label>
      <button disabled={busy||!workspace}>Xem trước, không tạo job</button></form></section></>}
    {tab==="goal-schedules"&&<GoalSchedulePanel/>}
    {tab==="artifact-learning"&&<ArtifactLearningPanel/>}
    {tab==="outcomes"&&<><OutcomeObservationPanel/><section className="au-panel"><h2>Outcome 24h / 72h / 7d</h2><p>Đọc phép so sánh hiện tại, không lưu snapshot. Cần action thật được xác minh và warehouse đủ coverage. Meta đang hoãn nghiệm thu; KPI tăng không chứng minh nhân quả.</p><form onSubmit={outcome}><label>Mã action <input name="action_id" required pattern="[0-9a-fA-F-]{36}"/></label><button disabled={busy}>Đọc bằng chứng, không sửa Ads</button></form></section></>}
    {output!==null&&<pre aria-label="Kết quả xem trước">{JSON.stringify(output,null,2)}</pre>}
  </PaoAppShell>
}
