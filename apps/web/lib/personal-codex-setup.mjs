const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const id=v=>typeof v==='string'&&uuid.test(v);
export function personalCodexPath(workspace){if(!id(workspace))throw new Error('scope');return `/v1/workspaces/${workspace}/personal-cli`}
export function personalCodexView(value,workspace,actor){
 if(!id(workspace)||!id(actor)||!value||value.workspace_id!==workspace||value.actor_id!==actor||
  value.scope!=='local_personal_self_only'||value.tools_enabled!==false||value.provider_calls!==false||value.expires_at!==null||
  !Number.isSafeInteger(value.revision)||value.revision<0||['enabled','make_default','ready'].some(k=>typeof value[k]!=='boolean')||
  value.connection_id!==null&&!id(value.connection_id)||value.ready&&(!value.enabled||value.connection_id===null)||
  value.make_default&&!value.enabled||!Array.isArray(value.connections)||value.connections.length>100)throw new Error('scope');
 const seen=new Set();const connections=value.connections.map(row=>{
  if(!row||!id(row.id)||seen.has(row.id)||typeof row.model!=='string'||!row.model||row.model.length>120||/[\s\x00-\x1f\x7f]/.test(row.model)||
   !['pending','connected','disconnected','error'].includes(row.status)||typeof row.authentication_ready!=='boolean'||typeof row.operation_pending!=='boolean'||
   row.authentication_ready&&row.status!=='connected')throw new Error('shape');
  seen.add(row.id);return {id:row.id,model:row.model,status:row.status,authentication_ready:row.authentication_ready,operation_pending:row.operation_pending};
 });
 return {workspace_id:workspace,actor_id:actor,revision:value.revision,enabled:value.enabled,make_default:value.make_default,
  ready:value.ready,connection_id:value.connection_id,connections};
}
export function personalCodexSave(value,{enabled,makeDefault,connection},requestKey,ack){
 if(!id(requestKey)||typeof enabled!=='boolean'||typeof makeDefault!=='boolean'||typeof ack!=='boolean')throw new Error('shape');
 if(enabled&&(!ack||!value.connections.some(row=>row.id===connection&&row.authentication_ready&&!row.operation_pending)))throw new Error('consent');
 return {request_key:requestKey,expected_revision:value.revision,connection_id:enabled?connection:null,
  enabled,make_default:enabled&&makeDefault,allow_personal_inference_ack:ack};
}

// Called only by an explicit Connect action (or its official login completion).
// Keep default selection unchanged; a metadata read alone must never activate AI.
export async function connectPersonalCodex(request,workspace,actor,connection,requestKey,isCurrent){
 if(!id(connection)||!id(requestKey)||typeof isCurrent!=='function'||!isCurrent())throw new Error('scope');
 const path=personalCodexPath(workspace),value=personalCodexView(await request(path),workspace,actor);
 if(!isCurrent())throw new Error('scope');
 if(value.ready&&value.connection_id===connection)return value;
 const body=personalCodexSave(value,{enabled:true,makeDefault:value.make_default,connection},requestKey,true);
 const saved=personalCodexView(await request(path,'PUT',body),workspace,actor);
 if(!isCurrent()||!saved.ready||saved.connection_id!==connection)throw new Error('scope');
 return saved;
}
