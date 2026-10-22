// Presentation and saved PAO metadata only. Never credentials or tool authority.
export const modelConnectionTabs = [
 {id:'client',label:'Kết nối qua Client',description:'Ưu tiên gói thuê bao'},
 {id:'api',label:'Kết nối qua API',description:'Khóa API của doanh nghiệp'},
];
export const clientProviders = [
 {id:'codex_cli',name:'Codex',detail:'Ứng dụng Codex CLI · tài khoản ChatGPT',metadata:true},
 {id:'claude_code',name:'Claude Code',detail:'Ứng dụng Claude Code · tài khoản Claude',metadata:false},
 {id:'antigravity',name:'Antigravity',detail:'Ứng dụng Antigravity · tài khoản Google',metadata:false},
 {id:'muse',name:'Muse',detail:'Ứng dụng Meta Muse Code · danh mục model và mức suy luận',metadata:false},
];
export function readModelConnection(search){
 const value=new URLSearchParams(search).get('model_connection');
 return value==='api'?'api':'client';
}
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function cliProfilesPath(workspace){
 if(!uuid.test(workspace))throw new Error('cli_scope_invalid');
 return `/v1/workspaces/${workspace}/cli-connections`;
}
export function cliProfileRows(value,workspace,actor){
 if(!uuid.test(workspace)||!uuid.test(actor)||!value||value.external_calls!==false||!Array.isArray(value.items)||value.items.length>100)throw new Error('cli_response_invalid');
 const ids=new Set();
 return value.items.map(row=>{
  if(!row||!uuid.test(row.id)||ids.has(row.id)||row.workspace_id!==workspace||row.owner_id!==actor||row.provider!=='codex_cli'||
   !Number.isSafeInteger(row.version)||row.version<1||!['pending','connected','disconnected','error'].includes(row.status)||
   typeof row.model!=='string'||!row.model.length||row.model.length>120||
   typeof row.authentication_ready!=='boolean'||typeof row.profile_operation_pending!=='boolean'||
   (row.authentication_ready&&row.status!=='connected')||row.credentials_stored_in_PAO!==false||
   row.scope!=='local_personal_self_only'||row.tools_enabled!==false||row.activation_required!==true)throw new Error('cli_response_invalid');
  ids.add(row.id);
  // Do not retain raw responses, device paths, setup commands or unknown fields.
  return {id:row.id,model:row.model,version:row.version,status:row.status,authentication_ready:row.authentication_ready,profile_operation_pending:row.profile_operation_pending};
 });
}
export function cliProfileLabel(row){
 if(row.profile_operation_pending)return 'Đang chuẩn bị hồ sơ';
 if(row.status==='connected'&&row.authentication_ready)return 'Đã ghi nhận đăng nhập';
 return {pending:'Chờ đăng nhập Codex',disconnected:'Đã ngắt trong PAO',error:'Cần kiểm tra đăng nhập'}[row.status]||'Chưa xác minh đăng nhập';
}
