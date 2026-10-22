"use client";
import {useEffect,useState} from "react";
import type {components} from "../../../packages/contracts/schema";
import PerformanceIntelligencePanel from "./PerformanceIntelligencePanel";
import CreativeIntelligencePanel from "./CreativeIntelligencePanel";
import AttributionCrmPanel from "./AttributionCrmPanel";
type S=components["schemas"];
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;
function compare(report:S["ReportOut"],metric:string,field:string){
  const group=report.comparison[metric];
  return group&&typeof group==='object'&&field in group?(group as Record<string,string|null>)[field]:null;
}

export default function AdsReportPanel({api,workspace,account,manage}:{api:Api;workspace:string;account:string;manage:boolean}) {
  const [kind,setKind]=useState<'daily'|'weekly'>('daily');const [end,setEnd]=useState('');
  const [dashboard,setDashboard]=useState<S["DashboardOut"]|null>(null);
  const [selected,setSelected]=useState<S["ReportDetail"]|null>(null);
  const [schedules,setSchedules]=useState<S["ReportScheduleOut"][]>([]);
  const [hour,setHour]=useState(8);const [weekday,setWeekday]=useState(0);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [destinations,setDestinations]=useState<{binding_id:string;bot_user_id:string|null;telegram_user_id:string}[]>([]),[destination,setDestination]=useState(''),[telegramAck,setTelegramAck]=useState(false),[destinationsKnown,setDestinationsKnown]=useState(false);
  const query=`workspace_id=${workspace}&account_id=${encodeURIComponent(account)}`;
  async function refresh(){
    const [d,s]=await Promise.all([api<S["DashboardOut"]>(`/v1/reports/dashboard?${query}`),
      api<S["ReportScheduleOut"][]>(`/v1/reports/configuration/schedules?workspace_id=${workspace}`)]);
    setDashboard(d);setSchedules(s);
  }
  useEffect(()=>{let live=true;Promise.all([api<S["DashboardOut"]>(`/v1/reports/dashboard?${query}`),
    api<S["ReportScheduleOut"][]>(`/v1/reports/configuration/schedules?workspace_id=${workspace}`)])
    .then(([d,s])=>{if(live){setDashboard(d);setSchedules(s);}}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[api,workspace,account]);
  useEffect(()=>{let live=true;setDestinationsKnown(false);setDestinations([]);setDestination('');setTelegramAck(false);
    api<{binding_id:string;bot_user_id:string|null;telegram_user_id:string}[]>('/v1/telegram/scoped/destinations?workspace_id='+workspace).then(rows=>{
      if(!Array.isArray(rows)||rows.some(r=>!r||!/^[-0-9a-f]{36}$/.test(r.binding_id)||!/^\d{1,16}$/.test(r.telegram_user_id)))throw new Error('invalid');
      if(live){setDestinations(rows);setDestinationsKnown(true)}
    }).catch(()=>{if(live)setDestinationsKnown(false)});return()=>{live=false};},[api,workspace]);
  async function act(fn:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function generate(){
    const report=await api<S["ReportDetail"]>('/v1/reports','POST',{workspace_id:workspace,account_id:account,kind,period_end:end,request_key:crypto.randomUUID()});
    setSelected(report);setNotice('Đã tạo báo cáo từ warehouse.');await refresh();
  }
  async function configure(enabled:boolean){
    const row=await api<S["ReportScheduleOut"]>('/v1/reports/configuration/schedules','PUT',{workspace_id:workspace,account_id:account,kind,
      enabled,delivery_hour:hour,weekday:kind==='weekly'?weekday:null,telegram:true,telegram_binding_id:enabled&&destination!=='legacy'?destination||null:null});
    setTelegramAck(false);
    setSchedules(old=>[...old.filter(x=>x.id!==row.id),row]);setNotice(enabled?'Đã bật lịch gửi báo cáo Telegram.':'Đã tắt lịch báo cáo.');
  }
  const latest=kind==='daily'?dashboard?.latest_daily:dashboard?.latest_weekly;
  const report=selected?.report||latest;
  const schedule=schedules.find(x=>x.account_id===account&&x.kind===kind);
  const shown=(value:string|number|null|undefined)=>value??'—';
  return <details className="pao-reports"><summary>Ads Reporting · Phase 9</summary>
    <p>Báo cáo đọc từ warehouse, không gọi Meta và không thay đổi quảng cáo. Chỉ tạo cho ngày đã hoàn tất theo múi giờ tài khoản.</p>
    <label>Loại báo cáo<select aria-label="Loại báo cáo Ads" value={kind} onChange={e=>{setKind(e.target.value as 'daily'|'weekly');setSelected(null);}}><option value="daily">Hằng ngày</option><option value="weekly">Hằng tuần</option></select></label>
    <label>Ngày kết thúc<input aria-label="Ngày kết thúc báo cáo" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
    <button disabled={busy||!manage||!end} onClick={()=>void act(generate)}>Tạo báo cáo</button>
    <button disabled={busy} onClick={()=>void act(refresh)}>Làm mới dashboard</button>
    {report?<section aria-label="Báo cáo quảng cáo hiện tại">
      <h3>{report.kind==='daily'?'Báo cáo ngày':'Báo cáo tuần'} · {report.period_start} → {report.period_end}</h3>
      <p>Dữ liệu {report.coverage_days}/{report.expected_days} ngày · {report.currency} · {report.timezone}</p>
      {report.coverage_days<report.expected_days&&<p role="alert">Dữ liệu chưa phủ đủ kỳ; các so sánh thiếu baseline hiển thị “—”.</p>}
      <div className="pao-report-cards"><span>Spend<strong>{shown(report.spend)}</strong></span><span>Revenue<strong>{shown(report.revenue)}</strong></span><span>ROAS<strong>{shown(report.roas)}</strong></span><span>CPA purchase<strong>{shown(report.cpa)}</strong></span></div>
      <p>Spend so với kỳ trước: {shown(compare(report,'spend','previous_period_pct'))}%{report.kind==='daily'&&` · so với TB 7 ngày trước: ${shown(compare(report,'spend','previous_7d_average_pct'))}%`}</p>
      {Boolean(report.comparison.business)&&<p>Business value · Actual orders: {shown(compare(report,'business','actual_orders'))} · CAC: {shown(compare(report,'business','cac'))} · Actual revenue: {shown(compare(report,'business','actual_revenue'))} {report.currency} · Tracking blocked: {String(compare(report,'business','optimization_blocked'))}</p>}
      <h4>Campaigns theo spend</h4><div style={{overflowX:'auto'}}><table><thead><tr><th>Campaign</th><th>Spend</th><th>Revenue</th><th>Purchases</th><th>ROAS</th></tr></thead><tbody>
        {report.campaigns.map((row,i)=><tr key={String(row.id||i)}><td>{String(row.name||row.id)}</td><td>{shown(row.spend as string|null)}</td><td>{shown(row.revenue as string|null)}</td><td>{shown(row.purchases as string|null)}</td><td>{shown(row.roas as string|null)}</td></tr>)}</tbody></table></div>
      <p>Underperformers/recommendations nằm trong Performance Intelligence; creative winners/fatigue nằm trong Creative Intelligence bên dưới.</p>
      {selected&&<button disabled={busy||!manage||!destination||!telegramAck||!destinationsKnown} onClick={()=>void act(async()=>{setTelegramAck(false);const d=await api<S["DeliveryOut"]>(`/v1/reports/${report.id}/telegram${destination==='legacy'?'':'?binding_id='+destination}`,'POST');setNotice(`Đã xếp báo cáo Telegram; chưa xác nhận đã gửi. Trạng thái: ${d.status}`);})}>Gửi báo cáo qua Telegram</button>}
    </section>:<p>Chưa có báo cáo {kind==='daily'?'ngày':'tuần'} cho tài khoản này.</p>}
    <h4>Xu hướng báo cáo ngày</h4><div style={{overflowX:'auto'}}><table><thead><tr><th>Ngày</th><th>Phủ dữ liệu</th><th>Spend</th><th>Revenue</th><th>ROAS</th></tr></thead><tbody>
      {(dashboard?.daily_trend||[]).map(row=><tr key={row.id}><td>{row.period_end}</td><td>{row.coverage_days}/{row.expected_days}</td><td>{shown(row.spend)} {row.currency}</td><td>{shown(row.revenue)} {row.currency}</td><td>{shown(row.roas)}</td></tr>)}</tbody></table></div>
    <h4>Lịch báo cáo</h4><p>{schedule?.enabled?`Đang bật · ${schedule.delivery_hour}:00 · lần tới ${schedule.next_at}`:'Đang tắt'}. Đích: Telegram + PAO UI.</p>
    <label>Nơi nhận báo cáo Telegram<select aria-label="Đích nhận báo cáo Telegram" value={destination} onChange={e=>{setDestination(e.target.value);setTelegramAck(false)}}><option value="">Chọn rõ bot và danh tính nhận</option>{destinations.map(row=><option key={row.binding_id} value={row.binding_id}>Bot {row.bot_user_id||'đã xác minh'} · Telegram ID {row.telegram_user_id}</option>)}<option value="legacy">Bot cũ dùng chung (chỉ khi đã được cấp phép)</option></select></label>
    {!destinationsKnown&&<p role="alert">Chưa xác minh danh sách nơi nhận; không thể gửi hoặc bật lịch. Kiểm tra quyền và tải lại trang.</p>}
    <p>Thiết lập danh tính và quyền nhận báo cáo trong Cài đặt → Kết nối → Telegram. Không tự chọn bot đầu tiên, không chuyển báo cáo sang doanh nghiệp hoặc nhân viên khác. Đổi quyền làm lịch cũ ngừng thay vì tự chọn đích mới.</p>
    <label><input type="checkbox" checked={telegramAck} disabled={busy||!destination||!destinationsKnown} onChange={e=>setTelegramAck(e.target.checked)}/>Tôi đã đối chiếu doanh nghiệp, bot và người nhận; đồng ý gửi báo cáo hoặc bật lịch tới đúng hội thoại riêng này.</label>
    <label>Giờ gửi theo múi giờ account<input aria-label="Giờ gửi báo cáo" type="number" min={0} max={23} value={hour} onChange={e=>setHour(Number(e.target.value))}/></label>
    {kind==='weekly'&&<label>Ngày gửi<select aria-label="Ngày gửi báo cáo tuần" value={weekday} onChange={e=>setWeekday(Number(e.target.value))}>{['Thứ Hai','Thứ Ba','Thứ Tư','Thứ Năm','Thứ Sáu','Thứ Bảy','Chủ Nhật'].map((x,i)=><option value={i} key={x}>{x}</option>)}</select></label>}
    <button disabled={busy||!manage||!destination||!telegramAck||!destinationsKnown} onClick={()=>void act(()=>configure(true))}>Bật lịch báo cáo</button>
    <button disabled={busy||!manage||!schedule?.enabled} onClick={()=>void act(()=>configure(false))}>Tắt lịch báo cáo</button>
    <p className="pao-muted">Monthly/custom cron/email chưa thuộc Phase 9.</p>
    <PerformanceIntelligencePanel api={api} workspace={workspace} account={account} manage={manage}/>
    <CreativeIntelligencePanel api={api} workspace={workspace} account={account} manage={manage}/>
    <AttributionCrmPanel api={api} workspace={workspace} account={account} manage={manage}/>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
