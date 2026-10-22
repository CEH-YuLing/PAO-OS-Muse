const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export function codexLoginPath(workspace,connection='',action=''){
 if(!uuid.test(workspace)||connection&&!uuid.test(connection)||!['','login','login/cancel','prepare','disconnect','login-capabilities'].includes(action))throw new Error('cli_login_scope_invalid');
 if(action==='login-capabilities'&&connection)throw new Error('cli_login_scope_invalid');
 return '/v1/workspaces/'+workspace+'/cli-connections'+(connection?'/'+connection:'')+(action?'/'+action:'');
}
export function codexLoginCapability(value){
 if(!value||value.provider!=='codex_cli'||typeof value.browser_login_enabled!=='boolean'||value.scope!=='local_personal_self_only'||value.managed_by!=='official_codex_app_server'||value.subscription_sharing_enabled!==false||value.tools_enabled!==false)throw new Error('cli_login_response_invalid');
 return value.browser_login_enabled;
}
export function codexLoginView(value,connection){
 if(!value||value.connection_id!==connection||!uuid.test(connection)||!Number.isSafeInteger(value.version)||value.version<1||
  !['starting','awaiting_user','connected','failed','expired','cancelled','cleanup_required','another_session','interrupted','idle'].includes(value.status)||
  value.operation_id!==null&&!uuid.test(value.operation_id)||!Number.isSafeInteger(value.expires_in)||value.expires_in<0||value.expires_in>600||value.provider_inference_verified!==false||value.grant_activated!==false)throw new Error('cli_login_response_invalid');
 if(value.status==='awaiting_user'){
  if(!uuid.test(value.operation_id)||value.verification_url!=='https://auth.openai.com/codex/device'||!/^([A-Z0-9]{4})-([A-Z0-9]{4,5})$/.test(value.user_code))throw new Error('cli_login_response_invalid');
 }else if(value.user_code!==null||value.verification_url!==null)throw new Error('cli_login_response_invalid');
 return {connection_id:connection,operation_id:value.operation_id,version:value.version,status:value.status,expires_in:value.expires_in,user_code:value.user_code,verification_url:value.verification_url};
}
export const codexLoginLabels={starting:'Đang chuẩn bị đăng nhập',awaiting_user:'Chờ bạn xác nhận tại OpenAI',connected:'Đã ghi nhận đăng nhập Codex',failed:'Đăng nhập chưa thành công',expired:'Phiên đăng nhập đã hết hạn',cancelled:'Đã hủy đăng nhập',cleanup_required:'Cần phục hồi phiên đăng nhập',another_session:'Phiên đăng nhập đang mở ở phiên PAO khác',interrupted:'Phiên bị gián đoạn, cần phục hồi',idle:'Chưa có phiên đăng nhập đang chạy'};
