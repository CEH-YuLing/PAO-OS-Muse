"use client";
import {FormEvent,useCallback,useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import PaoAppShell from "./PaoAppShell";
import "./automation.css";
import {SectionTabs,useSection} from "./SectionNavigation";
const CHANNEL_VIEWS=[{id:"inbox",label:"Hội thoại"},{id:"channels",label:"Kênh nhắn tin"},{id:"outbox",label:"Tin chờ gửi"},{id:"audit",label:"Nhật ký"}];
type Binding={id:string;channel:string;kind:string;mode:string;enabled:boolean;version:number;outbound_confirmed:boolean;retention_days:number;session_id:string|null};
type Receipt={id:string;status:string;text:string|null;response:string|null;run_status:string|null;purged:boolean};
type Delivery={id:string;status:string;kind:string;text:string|null;attempts:number;error_code:string|null};
export default function ChannelsWorkspace(){
  const [view,setView]=useSection(CHANNEL_VIEWS,'view');
  const runtime=usePao(),member=runtime.activeWorkspace,workspace=member?.id;
  const allowed=member?.role==="owner"||member?.role==="admin";
  const [enabled,setEnabled]=useState(false),[rows,setRows]=useState<Binding[]>([]),[selected,setSelected]=useState("");
  const [inbox,setInbox]=useState<Receipt[]>([]),[outbox,setOutbox]=useState<Delivery[]>([]),[audit,setAudit]=useState<{id:string;data:unknown}[]>([]);
  const [error,setError]=useState(""),[notice,setNotice]=useState(""),[busy,setBusy]=useState(false);
  const generation=useRef(0),replyKey=useRef<{text:string;key:string}|null>(null);
  const reconcileKeys=useRef<Record<string,{remote:string;key:string}>>({});
  const row=rows.find(r=>r.id===selected);
  const load=useCallback(async()=>{
    if(!workspace||!allowed)return;
    const status=await runtime.api<{enabled:boolean}>(`/v1/channels/status?workspace_id=${workspace}`);setEnabled(status.enabled);
    setRows(await runtime.api<Binding[]>(`/v1/channels/bindings?workspace_id=${workspace}`));
  },[workspace,allowed,runtime.api]);
  const detail=useCallback(async()=>{
    if(!selected||!allowed)return;const ticket=generation.current;
    const [a,b,c]=await Promise.all([runtime.api<Receipt[]>(`/v1/channels/bindings/${selected}/inbox`),runtime.api<Delivery[]>(`/v1/channels/bindings/${selected}/outbox`),runtime.api<{id:string;data:unknown}[]>(`/v1/channels/bindings/${selected}/audit`)]);
    if(ticket!==generation.current)return;setInbox(a);setOutbox(b);setAudit(c);
  },[selected,allowed,runtime.api]);
  useEffect(()=>{void load().catch(e=>setError(e.message))},[load]);
  useEffect(()=>{generation.current++;setInbox([]);setOutbox([]);setAudit([]);replyKey.current=null;void detail().catch(e=>setError(e.message))},[detail]);
  async function action(work:()=>Promise<void>){setBusy(true);setError("");setNotice("");try{await work();await load();await detail()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function create(event:FormEvent<HTMLFormElement>){event.preventDefault();const f=new FormData(event.currentTarget);
    await action(async()=>{const value=await runtime.api<Binding>("/v1/channels/bindings","POST",{workspace_id:workspace,actor_id:f.get("actor"),external_identity:f.get("identity"),channel:f.get("channel"),kind:f.get("kind"),brain_id:f.get("brain")||null,peer_id:f.get("peer")||null,retention_days:Number(f.get("retention"))});setSelected(value.id);setNotice("Đã tạo binding ở chế độ im lặng. Chưa cho phép gửi ra ngoài.")});
  }
  async function control(value:string){if(!row)return;
    const confirm=value==="allow_outbound";
    if(confirm&&!window.confirm("Cho phép PAO gửi tới Telegram peer đã allowlist của binding này? Hãy kiểm tra destination trên trang Settings trước. Đây là cho phép gửi thật khi bridge được bật."))return;
    await action(async()=>{await runtime.api(`/v1/channels/bindings/${row.id}/control`,"POST",{request_key:crypto.randomUUID(),version:row.version,action:value,confirm_destination:confirm})});
  }
  async function reply(event:FormEvent<HTMLFormElement>){event.preventDefault();const text=String(new FormData(event.currentTarget).get("reply"));
    if(!row)return;if(!replyKey.current||replyKey.current.text!==text)replyKey.current={text,key:crypto.randomUUID()};
    await action(async()=>{await runtime.api(`/v1/channels/bindings/${row.id}/reply`,"POST",{request_key:replyKey.current!.key,text});setNotice("Đã lưu vào outbox; queued chưa có nghĩa đã giao.")});
  }
  async function reconcile(event:FormEvent<HTMLFormElement>,delivery:Delivery){event.preventDefault();const remote=String(new FormData(event.currentTarget).get("remote"));
    if(!window.confirm("Bạn đã tự thấy tin này được giao trên Telegram? Chỉ ghi nhận quan sát của bạn; PAO không truy vấn provider và không gửi lại tin."))return;
    if(!reconcileKeys.current[delivery.id]||reconcileKeys.current[delivery.id].remote!==remote)reconcileKeys.current[delivery.id]={remote,key:crypto.randomUUID()};
    await action(async()=>{await runtime.api(`/v1/channels/outbox/${delivery.id}/reconcile`,"POST",{request_key:reconcileKeys.current[delivery.id].key,remote_id:remote,observed_delivered:true});setNotice("Đã ghi quan sát của owner, không phải xác minh tự động từ provider.")});
  }
  return <PaoAppShell pageTitle="Hộp thư và kênh" pageSubtitle="Chung Run service; tiếp quản có audit, không tự cấp quyền gửi.">
    <SectionTabs id="channel-view" label="Khu vực hộp thư" items={CHANNEL_VIEWS} value={view} onChange={setView}/>
    {!allowed?<p role="status">Chỉ chủ doanh nghiệp/quản trị viên được quản lý kênh và hộp thư khách hàng.</p>:<>
      {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
      <section className="au-panel"><h2>Kênh nhắn tin</h2><p>{enabled?"Channel manager đang bật.":"Channel manager chưa bật. Không kết nối hoặc gửi ra ngoài."} Zalo/Slack/WhatsApp chưa triển khai; cần audit connector riêng.</p>
        <button disabled={busy} onClick={()=>void action(async()=>{})}>Làm mới inbox</button>
        <div hidden={view!=='channels'}><form onSubmit={create}><label>Kênh <select name="channel"><option value="local">Local — kiểm thử nội bộ</option><option value="telegram">Telegram — peer đã allowlist</option></select></label>
          <label>Danh tính bên ngoài <input name="identity" required maxLength={128}/></label><label>Mã người thực hiện (UUID) <input name="actor" defaultValue={runtime.me?.id} required/></label>
          <label>Loại liên kết <select name="kind"><option value="personal">Cá nhân — chính bạn</option><option value="customer">Khách hàng — operator + Brain bắt buộc</option></select></label>
          <label>Mã Brain (UUID) <input name="brain"/></label><label>Mã liên kết Telegram (UUID) <input name="peer"/></label><label>Mốc lưu trữ cũ (ngày, chưa bật xóa) <input name="retention" type="number" min={1} max={30} defaultValue={7}/></label>
          <p>Chính sách SaaS hiện tại không tự xóa nội dung. Mốc ngày chỉ là cấu hình được lưu, không tự bật job xóa. Yêu cầu xóa cần xem trước và xác nhận riêng trong Cài đặt.</p>
          <button disabled={!enabled||busy}>Tạo liên kết im lặng</button></form></div>
        <label>Liên kết <select aria-label="Binding" value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Chọn binding</option>{rows.map(r=><option key={r.id} value={r.id}>{r.channel} · {r.kind} · {r.mode} · {r.id}</option>)}</select></label>
      </section>
      {row&&<section className="au-panel"><div hidden={view!=='inbox'}><h2>Hội thoại và tiếp quản</h2><p role="status">Chế độ: {row.mode} · {row.enabled?"bật":"tắt"} · gửi Telegram: {row.outbound_confirmed?"đã xác nhận":"chưa cho phép"}</p>
        <p>Khách hàng chỉ nhận trích đoạn có nguồn từ Brain đã chọn; không tool, terminal hoặc tự duyệt. Lịch sử không phải dữ liệu ẩn danh; backup và audit metadata có policy riêng.</p>
        {[["human","Tiếp quản"],["quiet","Im lặng"],["auto","Cho phép bot"],[row.enabled?"disable":"enable",row.enabled?"Tắt binding":"Bật binding"]].map(([value,label])=><button key={value} disabled={busy||(!enabled&&!['human','quiet','disable'].includes(value))} onClick={()=>void control(value)}>{label}</button>)}
        {row.channel==="telegram"&&<button disabled={busy||!enabled} onClick={()=>void control(row.outbound_confirmed?"deny_outbound":"allow_outbound")}>{row.outbound_confirmed?"Thu hồi gửi ngoài":"Xác nhận destination Telegram"}</button>}
        <button disabled={busy||!enabled} onClick={()=>void action(async()=>{await runtime.api(`/v1/channels/bindings/${row.id}/purge-expired`,"POST")})}>Xóa nội dung đã hết hạn</button>
        {row.kind==='personal'&&row.session_id&&<button onClick={()=>void runtime.selectSession(row.session_id!)}>Đồng bộ session Web</button>}
        {inbox.map(r=><article key={r.id}><p>{r.status} · {r.run_status||"không có Run"}</p><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{r.purged?"[Đã xóa theo retention]":r.text}</pre>{r.response&&<pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{r.response}</pre>}</article>)}
        <form onSubmit={reply}><label>Trả lời của nhân viên <textarea name="reply" required maxLength={2000}/></label><button disabled={!enabled||busy||row.mode!=="human"}>Lưu trả lời vào outbox</button></form>
        </div><div hidden={view!=='outbox'}><h3>Tin chờ gửi</h3>{outbox.map(d=><article key={d.id}><p>{d.status} · {d.kind} · {d.attempts} lần · {d.error_code||"không lỗi"}</p><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{d.text}</pre>{d.status==="unknown"&&<><p>Không tự gửi lại. Kiểm tra tin trên Telegram; chưa xác minh delivery thật.</p><form onSubmit={e=>void reconcile(e,d)}><label>Mã tin đã quan sát <input name="remote" required maxLength={64} pattern="[A-Za-z0-9_:-]+"/></label><label><input type="checkbox" required/>Tôi đã thấy tin được giao trên Telegram, không suy từ queued</label><button disabled={busy}>Ghi quan sát đối soát của owner</button></form></>}</article>)}
        </div><div hidden={view!=='audit'}><h3>Nhật ký điều khiển</h3>{audit.map(a=><pre key={a.id} style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{JSON.stringify(a.data)}</pre>)}
      </div></section>}
    </>}
  </PaoAppShell>
}
