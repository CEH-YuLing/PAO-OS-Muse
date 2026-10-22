const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
export function agyPath(workspace,action=''){
 if(!uuid.test(workspace)||!['','connect','disconnect','test'].includes(action))throw new Error('invalid_scope');
 return `/v1/workspaces/${workspace}/antigravity-native${action?'/'+action:''}`;
}
export function agyError(code){
 const messages={
  antigravity_native_binary_changed:'Client đã thay đổi phiên bản. Quản trị máy cần xác minh chữ ký và cập nhật bản được PAO cho phép; không cần nhập lại mật khẩu.',
  antigravity_native_tools_not_disabled:'Chưa thể chạy model an toàn: CLI vẫn bật công cụ. PAO đã dừng trước khi gửi câu hỏi; chưa tiêu quota cho câu thử.',
  antigravity_native_connect_first:'Hãy Kết nối hoặc Kiểm tra lại danh mục trước khi thử model.',
  antigravity_native_scope_changed:'Quyền hoặc doanh nghiệp đã thay đổi. Lượt thử không được xác nhận; không tự chạy lại.',
  antigravity_native_busy:'Client đang được kiểm tra. Hãy chờ lượt hiện tại kết thúc.',
 };
 return messages[code]||'Chưa xác minh kết quả. PAO không tự thử lại hoặc chuyển sang API tính phí. Kiểm tra trạng thái trước khi thực hiện lượt mới.';
}
export function agySmoke(value,workspace,actor){
 if(!value||value.workspace_id!==workspace||value.actor_id!==actor||!uuid.test(value.attempt_id)||
 value.status!=='passed'||value.model!=='gemini-3.8-flash-low'||value.response!=='PAO_ANTIGRAVITY_OK'||
 value.inference_verified!==true||value.prompt_sent!==true||value.tools_enabled!==false||
 value.general_chat_enabled!==false||value.provider_support_confirmed!==false)throw new Error('invalid_response');
 return value.response;
}
export function agyView(value,workspace,actor){
 if(!value||value.workspace_id!==workspace||value.actor_id!==actor||value.provider!=='antigravity_native'||
 value.scope!=='local_personal_machine_session'||value.credentials_stored_in_PAO!==false||
 value.inference_enabled!==false||value.inference_called!==false||value.provider_support_confirmed!==false||
 !['catalog_available','not_checked'].includes(value.status)||!Array.isArray(value.models)||value.models.length>100||
 value.models.some(x=>typeof x!=='string'||x.length>120||!(/^[a-z][a-z0-9]*(?:-[a-z0-9][a-z0-9._-]*)+$/.test(x)))||
 new Set(value.models).size!==value.models.length||typeof value.busy!=='boolean'||
 (value.status==='catalog_available')!==(value.models.length>0))throw new Error('invalid_response');
 return {status:value.status,models:[...value.models],busy:value.busy};
}
