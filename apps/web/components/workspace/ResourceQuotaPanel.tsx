"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import {resourcePools,resourceDraft,resourcePayload,resourceErrorHelp,validateResourceSnapshot,type ResourcePool,type ResourceSnapshot} from "@/lib/resource-quota.mjs";
import "./resource-quota.css";

export default function ResourceQuotaPanel(){
  const runtime=usePao(),member=runtime.activeWorkspace;
  if(!member)return <p>Chọn doanh nghiệp trước khi xem hạn mức.</p>;
  if(!["owner","admin"].includes(member.role))return <section aria-label="Hạn mức doanh nghiệp"><h2>Hạn mức doanh nghiệp</h2><p>Chỉ chủ doanh nghiệp/quản trị viên được xem và sửa hạn mức. Nhân viên cần liên hệ người quản lý; quyền mô hình không cấp quyền công cụ.</p></section>;
  return <section className="rq-panel" aria-label="Hạn mức doanh nghiệp"><h2>Hạn mức · {member.name}</h2>
    <p>Giới hạn dùng chung của doanh nghiệp này, không phải cho từng nhãn hàng hay nhân viên. Ngày tính từ 00:00 UTC (07:00 Việt Nam). Làm mới để xem số liệu mới nhất; không cập nhật liên tục.</p>
    <p className="rq-warning">Chi phí thực tế và hạn mức còn lại tại nhà cung cấp: <strong>Chưa xác định</strong>, không phải 0. Giới hạn PAO không phải hóa đơn, không thay đổi gói thuê bao và không cấp quyền chạy tác vụ.</p>
    <div className="rq-grid">{(Object.keys(resourcePools) as ResourcePool[]).map(pool=><ResourceCard key={`${runtime.me?.id}:${member.id}:${member.role}:${runtime.scopeRevision}:${pool}`} pool={pool} workspace={member.id}/>)}</div>
    <details><summary>Khi hạn mức chặn công việc, cần làm gì?</summary>{['tenant_model_daily_calls_exhausted','tenant_model_concurrency_exhausted','tenant_read_queue_exhausted'].map(code=><p key={code}>{resourceErrorHelp(code)}</p>)}<p>Tìm kiếm bộ nhớ/tri thức có thể chuyển sang từ khóa; vẫn phải có quyền dữ liệu. Không tự chuyển mô hình/đám mây, doanh nghiệp hoặc gửi lại tác vụ để vượt giới hạn. Công bằng tài nguyên toàn máy chủ chưa được nghiệm thu.</p></details>
  </section>;
}

function ResourceCard({pool,workspace}:{pool:ResourcePool;workspace:string}){
  const {apiRaw}=usePao(),spec=resourcePools[pool],epoch=useRef(0),lock=useRef(false),abort=useRef<AbortController|null>(null);
  const [snapshot,setSnapshot]=useState<ResourceSnapshot|null>(null),[draft,setDraft]=useState<Record<string,string>>({}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [observed,setObserved]=useState('');
  const request=useCallback(async(method:string,body?:unknown)=>{
    const controller=new AbortController();abort.current=controller;
    const response=await apiRaw(`/v1/workspaces/${workspace}/resources/${pool}`,{method,signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)]),
      ...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
    return validateResourceSnapshot(pool,await response.json(),workspace);
  },[apiRaw,workspace,pool]);
  const install=useCallback((data:ResourceSnapshot)=>{setSnapshot(data);setDraft(resourceDraft(pool,data));setObserved(new Date().toLocaleString('vi-VN'))},[pool]);
  const load=useCallback(async()=>{
    if(lock.current)return;lock.current=true;const ticket=++epoch.current;
    setBusy(true);setSnapshot(null);setDraft({});setError('');setNotice('');setObserved('');
    try{const data=await request('GET');if(ticket===epoch.current)install(data)}
    catch(reason){if(ticket===epoch.current)setError(resourceErrorHelp((reason as Error).message))}
    finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
  },[request,install]);
  useEffect(()=>{const currentEpoch=epoch,currentAbort=abort,currentLock=lock;void load();return()=>{currentEpoch.current++;currentAbort.current?.abort();currentLock.current=false}},[load]);
  let payload:Record<string,number>|null=null;
  if(snapshot)try{payload=resourcePayload(pool,snapshot,draft)}catch{}
  const changed=Boolean(snapshot&&payload&&Object.keys(spec.fields).some(key=>payload![key]!==snapshot[spec.policy]![key]));
  async function save(){
    if(lock.current||!snapshot||!payload||!changed)return;
    lock.current=true;const ticket=++epoch.current,body=payload;setBusy(true);setError('');setNotice('');
    try{const data=await request('PUT',body);if(ticket===epoch.current){install(data);setNotice('Đã lưu giới hạn của doanh nghiệp này. Không kích hoạt quyền, hoàn lại mức sử dụng hay hủy việc đang chạy.')}}
    catch(reason){if(ticket===epoch.current){setSnapshot(null);setDraft({});setObserved('');setError(resourceErrorHelp((reason as Error).message))}}
    finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
  }
  return <article className="rq-card" aria-label={`hạn mức ${pool}`} aria-busy={busy}>
    <h3>{spec.title}</h3><p>{spec.help}</p>
    <button type="button" onClick={()=>void load()} disabled={busy}>Tải lại hạn mức {spec.title}</button>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!snapshot?<p>{busy?'Đang đọc hạn mức…':'Chưa có trạng thái xác nhận; không thể lưu.'}</p>:<>
      <small>Phiên bản {snapshot[spec.policy]!.version} · đọc lúc {observed}. {snapshot[spec.policy]!.version===0?'Đang dùng mặc định; chưa tạo chính sách riêng.':''}</small>
      <dl>{Object.entries(spec.usage).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{String(snapshot.usage[key])}</dd></div>)}</dl>
      <form onSubmit={event=>{event.preventDefault();void save()}}>
        {Object.entries(spec.fields).map(([key,[label]])=><label key={key}>{label}<input aria-label={label} type="text" inputMode="numeric" autoComplete="off" value={draft[key]||''} disabled={busy} onChange={event=>setDraft(old=>({...old,[key]:event.target.value}))}/><small>1–{snapshot.host_ceilings[key]} (trần hệ thống)</small></label>)}
        {!payload&&<p role="alert">{resourceErrorHelp('quota_form_invalid')}</p>}
        <p>Giảm giới hạn có thể chặn việc mới; không xóa lịch sử, hoàn lại hạn mức hay dừng việc đang chạy. Tải lại sẽ bỏ bản nháp. Chỉ lưu khi bạn đã kiểm tra đúng doanh nghiệp.</p>
        <button type="submit" disabled={busy||!payload||!changed}>Lưu hạn mức {spec.title}</button>
      </form>
    </>}
  </article>;
}
