"use client";
import {useEffect, useRef, useState} from "react";
import WarehousePanel from "./WarehousePanel";
import type {components} from "../../../packages/contracts/schema";
type S=components["schemas"];
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;
const base="/v1/integrations/meta";

export default function MetaPanel({api,workspace,role}:{api:Api;workspace:string;role:string}) {
  const [connection,setConnection]=useState<S["pao__integrations__meta__schemas__ConnectionOut"]|null>(null);
  const [jobs,setJobs]=useState<S["pao__integrations__meta__schemas__SyncOut"][]>([]);
  const [accounts,setAccounts]=useState<Record<string,unknown>[]>([]);
  const [data,setData]=useState<S["SnapshotOut"]|null>(null);
  const [account,setAccount]=useState("");
  const [kind,setKind]=useState("campaigns");
  const [since,setSince]=useState("");const [until,setUntil]=useState("");
  const [offset,setOffset]=useState(0);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
  const live=useRef(true);const ticket=useRef(0);
  const query=`workspace_id=${workspace}`;
  const manage=role==="owner"||role==="admin";
  const active=jobs.some(j=>j.status==="queued"||j.status==="running");
  async function refresh() {
    const seq=++ticket.current;
    const [c,j,a]=await Promise.all([
      api<S["pao__integrations__meta__schemas__ConnectionOut"]>(`${base}/connection?${query}`),
      api<S["pao__integrations__meta__schemas__SyncOut"][]>(`${base}/jobs?${query}`),
      api<S["SnapshotOut"]>(`${base}/snapshots?${query}&kind=accounts`)]);
    if(live.current&&seq===ticket.current){setConnection(c);setJobs(j);setAccounts(a.rows);}
  }
  useEffect(()=>{live.current=true;const poll=()=>void refresh().catch(e=>{if(live.current)setError(e.message);});
    poll();const timer=setInterval(poll,5000);return()=>{live.current=false;ticket.current++;clearInterval(timer);};
  },[api,workspace]);
  useEffect(()=>{let current=true;
    if(!account){setData(null);return;}
    api<S["SnapshotOut"]>(`${base}/snapshots?${query}&kind=${kind}&account_id=${encodeURIComponent(account)}&offset=${offset}`)
      .then(x=>{if(current)setData(x);}).catch(e=>{if(current)setError(e.message);});
    return()=>{current=false;};
  },[api,workspace,account,kind,offset,jobs[0]?.status,connection?.status]);
  async function action(fn:()=>Promise<void>){setBusy(true);setError("");try{await fn();await refresh();}
    catch(e){if(live.current)setError((e as Error).message);}finally{if(live.current)setBusy(false);}}
  async function sync(type:"accounts"|"historical") {
    await api(`${base}/sync`,"POST",{workspace_id:workspace,request_key:crypto.randomUUID(),kind:type,
      ...(type==="historical"?{account_id:account,since,until}:{})});
  }
  return <details className="pao-meta"><summary>Meta Ads · Copilot</summary>
    <p>Trạng thái: {connection?.status||"đang tải"}. Quyền: ads_read.</p>
    {connection&&!connection.configured&&<p>Chưa cấu hình Meta trên máy chủ. Chạy scripts/setup_meta.py để nhập App ID, phiên bản API và App Secret.</p>}
    <p className="pao-muted">Dữ liệu là bản chụp từ lần đồng bộ hoàn tất, chưa phải báo cáo trực tiếp. Phase 7 không tạo hoặc sửa quảng cáo.</p>
    <div className="pao-toolbar"><button disabled={busy} onClick={()=>void action(refresh)}>Làm mới Meta</button>
      <button disabled={!manage||busy||!connection?.configured} onClick={()=>{
        const popup=window.open("about:blank","pao-meta","popup,width=700,height=750");
        if(!popup){setError("Cho phép cửa sổ bật lên để kết nối Meta.");return;}
        void action(async()=>{try{const x=await api<S["OAuthStart"]>(`${base}/oauth/start?${query}`,"POST");popup.location.href=x.authorization_url;}
          catch(e){popup.close();throw e;}});
      }}>Kết nối Meta</button>
      <button disabled={!manage||busy||connection?.status==="disconnected"} onClick={()=>void action(async()=>{
        await api(`${base}/connection?${query}`,"DELETE");setAccount("");setData(null);
      })}>Ngắt kết nối</button></div>
    <button disabled={!manage||busy||active||connection?.status!=="connected"} onClick={()=>void action(()=>sync("accounts"))}>Đồng bộ tài khoản</button>
    <label>Tài khoản quảng cáo<select aria-label="Tài khoản Meta" value={account} onChange={e=>{setAccount(e.target.value);setOffset(0);}}>
      <option value="">Chọn tài khoản</option>{accounts.map(a=><option key={String(a.id)} value={String(a.id)}>{String(a.name||a.id)} · {String(a.currency||"")}</option>)}</select></label>
    <form onSubmit={e=>{e.preventDefault();void action(()=>sync("historical"));}}>
      <label>Từ ngày<input type="date" required value={since} onChange={e=>setSince(e.target.value)}/></label>
      <label>Đến ngày<input type="date" required value={until} onChange={e=>setUntil(e.target.value)}/></label>
      <button disabled={!manage||busy||active||!account||connection?.status!=="connected"}>Đồng bộ lịch sử (tối đa 31 ngày)</button>
    </form>
    {jobs.slice(0,5).map(j=><p key={j.id}>{j.kind} · {j.account_id||"tài khoản"} · {j.status} · {j.row_count} bản ghi{j.error_code&&` · ${j.error_code}`}</p>)}
    {account&&<><label>Dữ liệu<select aria-label="Loại dữ liệu Meta" value={kind} onChange={e=>{setKind(e.target.value);setOffset(0);}}>
      {['campaigns','adsets','ads','insights'].map(k=><option key={k}>{k}</option>)}</select></label>
      <p>{data?.job?`Cập nhật: ${data.job.updated_at} · ${data.job.api_version} · ${data.job.since} → ${data.job.until}`:"Chưa có lượt đồng bộ lịch sử hoàn tất."}</p>
      {data?.rows.map((row,i)=><pre key={i} style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{JSON.stringify(row,null,2)}</pre>)}
      <button disabled={offset===0} onClick={()=>setOffset(x=>Math.max(0,x-50))}>Trước</button>
      <button disabled={!data?.has_more} onClick={()=>setOffset(x=>x+50)}>Sau</button>
    </>}
    {account&&connection?.status!=="disconnected"&&<WarehousePanel key={`${workspace}:${account}`} api={api} workspace={workspace} account={account} manage={manage} connected={connection?.status==="connected"}/>}
    {error&&<p role="alert">{error}</p>}
  </details>;
}
