"use client";
import {useEffect,useState} from "react";
import type {components} from "../../../packages/contracts/schema";
type S=components["schemas"];
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;

export default function AutopilotPolicyPanel({api,workspace,account,manage}:{api:Api;workspace:string;account:string;manage:boolean}){
  const [runtime,setRuntime]=useState<S["AutopilotRuntimeStatus"]|null>(null);const [detail,setDetail]=useState<S["PolicyDetail"]|null>(null);
  const [mode,setMode]=useState<'observer'|'advisor'|'copilot'|'autopilot'>('observer');const [halted,setHalted]=useState(true);
  const [pause,setPause]=useState(false);const [resume,setResume]=useState(false);const [budget,setBudget]=useState(false);
  const [maxChange,setMaxChange]=useState(10);const [budgetCap,setBudgetCap]=useState('');const [impressions,setImpressions]=useState(3000);
  const [conversions,setConversions]=useState(3);const [confidence,setConfidence]=useState('0.8');const [freshness,setFreshness]=useState(60);
  const [daily,setDaily]=useState(3);const [quiet,setQuiet]=useState(true);const [quietStart,setQuietStart]=useState('23:00');const [quietEnd,setQuietEnd]=useState('07:00');
  const [confirmed,setConfirmed]=useState(false);const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');const [error,setError]=useState('');
  function load(value:S["PolicyDetail"]|null){setDetail(value);const p=value?.policy;if(!p)return;setMode(p.mode as typeof mode);setHalted(p.halted);
    setPause(p.pause_allowed);setResume(p.resume_allowed);setBudget(p.budget_allowed);setMaxChange(p.max_budget_change_pct);
    setBudgetCap(p.max_daily_budget_minor_units==null?'':String(p.max_daily_budget_minor_units));setImpressions(p.minimum_impressions);
    setConversions(p.minimum_conversions);setConfidence(String(p.minimum_confidence));setFreshness(p.freshness_minutes);setDaily(p.max_actions_per_day);
    setQuiet(p.quiet_hours_enabled);setQuietStart(p.quiet_start.slice(0,5));setQuietEnd(p.quiet_end.slice(0,5));setConfirmed(false);}
  async function refresh(){const [r,rows]=await Promise.all([api<S["AutopilotRuntimeStatus"]>('/v1/ads/autopilot/status'),
    api<S["PolicyOut"][]>(`/v1/ads/autopilot/policies?workspace_id=${workspace}`)]);setRuntime(r);const found=rows.find(row=>row.account_id===account);
    load(found?await api<S["PolicyDetail"]>(`/v1/ads/autopilot/policies/${found.id}`):null);}
  useEffect(()=>{void refresh().catch(e=>setError(e.message));},[api,workspace,account]);
  async function act(fn:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function save(){const result=await api<S["PolicyDetail"]>('/v1/ads/autopilot/policies','PUT',{workspace_id:workspace,account_id:account,mode,halted,
    pause_allowed:pause,resume_allowed:resume,budget_allowed:budget,max_budget_change_pct:maxChange,max_daily_budget_minor_units:budgetCap?Number(budgetCap):null,
    minimum_impressions:impressions,minimum_conversions:conversions,minimum_confidence:Number(confidence),freshness_minutes:freshness,
    quiet_hours_enabled:quiet,quiet_start:quietStart,quiet_end:quietEnd,max_actions_per_day:daily,version:detail?.policy.version??null,
    confirmation:mode==='autopilot'&&!halted&&confirmed?'ENABLE AUTOPILOT':null});load(result);setNotice(result.effective_autopilot?'Limited Autopilot đang hiệu lực.':'Đã lưu policy ở trạng thái an toàn.');}
  async function freeze(value:boolean){if(!detail)return;const result=await api<S["PolicyDetail"]>(`/v1/ads/autopilot/policies/${detail.policy.id}/${value?'freeze':'unfreeze'}`,'POST',{
    version:detail.policy.version,reason:value?'Emergency freeze requested from PAO UI':'Reviewed and cleared from PAO UI',confirmation:value?'FREEZE':'UNFREEZE'});load(result);setNotice(value?'Đã emergency freeze và hạ về Advisor.':'Đã bỏ freeze; workspace vẫn halted.');}
  const effective=detail?.effective_autopilot;
  return <details className="pao-autopilot"><summary>Limited Autopilot · Phase 13</summary>
    <p>Runtime gates: global <strong>{runtime?.global_enabled?'ON':'OFF'}</strong> · Meta <strong>{runtime?.meta_enabled?'ON':'OFF'}</strong> · account <strong>{effective?'ACTIVE':'SAFE/OFF'}</strong>.</p>
    <p className="pao-muted">Fresh install là Observer. Chỉ recommendation của Performance Analyst đủ policy mới tự vào worker; action thủ công vẫn cần Phase 12 approval.</p>
    <label>Ads mode<select aria-label="Ads operating mode" value={mode} onChange={e=>setMode(e.target.value as typeof mode)}><option value="observer">Observer</option><option value="advisor">Advisor</option><option value="copilot">Copilot</option><option value="autopilot">Autopilot</option></select></label>
    <label className="pao-check"><input type="checkbox" checked={halted} onChange={e=>setHalted(e.target.checked)}/>Workspace kill switch / HALTED</label>
    <label className="pao-check"><input type="checkbox" checked={pause} onChange={e=>setPause(e.target.checked)}/>Cho phép pause</label>
    <label className="pao-check"><input type="checkbox" checked={resume} onChange={e=>setResume(e.target.checked)}/>Cho phép resume</label>
    <label className="pao-check"><input type="checkbox" checked={budget} onChange={e=>setBudget(e.target.checked)}/>Cho phép budget change</label>
    <label>Budget change tối đa %<input aria-label="Autopilot max budget percent" type="number" min={1} max={20} value={maxChange} onChange={e=>setMaxChange(Number(e.target.value))}/></label>
    <label>Daily budget cap — minor units<input aria-label="Autopilot daily budget cap" type="number" min={1} value={budgetCap} onChange={e=>setBudgetCap(e.target.value)}/></label>
    <label>Minimum impressions<input type="number" min={0} value={impressions} onChange={e=>setImpressions(Number(e.target.value))}/></label>
    <label>Minimum conversions<input type="number" min={0} value={conversions} onChange={e=>setConversions(Number(e.target.value))}/></label>
    <label>Minimum confidence<input type="number" min={0} max={1} step="0.05" value={confidence} onChange={e=>setConfidence(e.target.value)}/></label>
    <label>Freshness tối đa — phút<input type="number" min={15} max={1440} value={freshness} onChange={e=>setFreshness(Number(e.target.value))}/></label>
    <label>Actions tối đa/ngày<input type="number" min={1} max={100} value={daily} onChange={e=>setDaily(Number(e.target.value))}/></label>
    <label className="pao-check"><input type="checkbox" checked={quiet} onChange={e=>setQuiet(e.target.checked)}/>Bật quiet hours</label>
    <label>Quiet start<input type="time" value={quietStart} onChange={e=>setQuietStart(e.target.value)}/></label><label>Quiet end<input type="time" value={quietEnd} onChange={e=>setQuietEnd(e.target.value)}/></label>
    {mode==='autopilot'&&!halted&&<label className="pao-check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Tôi xác nhận bật Limited Autopilot cho account này</label>}
    <div className="pao-toolbar"><button disabled={!manage||busy||(budget&&!budgetCap)||(mode==='autopilot'&&!halted&&!confirmed)} onClick={()=>void act(save)}>Lưu Autopilot policy</button>
      <button disabled={busy} onClick={()=>void act(refresh)}>Làm mới policy</button>
      {detail&&!detail.policy.emergency_frozen&&<button disabled={!manage||busy} onClick={()=>void act(()=>freeze(true))}>EMERGENCY FREEZE</button>}
      {detail?.policy.emergency_frozen&&<button disabled={!manage||busy} onClick={()=>void act(()=>freeze(false))}>Bỏ freeze có kiểm soát</button>}</div>
    {detail&&<p>Policy v{detail.policy.version} · {detail.policy.mode} · {detail.policy.halted?'halted':'running'} · freeze: {detail.policy.freeze_reason||'—'} · audit: {detail.audit.map(row=>row.event).join(' → ')}</p>}
    {!runtime?.global_enabled&&<p className="pao-muted">Global gate đang OFF. Chỉ bật sau nghiệm thu bằng scripts/setup_autopilot.py và restart API/worker.</p>}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
