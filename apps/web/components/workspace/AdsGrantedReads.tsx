"use client";
import {useEffect,useRef,useState} from "react";
import {settingsError} from '@/lib/settings-vi';
import {usePao} from "@/lib/PaoRuntimeContext";
type Grant={grant_id:string;kind:"meta_ads"|"google_ads";brand_id:string|null;account_id:string;expires_at:string};
type Metric={entity_id:string;day:string;currency:string;timezone:string;spend:string|null;impressions:number|null;clicks:number|null};
type Page={rows:Metric[];has_more:boolean;account_id:string};

export default function AdsGrantedReads({kind}:{kind?:'meta_ads'|'google_ads'}){
 const {api,activeWorkspace}=usePao(),workspace=activeWorkspace?.id||"",epoch=useRef(0),requestKey=useRef("");
 const [brands,setBrands]=useState<{id:string;name:string}[]>([]),[brand,setBrand]=useState("");
 const [grants,setGrants]=useState<Grant[]>([]),[choice,setChoice]=useState("");
 const today=new Date().toISOString().slice(0,10);
 const [since,setSince]=useState(today),[until,setUntil]=useState(today),[ack,setAck]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState(""),[report,setReport]=useState<Page|null>(null);
 const base=`/v1/workspaces/${workspace}/connection-inventory`,selected=grants.find(g=>g.grant_id===choice);
 useEffect(()=>{const scope=epoch,ticket=++scope.current;void api<{id:string;name:string}[]>(`/v1/brands?workspace_id=${workspace}`).then(rows=>{if(ticket===scope.current)setBrands(rows)}).catch(reason=>{if(ticket===scope.current)setError((reason as Error).message)});return()=>{scope.current++}},[api,workspace]);
 function reset(){epoch.current++;setGrants([]);setChoice("");setReport(null);setNotice("");setAck(false);requestKey.current=""}
 async function work(task:(ticket:number)=>Promise<void>){if(busy)return;const ticket=epoch.current;setBusy(true);setError("");try{await task(ticket)}catch(reason){if(ticket===epoch.current)setError((reason as Error).message)}finally{if(ticket===epoch.current)setBusy(false)}}
 return <section className="pao-model-access" aria-label="Đọc Ads bằng quyền đã cấp">
  <h3>Đọc Ads bằng quyền đã cấp</h3><p>Chỉ tài khoản và nhãn hàng đã được cấp. Không sửa quảng cáo hoặc chi tiền. Kết quả còn tùy thời điểm đồng bộ; số liệu thiếu không được coi như 0.</p>
  <label>Nhãn hàng<select aria-label="Nhãn hàng đọc Ads" disabled={busy} value={brand} onChange={e=>{reset();setBrand(e.target.value)}}><option value="">Không gắn nhãn hàng</option>{brands.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
  <button disabled={busy} onClick={()=>void work(async ticket=>{const result=await api<{items:Grant[];has_more:boolean}>(base+`/ads-grants${brand?"?brand_id="+brand:""}`);if(ticket===epoch.current){const items=result.items.filter(row=>!kind||row.kind===kind);setGrants(items);setChoice("");setReport(null);setAck(false);requestKey.current="";setNotice(result.has_more?"Danh sách quyền đang phân trang; có thể còn quyền của nền tảng này ở trang tiếp theo.":!items.length?"Không có quyền Ads hợp lệ trong phạm vi này.":"Thông tin quyền không xác nhận nhà cung cấp đang hoạt động.")}})}>Tải quyền đọc Ads</button>
  <label>Quyền đọc<select aria-label="Quyền Ads đã cấp" disabled={busy} value={choice} onChange={e=>{setChoice(e.target.value);setAck(false);setReport(null);requestKey.current=""}}><option value="">Chọn quyền…</option>{grants.map(g=><option key={g.grant_id} value={g.grant_id}>{g.kind} · {g.account_id} · {g.grant_id.slice(0,8)}</option>)}</select></label>
  <label>Từ ngày<input aria-label="Ads từ ngày" type="date" disabled={busy} value={since} max={today} onChange={e=>{setSince(e.target.value);setAck(false);setReport(null);requestKey.current=""}}/></label>
  <label>Đến ngày<input aria-label="Ads đến ngày" type="date" disabled={busy} value={until} max={today} onChange={e=>{setUntil(e.target.value);setAck(false);setReport(null);requestKey.current=""}}/></label>
  {selected&&<p>Tài khoản {selected.account_id} · hết hạn {new Date(selected.expires_at).toLocaleString("vi-VN")}.</p>}
  <label><input aria-label="Đồng ý đồng bộ Ads chỉ đọc" type="checkbox" disabled={busy||!selected} checked={ack} onChange={e=>setAck(e.target.checked)}/>Tôi yêu cầu chỉ đọc lịch sử số liệu tài khoản đã chọn, tối đa31ngày; không thay đổi dữ liệu Ads.</label>
  <button disabled={busy||!selected||!ack||!since||!until||since>until} onClick={()=>void work(async ticket=>{
   if(!selected)return;requestKey.current ||= crypto.randomUUID();
   const result=await api<{id:string;status:string}>(`/v1/integrations/${selected.kind==="meta_ads"?"meta":"google-ads"}/sync`,"POST",{workspace_id:workspace,grant_id:selected.grant_id,brand_id:brand||null,account_id:selected.account_id,request_key:requestKey.current,kind:"historical",since,until,...(selected.kind==="meta_ads"?{warehouse:true}:{})});
   if(ticket===epoch.current)setNotice(`công việc ${result.id.slice(0,8)} · ${result.status}. đang chờ không có nghĩa đã gọi nhà cung cấp hoặc đã có số liệu.`);
  })}>Xếp hàng đồng bộ Ads chỉ đọc</button>
  <button disabled={busy||!selected||!since||!until||since>until} onClick={()=>void work(async ticket=>{const result=await api<Page>(`${base}/grants/${choice}/ads-report?since=${since}&until=${until}${brand?"&brand_id="+brand:""}`);if(ticket===epoch.current){setReport(result);setNotice(result.rows.length?"Đã đọc số liệu có provenance đã hoàn tất đúng source/phiên bản/tài khoản.":"Chưa có số liệu đã hoàn tất trong khoảng này; không đồng nghĩa chi phí bằng 0.")}})}>Đọc báo cáo đã đồng bộ</button>
  {report&&<div aria-label="Báo cáo Ads được cấp">{report.rows.map(row=><p key={row.entity_id+row.day}>{row.day} · {row.entity_id} · chi phí {row.spend===null?"chưa có dữ liệu":row.spend+" "+row.currency} · {row.timezone}</p>)}{report.has_more&&<p>Báo cáo đang phân trang; không phải tổng số liệu toàn chiến dịch.</p>}</div>}
  {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{settingsError()}</p>}
 </section>;
}
