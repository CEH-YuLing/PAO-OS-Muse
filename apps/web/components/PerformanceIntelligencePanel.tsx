"use client";
import {useEffect,useState} from "react";
import type {components} from "../../../packages/contracts/schema";
import MetaActionPanel from "./MetaActionPanel";
import AutopilotPolicyPanel from "./AutopilotPolicyPanel";
type S=components["schemas"];
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;

export default function PerformanceIntelligencePanel({api,workspace,account,manage}:{api:Api;workspace:string;account:string;manage:boolean}){
  const [target,setTarget]=useState<S["TargetOut"]|null>(null);const [rules,setRules]=useState<S["RuleOut"][]>([]);
  const [anomalies,setAnomalies]=useState<S["AnomalyOut"][]>([]);const [recommendations,setRecommendations]=useState<S["RecommendationOut"][]>([]);
  const [asOf,setAsOf]=useState('');const [granularity,setGranularity]=useState<'daily'|'hourly'>('daily');const [hour,setHour]=useState(0);
  const [cpa,setCpa]=useState('');const [roas,setRoas]=useState('');const [minimumSpend,setMinimumSpend]=useState('0');
  const [minimumImpressions,setMinimumImpressions]=useState(1000);const [minimumClicks,setMinimumClicks]=useState(20);
  const [minimumConversions,setMinimumConversions]=useState(3);const [minimumRunDays,setMinimumRunDays]=useState(3);const [freshness,setFreshness]=useState(180);
  const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');const [error,setError]=useState('');
  const query=`workspace_id=${workspace}&account_id=${encodeURIComponent(account)}`;
  async function refresh(){
    const [targets,ruleRows,alertRows,recRows]=await Promise.all([
      api<S["TargetOut"][]>(`/v1/ads/targets?workspace_id=${workspace}`),api<S["RuleOut"][]>(`/v1/ads/rules?${query}`),
      api<S["AnomalyOut"][]>(`/v1/ads/anomalies?${query}`),api<S["RecommendationOut"][]>(`/v1/ads/recommendations?${query}`)]);
    const found=targets.find(row=>row.account_id===account)||null;setTarget(found);setRules(ruleRows);setAnomalies(alertRows);setRecommendations(recRows);
    if(found){setCpa(found.target_cpa||'');setRoas(found.target_roas||'');setMinimumSpend(found.minimum_spend);
      setMinimumImpressions(found.minimum_impressions);setMinimumClicks(found.minimum_clicks);setMinimumConversions(found.minimum_conversions);
      setMinimumRunDays(found.minimum_run_days);setFreshness(found.freshness_minutes);}
  }
  useEffect(()=>{let live=true;refresh().catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[api,workspace,account]);
  async function act(fn:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function saveTarget(){
    const row=await api<S["TargetOut"]>('/v1/ads/targets','PUT',{workspace_id:workspace,account_id:account,target_cpa:cpa||null,target_roas:roas||null,
      minimum_spend:minimumSpend,minimum_impressions:minimumImpressions,minimum_clicks:minimumClicks,minimum_conversions:minimumConversions,
      minimum_run_days:minimumRunDays,freshness_minutes:freshness});setTarget(row);setNotice('Đã lưu targets và guardrails.');await refresh();
  }
  async function run(){
    const result=await api<S["IntelligenceOut"]>('/v1/ads/intelligence/analyze','POST',{workspace_id:workspace,account_id:account,as_of:asOf,
      granularity,hour:granularity==='hourly'?hour:null,request_key:crypto.randomUUID()});setAnomalies(result.anomalies);setRecommendations(result.recommendations);
    setNotice(`Performance Analyst đã phân tích ${result.run.summary.campaigns_analyzed||0} campaign.`);
  }
  const confidence=(value:string|number)=>{const score=Number(value);return score>=.8?'HIGH':score>=.55?'MEDIUM':'LOW';};
  return <details className="pao-intelligence"><summary>Performance Intelligence · Phase 10</summary>
    <p>Phân tích deterministic từ warehouse. Mọi đề xuất chỉ là advisor, không thể thay đổi quảng cáo.</p>
    <h4>Targets và guardrails</h4>
    <label>Target CPA<input aria-label="Target CPA" inputMode="decimal" value={cpa} onChange={e=>setCpa(e.target.value)}/></label>
    <label>Target ROAS<input aria-label="Target ROAS" inputMode="decimal" value={roas} onChange={e=>setRoas(e.target.value)}/></label>
    <label>Minimum spend<input type="number" min={0} value={minimumSpend} onChange={e=>setMinimumSpend(e.target.value)}/></label>
    <label>Minimum impressions<input type="number" min={0} value={minimumImpressions} onChange={e=>setMinimumImpressions(Number(e.target.value))}/></label>
    <label>Minimum clicks<input type="number" min={0} value={minimumClicks} onChange={e=>setMinimumClicks(Number(e.target.value))}/></label>
    <label>Minimum conversions<input type="number" min={0} value={minimumConversions} onChange={e=>setMinimumConversions(Number(e.target.value))}/></label>
    <label>Minimum run days<input type="number" min={1} max={30} value={minimumRunDays} onChange={e=>setMinimumRunDays(Number(e.target.value))}/></label>
    <label>Freshness tối đa (phút)<input type="number" min={15} max={10080} value={freshness} onChange={e=>setFreshness(Number(e.target.value))}/></label>
    <button disabled={busy||!manage||(!cpa&&!roas)} onClick={()=>void act(saveTarget)}>Lưu targets</button>
    <h4>Rule engine</h4>{rules.length?rules.map(rule=><label className="pao-check" key={rule.id}><input type="checkbox" checked={rule.enabled} disabled={busy||!manage}
      onChange={e=>void act(async()=>{await api(`/v1/ads/rules/${rule.id}?workspace_id=${workspace}`,'PUT',{enabled:e.target.checked});await refresh();})}/>{rule.name} · advisor</label>):<p>Lưu targets để khởi tạo rules.</p>}
    <h4>Chạy Performance Analyst</h4>
    <label>Ngày phân tích<input aria-label="Ngày phân tích intelligence" type="date" value={asOf} onChange={e=>setAsOf(e.target.value)}/></label>
    <label>Độ chi tiết<select aria-label="Độ chi tiết intelligence" value={granularity} onChange={e=>setGranularity(e.target.value as 'daily'|'hourly')}><option value="daily">Theo ngày</option><option value="hourly">Theo giờ</option></select></label>
    {granularity==='hourly'&&<label>Giờ account<input aria-label="Giờ intelligence" type="number" min={0} max={23} value={hour} onChange={e=>setHour(Number(e.target.value))}/></label>}
    <button disabled={busy||!manage||!target||!asOf} onClick={()=>void act(run)}>Phân tích hiệu suất</button><button disabled={busy} onClick={()=>void act(refresh)}>Làm mới intelligence</button>
    <h4>Anomalies</h4>{anomalies.length?anomalies.map(row=><article className={`pao-signal ${row.severity}`} key={row.id}><strong>{row.severity.toUpperCase()} · {row.kind}</strong>
      <p>Campaign {row.resource_id} · hiện tại {row.current_value??'—'} · baseline {row.baseline_value??'—'} · lệch {row.deviation_pct??'—'}%</p>
      {!row.acknowledged&&<button disabled={busy||!manage} onClick={()=>void act(async()=>{await api(`/v1/ads/anomalies/${row.id}/acknowledge?workspace_id=${workspace}`,'POST');await refresh();})}>Đã xem</button>}</article>):<p>Không có anomaly đang mở.</p>}
    <h4>Recommendations</h4>{recommendations.length?recommendations.map(row=><article className="pao-signal recommendation" key={row.id}><strong>{row.type} · confidence {confidence(row.confidence)} ({row.confidence})</strong>
      <p>{row.explanation}</p><p>Reason codes: {row.reason_codes.join(', ')} · dữ liệu {row.data_freshness_seconds}s trước</p>
      <p>Proposed action: {String(row.proposed_action.type||'none')} · executable: <strong>NO</strong></p>
      <button disabled={busy||!manage} onClick={()=>void act(async()=>{await api(`/v1/ads/recommendations/${row.id}/dismiss?workspace_id=${workspace}`,'POST');await refresh();})}>Bỏ qua</button></article>):<p>Chưa có recommendation đang hoạt động.</p>}
    <p className="pao-muted">Baseline dùng cùng thứ/giờ tối đa bốn mẫu lịch sử. Creative fatigue nằm trong Phase 14 bên dưới; landing CVR cần Phase 15. Phase 10 không gọi LLM và không ghi Meta.</p>
    <MetaActionPanel api={api} workspace={workspace} account={account} manage={manage}/>
    <AutopilotPolicyPanel api={api} workspace={workspace} account={account} manage={manage}/>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
