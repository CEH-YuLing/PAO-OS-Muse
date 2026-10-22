const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const model=v=>typeof v==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9._:/+-]{0,119}$/.test(v);
export function codexModelPath(wid,cid,action){if(!uuid.test(wid)||!uuid.test(cid)||!['models','model'].includes(action))throw Error('scope');return `/v1/workspaces/${wid}/cli-connections/${cid}/${action}`;}
export function codexModels(value,wid,uid,cid){
 if(!value||value.workspace_id!==wid||value.actor_id!==uid||value.connection_id!==cid||![wid,uid,cid].every(x=>uuid.test(x))||
  value.scope!=='local_personal_self_only'||value.inference_called!==false||!Number.isSafeInteger(value.version)||value.version<1||!model(value.current_model)||
  typeof value.consent_required!=='boolean'||!Array.isArray(value.models)||!value.models.length||value.models.length>500)throw Error('scope');
 const seen=new Set(),models=value.models.map(row=>{if(!row||!model(row.model)||typeof row.is_default!=='boolean'||seen.has(row.model))throw Error('shape');seen.add(row.model);return {model:row.model,is_default:row.is_default};});
 if(models.filter(row=>row.is_default).length>1)throw Error('shape');
 return {version:value.version,current_model:value.current_model,models,consent_required:value.consent_required};
}
