"use client";
import {useEffect,useState} from "react";
import type {components} from "../../../packages/contracts/schema";
type S=components["schemas"];
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;

function CreativeCard({row,api,workspace,manage,onSaved}:{row:S["CreativeView"];api:Api;workspace:string;manage:boolean;onSaved:()=>Promise<void>}){
  const meta=row.metadata;const [editing,setEditing]=useState(false);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
  const [form,setForm]=useState({product:meta?.product||"",market:meta?.market||"",language:meta?.language||"",format:meta?.format||"",
    duration_seconds:meta?.duration_seconds?String(meta.duration_seconds):"",hook:meta?.hook||"",angle:meta?.angle||"",offer:meta?.offer||"",
    cta:meta?.cta||"",creator:meta?.creator||"",landing_page:meta?.landing_page||""});
  async function save(){setBusy(true);setError("");try{const values=Object.fromEntries(Object.entries(form).map(([k,v])=>[k,v||null]));
    await api(`/v1/creatives/assets/${row.asset.id}/metadata?workspace_id=${workspace}`,'PUT',{version:meta?.version||0,brand_id:meta?.brand_id||null,
      ...values,duration_seconds:form.duration_seconds?Number(form.duration_seconds):null});setEditing(false);await onSaved();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  const shown=(value:string|number|null|undefined)=>value??'—';const feature=row.feature;
  return <article className={`pao-creative ${feature?.fatigue_status||'insufficient'}`}>
    <strong>{row.asset.name||`Creative ${row.asset.creative_id}`} · {feature?.fatigue_status?.toUpperCase()||'CHƯA PHÂN TÍCH'}</strong>
    <p>ID {row.asset.creative_id} · tuổi {feature?.age_days??'—'} ngày · confidence {feature?.confidence??'—'} · fatigue score {feature?.fatigue_score??'—'}</p>
    <div className="pao-report-cards"><span>Spend<strong>{shown(row.current?.spend)}</strong></span><span>CTR<strong>{shown(row.current?.ctr)}%</strong></span><span>CPA<strong>{shown(row.current?.cpa)}</strong></span><span>ROAS<strong>{shown(row.current?.roas)}</strong></span></div>
    <p>Hook: {meta?.hook||'chưa gắn nhãn'} · Angle: {meta?.angle||'—'} · Format: {meta?.format||'—'} · Market: {meta?.market||'—'}</p>
    {feature?.fatigue_status==='fatigued'&&<p role="alert">Creative cần refresh. Brief: 5 hooks, 3 angles, 2 CTA; thử một biến mỗi lần và cần người duyệt trước bước sản xuất/launch.</p>}
    <button disabled={!manage||busy} onClick={()=>setEditing(x=>!x)}>{editing?'Đóng':'Sửa metadata'}</button>
    {editing&&<div className="pao-creative-form">{([['product','Sản phẩm'],['market','Thị trường'],['language','Ngôn ngữ'],['format','Định dạng'],['hook','Hook'],['angle','Angle'],['offer','Offer'],['cta','CTA'],['creator','Creator'],['landing_page','Landing page']] as const).map(([key,label])=><label key={key}>{label}<input value={form[key]} onChange={e=>setForm(x=>({...x,[key]:e.target.value}))}/></label>)}
      <label>Thời lượng (giây)<input type="number" min={1} max={86400} value={form.duration_seconds} onChange={e=>setForm(x=>({...x,duration_seconds:e.target.value}))}/></label>
      <button disabled={busy} onClick={()=>void save()}>Lưu metadata</button></div>}{error&&<p role="alert">{error}</p>}
  </article>;
}

export default function CreativeIntelligencePanel({api,workspace,account,manage}:{api:Api;workspace:string;account:string;manage:boolean}){
  const [data,setData]=useState<S["CreativeDashboardOut"]|null>(null);const [asOf,setAsOf]=useState('');
  const [minimumImpressions,setMinimumImpressions]=useState(1000);const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');const [error,setError]=useState('');
  const query=`workspace_id=${workspace}&account_id=${encodeURIComponent(account)}`;
  async function refresh(){setData(await api<S["CreativeDashboardOut"]>(`/v1/creatives/dashboard?${query}`));}
  useEffect(()=>{let live=true;api<S["CreativeDashboardOut"]>(`/v1/creatives/dashboard?${query}`).then(x=>{if(live)setData(x)}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[api,query]);
  async function run(){setBusy(true);setError('');setNotice('');try{const result=await api<S["CreativeDashboardOut"]>('/v1/creatives/analyze','POST',{
    workspace_id:workspace,account_id:account,as_of:asOf,request_key:crypto.randomUUID(),current_days:3,baseline_days:3,
    minimum_impressions:minimumImpressions,minimum_age_days:7,saturation_impressions:10000,frequency_rise_pct:'20',ctr_decline_pct:'20',cpa_increase_pct:'20',cpm_stable_pct:'15'});
    setData(result);setNotice(`Đã phân tích ${result.run?.summary.creative_count||0} creative từ warehouse.`);}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  return <details className="pao-creatives"><summary>Creative Intelligence · Phase 14</summary>
    <p>Phân tích deterministic từ ad-level warehouse: winner, metadata, hiệu suất và fatigue đa tín hiệu. Chức năng này không gọi Meta và không tạo hoặc sửa quảng cáo.</p>
    <label>Ngày kết thúc<input type="date" aria-label="Ngày phân tích creative" value={asOf} onChange={e=>setAsOf(e.target.value)}/></label>
    <label>Minimum impressions mỗi cửa sổ<input type="number" min={100} value={minimumImpressions} onChange={e=>setMinimumImpressions(Number(e.target.value))}/></label>
    <button disabled={busy||!manage||!asOf} onClick={()=>void run()}>Phân tích creative</button><button disabled={busy} onClick={()=>void refresh()}>Làm mới</button>
    {data?.run&&<p>Analyst {data.run.analyst_version} · {String(data.run.summary.creative_count||0)} creatives · read-only.</p>}
    <h4>Creative health</h4>{data?.creatives.length?data.creatives.map(row=><CreativeCard key={row.asset.id} row={row} api={api} workspace={workspace} manage={manage} onSaved={refresh}/>):<p>Chưa có kết quả. Cần warehouse daily ở level ad và creative ID.</p>}
    <h4>Advertising Memory · Creative learnings</h4>{data?.learnings.length?data.learnings.map(row=><article className="pao-signal recommendation" key={row.id}><strong>{row.dimension}: {row.value}</strong><p>{row.statement}</p><p>Confidence {row.confidence} · {String(row.evidence.impressions||'—')} impressions · so sánh {String(row.evidence.compared_values||'—')} nhóm.</p></article>):<p>Chưa đủ ít nhất hai nhóm metadata có đủ mẫu để tạo learning.</p>}
    <p className="pao-muted">Frequency chỉ được tính khi creative thuộc một ad; khi tái sử dụng trên nhiều ad, PAO không cộng reach vì sẽ sai toán học. Pipeline tạo nội dung, thử nghiệm và launch thuộc phase sau.</p>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
