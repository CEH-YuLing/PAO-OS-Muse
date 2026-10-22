/** Strict metadata view. Catalog-only must never masquerade as live inference. */
export function museStatus(value){
 if(!value||!Number.isInteger(value.revision)||value.revision<0||typeof value.connected!=='boolean'||typeof value.can_manage!=='boolean'
  ||!Array.isArray(value.models)||typeof value.inference_enabled!=='boolean'||value.inference_verified!==false
  ||!['catalog_only','text_adapter'].includes(value.connection_mode)||value.scope!=='installation'||value.credentials_stored_in_PAO!==false
  ||(value.connection_mode==='text_adapter')!==value.inference_enabled)throw Error('muse_status_invalid');
 if(value.models.length>100||value.models.some(row=>!row||typeof row.model!=='string'||typeof row.display_name!=='string'||!Array.isArray(row.reasoning_efforts)||row.reasoning_efforts.some(v=>typeof v!=='string')))throw Error('muse_status_invalid');
 return value;
}
export function museError(message){
 if(message.includes('muse_installation_manager_required'))return 'Chỉ quản trị bản cài được kết nối hoặc ngắt Muse.';
 if(message.includes('muse_not_installed'))return 'Chưa tìm thấy bản Muse đã được kiểm chứng trên máy backend. Kiểm tra cài đặt Muse.';
 if(message.includes('muse_binary_changed')||message.includes('muse_schema_changed'))return 'Muse đã thay đổi phiên bản hoặc giao thức. Cần kiểm tra tương thích; PAO giữ nguyên cấu hình cũ.';
 if(message.includes('muse_revision_conflict'))return 'Cấu hình đã thay đổi. Bấm Đọc lại trạng thái đã lưu rồi thử lại.';
 return 'Chưa xác nhận được yêu cầu. Bấm Đọc lại trạng thái đã lưu để đối chiếu; PAO không tự gọi model, đăng xuất hoặc chuyển API trả phí.';
}
export function museLogin(value){
 if(!value||!['none','pending','granted','failed','cancelled','expired'].includes(value.status)||value.profile!=='pao_isolated')throw Error('muse_login_invalid');
 if(value.status==='pending'){
  const url=new URL(value.verification_url);
  if(url.protocol!=='https:'||!['auth.meta.com','www.meta.com','meta.com','dev.meta.ai','accountscenter.meta.com','www.facebook.com'].includes(url.hostname)||url.username||url.password||typeof value.user_code!=='string'||value.user_code.length>64)throw Error('muse_login_invalid');
  return {status:value.status,verification_url:url.href,user_code:value.user_code};
 }
 return {status:value.status};
}
