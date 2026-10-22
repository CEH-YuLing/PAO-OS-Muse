"use client";
import {useEffect,useState} from "react";
import type {components} from "../../../packages/contracts/schema";
import AdsReportPanel from "./AdsReportPanel";
type S=components["schemas"];
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;
export default function WarehousePanel({api,workspace,account,manage,connected}:{api:Api;workspace:string;account:string;manage:boolean;connected:boolean}) {
  const [grain,setGrain]=useState("daily");const [level,setLevel]=useState("campaign");
  const [since,setSince]=useState("");const [until,setUntil]=useState("");
  const [data,setData]=useState<S["MetricsPage"]|null>(null);const [offset,setOffset]=useState(0);
  const [interval,setIntervalMinutes]=useState(1440);const [lookback,setLookback]=useState(3);
  const [schedules,setSchedules]=useState<S["ScheduleOut"][]>([]);
  const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [notice,setNotice]=useState("");
  const query=`workspace_id=${workspace}&account_id=${encodeURIComponent(account)}`;
  useEffect(()=>{let live=true;api<S["ScheduleOut"][]>(`/v1/warehouse/schedules?workspace_id=${workspace}`).then(x=>{if(live)setSchedules(x);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[api,workspace]);
  async function load(page=0){const x=await api<S["MetricsPage"]>(`/v1/warehouse/metrics?${query}&since=${since}&until=${until}&level=${level}&granularity=${grain}&offset=${page}`);setData(x);setOffset(page);}
  async function act(fn:()=>Promise<void>){setBusy(true);setError("");setNotice("");try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function schedule(enabled:boolean){
    const x=await api<S["ScheduleOut"]>("/v1/warehouse/schedules","PUT",{workspace_id:workspace,account_id:account,granularity:grain,enabled,interval_minutes:interval,lookback_days:lookback});
    setSchedules(old=>[...old.filter(s=>s.id!==x.id),x]);setNotice(enabled?"Đã bật lịch đồng bộ.":"Đã tắt lịch đồng bộ.");
  }
  const current=schedules.find(s=>s.account_id===account&&s.granularity===grain);
  return <details className="pao-warehouse"><summary>Kho dữ liệu quảng cáo · Phase 8</summary>
    <p>Dữ liệu chuẩn hóa từ lần đồng bộ hoàn tất. “—” là chưa có số liệu, không phải 0. Số tiền giữ nguyên đơn vị tiền tệ của tài khoản.</p>
    <label>Độ chi tiết<select aria-label="Độ chi tiết warehouse" value={grain} onChange={e=>{setGrain(e.target.value);setData(null);}}><option value="daily">Theo ngày</option><option value="hourly">Theo giờ tài khoản</option></select></label>
    <label>Cấp dữ liệu<select aria-label="Cấp warehouse" value={level} onChange={e=>{setLevel(e.target.value);setData(null);}}>{['campaign','adset','ad'].map(x=><option key={x}>{x}</option>)}</select></label>
    <label>Từ ngày<input aria-label="Warehouse từ ngày" type="date" value={since} onChange={e=>{setSince(e.target.value);setData(null);}}/></label>
    <label>Đến ngày<input aria-label="Warehouse đến ngày" type="date" value={until} onChange={e=>{setUntil(e.target.value);setData(null);}}/></label>
    <button disabled={busy||!since||!until} onClick={()=>void act(()=>load())}>Đọc kho dữ liệu</button>
    <button disabled={busy||!manage||!connected||!since||!until} onClick={()=>void act(async()=>{
      await api('/v1/integrations/meta/sync','POST',{workspace_id:workspace,request_key:crypto.randomUUID(),kind:'historical',warehouse:true,granularity:grain,account_id:account,since,until});
      setNotice('Đã xếp hàng đồng bộ. Theo dõi trạng thái ở bảng Meta; đọc lại kho sau khi completed.');
    })}>Đồng bộ vào kho (tối đa 31 ngày)</button>
    {data&&<><div style={{overflowX:'auto'}}><table><thead><tr>{['Ngày/giờ','ID','Tiền tệ','Spend','Impressions','Clicks','Purchase','Revenue','ROAS'].map(x=><th key={x}>{x}</th>)}</tr></thead>
      <tbody>{data.rows.map((r,i)=><tr key={i}>{[`${r.day}${r.hour>=0?` ${r.hour}:00`:''}`,r.entity_id,r.currency,r.spend,r.impressions,r.clicks,r.purchase,r.revenue,r.roas].map((v,j)=><td key={j}>{v??'—'}</td>)}</tr>)}</tbody></table></div>
      {!data.rows.length&&<p>Chưa có dữ liệu trong khoảng đã chọn.</p>}
      {data.rows[0]&&<p>Múi giờ: {data.rows[0].timezone}. Cập nhật: {data.rows[0].updated_at}. CPA dùng purchase; attribution 7 ngày click + 1 ngày view.</p>}
      <button disabled={busy||offset===0} onClick={()=>void act(()=>load(offset-50))}>Trang trước</button>
      <button disabled={busy||!data.has_more} onClick={()=>void act(()=>load(offset+50))}>Trang sau</button></>}
    <p>Lịch {grain}: {current?.enabled?`đang bật, mỗi ${current.interval_minutes} phút, đọc lại ${current.lookback_days} ngày`:'đang tắt'}.</p>
    <label>Chu kỳ (phút)<input type="number" min={15} max={10080} value={interval} onChange={e=>setIntervalMinutes(Number(e.target.value))}/></label>
    <label>Số ngày đọc lại<input type="number" min={1} max={31} value={lookback} onChange={e=>setLookback(Number(e.target.value))}/></label>
    <button disabled={!manage||!connected||busy} onClick={()=>void act(()=>schedule(true))}>Bật lịch warehouse</button>
    <button disabled={!manage||busy||!current?.enabled} onClick={()=>void act(()=>schedule(false))}>Tắt lịch warehouse</button>
    <AdsReportPanel api={api} workspace={workspace} account={account} manage={manage}/>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
