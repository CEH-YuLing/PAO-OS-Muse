const uuid=x=>typeof x==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(x);
const numeric=x=>typeof x==='string'&&/^[1-9][0-9]{0,15}$/.test(x);
const obj=x=>x&&typeof x==='object'&&!Array.isArray(x);
const deny=()=>{throw new Error('telegram_settings_response_invalid')};
export function telegramConnections(value,workspace){
 if(!obj(value)||value.workspace_id!==workspace||!uuid(workspace)||!['runtime_available','can_manage','can_pair'].every(k=>typeof value[k]==='boolean')||!Array.isArray(value.connections)||value.connections.length>100)deny();
 const seen=new Set(),connections=value.connections.map(row=>{
  if(!obj(row)||!uuid(row.id)||seen.has(row.id)||row.workspace_id!==workspace||!(numeric(row.bot_user_id)||row.bot_user_id===null)||!['legacy','native'].includes(row.kind)||!['empty','disabled','enabled','revoked'].includes(row.status)||!['polling','webhook'].includes(row.mode)||!Number.isSafeInteger(row.generation)||row.generation<0||typeof row.editable!=='boolean'||typeof row.identity_verified!=='boolean'||row.live_accepted!==false)deny();
  seen.add(row.id);return {id:row.id,workspace_id:workspace,bot_user_id:row.bot_user_id,kind:row.kind,generation:row.generation,status:row.status,mode:row.mode,editable:row.editable,identity_verified:row.identity_verified,live_accepted:false};
 });
 return {workspace_id:workspace,runtime_available:value.runtime_available,can_manage:value.can_manage,can_pair:value.can_pair,connections};
}
export function telegramTeam(value){
 if(!obj(value)||!Array.isArray(value.peers)||value.peers.length>100||!Array.isArray(value.pairings)||value.pairings.length>10)deny();
 const peers=value.peers.map(r=>{
  if(!obj(r)||!uuid(r.id)||!uuid(r.user_id)||!numeric(r.telegram_user_id)||!Number.isSafeInteger(r.version)||r.version<0||!['enabled','allow_chat','allow_reports'].every(k=>typeof r[k]==='boolean'))deny();
  return {id:r.id,user_id:r.user_id,telegram_user_id:r.telegram_user_id,version:r.version,enabled:r.enabled,allow_chat:r.allow_chat,allow_reports:r.allow_reports};
 });
 const pairings=value.pairings.map(r=>{
  if(!obj(r)||!uuid(r.id)||!['pending','observed','confirmed','revoked'].includes(r.status)||!numeric(r.expected_user_id)||!(r.observed_user_id===null||numeric(r.observed_user_id))||typeof r.expired!=='boolean'||typeof r.expires_at!=='string'||!Number.isFinite(Date.parse(r.expires_at)))deny();
  return {id:r.id,status:r.status,expected_user_id:r.expected_user_id,observed_user_id:r.observed_user_id,expired:r.expired,expires_at:r.expires_at};
 });return {peers,pairings};
}
export function pairingCommand(value){
 if(!obj(value)||!uuid(value.id)||typeof value.command!=='string'||!/^\/start pao_[A-Za-z0-9_-]{32}$/.test(value.command)||value.granted!==false||!Number.isFinite(Date.parse(value.expires_at)))deny();
 return value.command;
}
export function telegramError(code){
 if(code==='telegram_binding_brain_immutable')return 'Không thể đổi kho tri thức của liên kết đã có lịch sử. Giữ kho ban đầu hoặc dùng bot/kết nối khác cho kho mới; không sửa lịch sử để vượt kiểm tra.';
 if(code==='telegram_pairing_confirmation_required')return 'Danh tính chưa được xác nhận ở phiên bản khóa hiện tại. Nhân viên cần tạo mã mới, gửi tới đúng bot và xác nhận lại trong PAO trước khi quản trị viên cấp quyền.';
 if(code==='telegram_store_generation_stale'||code==='telegram_grant_version_conflict')return 'Cấu hình hoặc quyền đã đổi. Đọc lại Telegram, kiểm tra phiên bản mới rồi xác nhận ý định mới; không ghi đè dữ liệu cũ.';
 if(code==='telegram_runtime_encryption_unavailable')return 'Máy chủ chưa sẵn sàng mã hóa khóa. Token chưa được lưu; nhờ quản trị hệ thống kiểm tra khóa mã hóa theo quy trình phục hồi, không tự thay khóa hoặc gửi token qua chat.';
 const known={telegram_runtime_disabled:'Máy chủ chưa bật vận hành Telegram theo doanh nghiệp. Cấu hình không được kích hoạt; nhờ quản trị hệ thống kiểm tra trước khi thử lại.',telegram_runtime_legacy_conflict:'Bot dùng chung đang bật. Không thể bật song song kết nối theo doanh nghiệp; nhờ quản trị viên chuyển đổi an toàn.',telegram_runtime_bot_busy:'Bot đang xử lý một lượt khác. Chờ lượt kết thúc rồi đọc lại trạng thái; chưa tự gửi lại thao tác.',telegram_identity_claimed:'Bot đã được đăng ký. Kiểm tra doanh nghiệp và bot hiện có; không chuyển quyền hoặc nhập lại khóa để vượt kiểm tra.',telegram_pairing_not_confirmable:'Chưa thể xác nhận liên kết: mã có thể hết hạn, chưa nhận từ đúng Telegram ID hoặc cấu hình đã đổi. Đọc lại, kiểm tra ID rồi tạo mã mới nếu cần.',telegram_transport_mode_conflict:'Chế độ nhận tin tại Telegram không khớp PAO. Tắt kết nối, xác nhận đổi chế độ rồi kiểm tra lại; không tự xóa webhook.',telegram_webhook_https_required:'Máy chủ chưa có địa chỉ HTTPS webhook hợp lệ. Dùng lấy tin định kỳ khi chạy local; nhờ quản trị hệ thống cấu hình HTTPS trước khi dùng webhook.',telegram_transport_change_uncertain:'Telegram chưa xác nhận kết quả đổi chế độ. Kết nối vẫn tắt; đọc lại và kiểm tra với quản trị viên, không tự gửi lại.',telegram_setup_owner_required:'Chỉ người quản trị đã tạo kết nối mới được đổi khóa/cấu hình bot này. Quản trị viên khác chỉ cấp quyền đội ngũ trong doanh nghiệp.',telegram_team_permission_denied:'Bạn không có quyền thực hiện thao tác Telegram trong doanh nghiệp này. Nhờ chủ doanh nghiệp kiểm tra thành viên; quản trị nhóm Telegram không thay thế quyền PAO.'};
 return known[code]||'Chưa xác nhận được kết quả. Không tự gửi lại: đọc lại trạng thái để đối chiếu, kiểm tra đúng doanh nghiệp và quyền hiện tại. Không gửi token hoặc mã liên kết qua hội thoại hỗ trợ.';
}
export const telegramState=code=>({empty:'Chưa lưu khóa',disabled:'Đang tắt',enabled:'Đã bật xử lý',revoked:'Đã thu hồi',pending:'Chờ gửi mã từ Telegram',observed:'Đã nhận từ đúng ID; chờ bạn xác nhận',confirmed:'Đã xác nhận danh tính; quyền do quản trị viên cấp',polling:'Lấy tin định kỳ',webhook:'Nhận tin qua HTTPS'}[code]||'Chưa xác minh');
