const fields=['app_id','api_version','redirect_uri','secret_present','revision','restart_required','write_enabled','autopilot_enabled','scope'];
export function metaAppCallback(value){
 try{
  if(typeof value!=='string'||value.length>512||/[\s\x00-\x1f\x7f]/.test(value)||value.includes('\\'))throw new Error();
  const uri=new URL(value);
  if(uri.username||uri.password||uri.search||uri.hash||uri.pathname!=='/v1/integrations/meta/callback'||value.includes('/../')||value.includes('/./')||/%/i.test(value)||
   !(uri.protocol==='https:'||uri.protocol==='http:'&&['localhost','127.0.0.1'].includes(uri.hostname)))throw new Error();
  return value;
 }catch{throw new Error('meta_app_config_invalid_input')}
}
export function metaAppStatus(value){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!fields.includes(key))||value.scope!=='installation_local'||
  !['secret_present','restart_required','write_enabled','autopilot_enabled'].every(key=>typeof value[key]==='boolean')||
  typeof value.app_id!=='string'||!/^\d{0,64}$/.test(value.app_id)||typeof value.api_version!=='string'||!(value.api_version===''||/^v\d+\.\d+$/.test(value.api_version)&&value.api_version.length<=16)||
  typeof value.revision!=='string'||!/^[a-f0-9]{64}$/.test(value.revision))throw new Error('meta_app_response_invalid');
 try{metaAppCallback(value.redirect_uri)}catch{throw new Error('meta_app_response_invalid')}
 return value;
}
export function metaAppPayload(status,draft){
 metaAppStatus(status);
 if(status.write_enabled||status.autopilot_enabled)throw new Error('meta_app_requires_readonly_mode');
 const appId=draft.appId,version=draft.version,callback=draft.callback,secret=draft.secret;
 if(typeof appId!=='string'||!/^\d{1,64}$/.test(appId)||typeof version!=='string'||!/^v\d+\.\d+$/.test(version)||version.length>16)throw new Error('meta_app_config_invalid_input');
 metaAppCallback(callback);
 if(typeof secret!=='string'||secret!==''&&!/^[A-Za-z0-9_-]{16,256}$/.test(secret))throw new Error('meta_app_config_invalid_input');
 if(!secret&&(!status.secret_present||appId!==status.app_id))throw new Error('meta_app_secret_required');
 return {app_id:appId,api_version:version,redirect_uri:callback,revision:status.revision,...(secret?{app_secret:secret}:{})};
}
export function metaAppError(code){
 const help={
  meta_app_config_requires_single_owner_workspace:'Bản cài nhiều doanh nghiệp hoặc chủ doanh nghiệp: biểu mẫu máy chủ App bị khóa. Quản trị viên cấu hình ứng dụng PAO trên máy chủ; App riêng từng doanh nghiệp triển khai ở S4, không dùng biểu mẫu này để thay ứng dụng toàn hệ thống.',
  meta_app_disconnect_before_change:'Có token Meta đang được lưu. Kiểm tra/ngắt kết nối phù hợp rồi đọc lại cấu hình; biểu mẫu không tự disconnect để đổi App.',
  meta_app_wait_for_sync:'Có công việc Meta đang chờ/chạy. Chờ kết thúc và đọc lại cấu hình; không tự hủy công việc hoặc lưu lại.',
  meta_app_wait_for_oauth:'Có phiên OAuth còn hạn. Hoàn tất/chờ hết hạn rồi đọc lại cấu hình; đóng popup không bảo đảm phiên máy chủ đã bị hủy.',
  meta_app_config_stale:'Cấu hình đã đổi ở phiên khác. Bấm Tải lại cấu hình, kiểm tra rồi xác nhận ý định mới; không ghi đè hoặc tự gửi lại.',
  meta_app_config_busy:'Cấu hình đang được xử lý bởi phiên khác. Chờ rồi đọc lại; không tự bỏ file lock hoặc gửi lại.',
  meta_app_environment_override:'Biến môi trường máy chủ đang ghi đè cấu hình. Quản trị viên cần xử lý; không nhập lại khóa bí mật hoặc tự restart.',
  meta_app_config_local_only:'Native API chỉ cho cấu hình từ loopback của bản cài; proxy/remote không tự là bằng chứng an toàn. Không mở public địa chỉ dịch vụ để né chốt này.',
  meta_app_requires_readonly_mode:'Write/autopilot gates đang bật. biểu mẫu máy chủ App chỉ dùng chế độ chỉ đọc; không tự đổi flags hoặc lưu cấu hình.',
  meta_app_existing_encryption_key_invalid:'Khóa mã hóa hiện có không hợp lệ. Cần quản trị viên kiểm tra backup/vault; không thay khóa tự động vì có thể mất khả năng giải mã credential cũ.',
  meta_app_secret_required:'Cần khóa bí mật mới khi chưa có khóa hoặc khi đổi App ID. Bản nháp đã bỏ; chỉ nhập trong password biểu mẫu trên máy, không gửi vào chat.',
  meta_app_config_invalid_input:'Kiểm tra App ID số, phiên bản vNN.N, địa chỉ nhận kết quả HTTPS hoặc HTTP loopback đúng đường dẫn, không query/fragment; khóa bí mật theo profile native 16–256 chữ/số/gạch dưới/gạch ngang, không khoảng trắng. Bản nháp/khóa bí mật đã bỏ; chưa gửi yêu cầu.',
  meta_app_response_invalid:'Response không đúng profile máy chủ cấu hình. biểu mẫu bị khóa; đọc lại và kiểm tra API trước khi lưu. Không coi dữ liệu thiếu hoặc truthy string là cấu hình an toàn.',
 };
 return help[code]||'Không xác nhận được kết quả. Máy chủ có thể đã lưu; bấm Tải lại cấu hình để đối chiếu trước ý định mới. lần đọc GET khi yêu cầu cũ còn chạy chưa chứng minh kết quả cuối. khóa bí mật/bản nháp đã bỏ; không tự gửi lại hoặc restart.';
}
