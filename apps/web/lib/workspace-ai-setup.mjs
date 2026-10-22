// Setup drafts are presentation only. Native policy endpoints remain authority.
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const providers=new Set(['openai','anthropic','gemini','openrouter']);
const validId=value=>typeof value==='string'&&uuid.test(value);
export function workspaceAiPolicy(value,workspace){
 if(!validId(workspace)||!value||typeof value!=='object'||Array.isArray(value)||value.workspace_id!==workspace||
  !Number.isSafeInteger(value.revision)||value.revision<0||typeof value.enabled!=='boolean'||typeof value.can_manage!=='boolean'||
  !Array.isArray(value.connections)||value.connections.length>100||
  value.default_connection_id!==null&&!validId(value.default_connection_id))throw new Error('invalid_ai_setup');
 const ids=new Set();
 const connections=value.connections.map(row=>{
  if(!row||!validId(row.id)||ids.has(row.id)||!providers.has(row.provider)||typeof row.model!=='string'||
   !row.model||row.model.length>120||/[\s\x00-\x1f\x7f]/.test(row.model)||!['connected','error'].includes(row.status)||
   ['selected','available','is_default'].some(key=>typeof row[key]!=='boolean')||
   row.is_default!==(value.default_connection_id===row.id)||row.available&&(!value.enabled||!row.selected||row.status!=='connected'))
   throw new Error('invalid_ai_setup');
  ids.add(row.id);
  return {id:row.id,provider:row.provider,model:row.model,status:row.status,selected:row.selected,available:row.available,is_default:row.is_default};
 });
 return {workspace_id:workspace,revision:value.revision,enabled:value.enabled,can_manage:value.can_manage,connections,default_connection_id:value.default_connection_id};
}
export function workspaceAiDraft(policy){
 const selected=policy.connections.filter(row=>row.selected).map(row=>row.id);
 const candidates=policy.connections.filter(row=>row.status==='connected');
 const defaultId=policy.default_connection_id?(policy.connections.some(row=>row.id===policy.default_connection_id)?policy.default_connection_id:''):(candidates.length===1?candidates[0].id:'');
 if(defaultId&&!selected.includes(defaultId))selected.push(defaultId);
 return {selected,defaultId,enabled:policy.enabled,suggested:!policy.default_connection_id&&Boolean(defaultId)};
}
export function workspaceAiSave(policy,draft,requestKey,ack){
 if(!validId(requestKey)||!policy.can_manage||typeof draft.enabled!=='boolean'||typeof ack!=='boolean'||
  !Array.isArray(draft.selected)||new Set(draft.selected).size!==draft.selected.length||
  draft.selected.some(id=>!policy.connections.some(row=>row.id===id))||
  draft.defaultId&&!draft.selected.includes(draft.defaultId))throw new Error('invalid_ai_setup');
 if(draft.enabled&&(!ack||!draft.defaultId||!draft.selected.length||
  draft.selected.some(id=>!policy.connections.some(row=>row.id===id&&row.status==='connected'))))throw new Error('ai_setup_consent_required');
 return {request_key:requestKey,expected_revision:policy.revision,enabled:draft.enabled,connection_ids:[...draft.selected],
  default_connection_id:draft.enabled?draft.defaultId:null,allow_enterprise_inference_ack:ack};
}
export function workspaceAiSettingsUrl(workspace,section='access',method='client'){
 if(!validId(workspace)||!['access','providers','members'].includes(section)||!['client','api'].includes(method))throw new Error('invalid_ai_setup');
 const query=new URLSearchParams({sme:workspace,tab:section==='members'?'team':'ai',section});
 if(section==='providers')query.set('model_connection',method);
 return '/settings?'+query.toString();
}
