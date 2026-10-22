// GET observations, not provider tests. Never turn flags/credentials into health.
export const settingsSources = [
  ['meta','Meta Ads','/v1/integrations/meta/connection','sme'],
  ['google','Google Ads','/v1/integrations/google-ads/connection','sme'],
  ['telegram','Telegram runtime','/v1/telegram/status','host'],
  ['voice','Voice runtime','/v1/voice/status','host'],
  ['automation','Temporal runtime','/v1/automation/status','host'],
  ['write','Ads write gate','/v1/ads/write-status','host'],
  ['autopilot','Autopilot gate','/v1/ads/autopilot/status','host'],
  ['platform','Platform evidence','/v1/platform/catalog','sme'],
  ['providers','Cloud model records','/v1/model-providers','sme'],
];
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const bools = (x,keys) => object(x) && keys.every(key=>typeof x[key]==='boolean');
const strings = x => Array.isArray(x) && x.every(item=>typeof item==='string');
export function settingsPath(path,scope,workspace) {
  if (!workspace) throw new Error('settings_scope_missing');
  return scope==='sme'?`${path}?workspace_id=${encodeURIComponent(workspace)}`:path;
}
export function validateSettingsStatus(key,x) {
  let valid=false;
  if (['meta','google'].includes(key)) valid=bools(x,['configured'])&&typeof x.status==='string'&&strings(x.scopes);
  if (key==='telegram') valid=bools(x,['enabled','configured'])&&typeof x.mode==='string'&&Number.isSafeInteger(x.allowed_peers)&&x.allowed_peers>=0&&Array.isArray(x.delivery_issues);
  if (key==='voice') valid=bools(x,['enabled','stt_ready','tts_ready'])&&typeof x.stt_device==='string'&&typeof x.stt_compute_type==='string'&&typeof x.tts_provider==='string'&&Number.isSafeInteger(x.max_seconds)&&x.max_seconds>0;
  if (key==='automation') valid=bools(x,['enabled'])&&typeof x.namespace==='string'&&typeof x.task_queue==='string';
  if (key==='write') valid=bools(x,['enabled','dry_run_default'])&&typeof x.max_budget_change_pct==='number'&&Number.isFinite(x.max_budget_change_pct);
  if (key==='autopilot') valid=bools(x,['global_enabled','meta_enabled'])&&typeof x.default_mode==='string'&&Number.isSafeInteger(x.phase);
  if (key==='platform') valid=object(x)&&['features','integrations','model_providers'].every(k=>Array.isArray(x[k])&&x[k].every(row=>object(row)&&typeof row.key==='string'&&typeof row.name==='string'))&&object(x.javis_compatibility);
  if (key==='providers') valid=Array.isArray(x)&&x.every(row=>bools(row,['configured','is_default'])&&['openai','anthropic','gemini','openrouter'].includes(row.provider)&&typeof row.name==='string'&&typeof row.status==='string'&&Number.isSafeInteger(row.model_count)&&row.model_count>=0&&(row.model===null||typeof row.model==='string')&&(row.key_hint===null||typeof row.key_hint==='string'));
  if (!valid) throw new Error('settings_status_invalid');
  return x;
}
export async function collectSettingsStatus(workspace,read) {
  const results=await Promise.allSettled(settingsSources.map(async([key,,path,scope])=>validateSettingsStatus(key,await read(settingsPath(path,scope,workspace)))));
  const data={},failed=[];
  results.forEach((result,index)=>{const [key,label]=settingsSources[index];if(result.status==='fulfilled')data[key]=result.value;else failed.push(label)});
  return {data,failed,responding:settingsSources.length-failed.length};
}
export const evidenceValue = value => value===true?'Có':value===false?'Chưa':'Chưa xác minh';
export function connectionEvidence(kind,record) {
  if (!record) return {configured:null,connected:null,healthy:null,accepted:null};
  if (kind==='telegram') return {configured:record.configured,connected:null,healthy:null,accepted:null};
  // A stored OAuth/model connected label is historical, not a live probe.
  return {configured:record.configured,connected:record.status==='connected',healthy:null,accepted:null};
}
