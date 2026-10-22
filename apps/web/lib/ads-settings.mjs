export const adsHelp={
 meta:{name:'Meta Ads',base:'/v1/integrations/meta',url:'https://developers.facebook.com/docs/marketing-api/overview/authorization/',text:'PAO yêu cầu ads_read ở luồng chỉ đọc, không ads_management. Cần tài khoản Facebook có quyền tài sản quảng cáo và ứng dụng cho phép đăng nhập; trạng thái đã kết nối không chứng minh xét duyệt ứng dụng hoặc quyền mọi tài khoản. App ID/Secret thuộc ứng dụng PAO hoặc ứng dụng riêng SME đã chọn, không phải token người dùng. Tài liệu Meta vẫn bị rate-limit khi đối chiếu16/10; phải kiểm tra App/use-case/thẩm định trước kết nối thật.'},
 google:{name:'Google Ads',base:'/v1/integrations/google-ads',url:'https://developers.google.com/google-ads/api/docs/oauth/access-model',text:'Google dùng phạm vi https://www.googleapis.com/auth/adwords cho cả đọc và ghi. Nên cấp vai trò chỉ đọc tại Google Ads; PAO tiếp tục kiểm quyền được cấp/tài khoản/công việc và không gọi mutate ở luồng này. Client ID/khóa bí mật thuộc đám mây project đã bật Google Ads API và được duyệt API access; không nhập Gemini API key. login-customer-id là manager root, không customer đích. Backend giữ v25; không tự nâng phiên bản.'},
};
const object=x=>Boolean(x&&typeof x==='object'&&!Array.isArray(x));
export function adsStatus(provider,value){
 if(!adsHelp[provider]||!object(value)||typeof value.configured!=='boolean'||!['connected','disconnected','expired'].includes(value.status)||!Array.isArray(value.scopes)||value.scopes.length>100||!value.scopes.every(s=>typeof s==='string'&&s.length<=200))throw new Error('ads_response_invalid');
 if(provider==='meta'&&((value.remote_user_id!=null&&(typeof value.remote_user_id!=='string'||!/^\d{1,64}$/.test(value.remote_user_id)))||(value.expires_at!=null&&(typeof value.expires_at!=='string'||!Number.isFinite(Date.parse(value.expires_at))))))throw new Error('ads_response_invalid');
 return value;
}
export function adsOAuthUrl(provider,value,origin){
 try{
  if(!adsHelp[provider]||!object(value)||typeof value.authorization_url!=='string'||value.authorization_url.length>4096)throw new Error();
  const url=new URL(value.authorization_url),p=url.searchParams;
  if(url.protocol!=='https:'||url.username||url.password||url.hash||url.port||p.get('response_type')!=='code'||!p.get('client_id')||!/^[-_a-zA-Z0-9]{32,128}$/.test(p.get('state')||''))throw new Error();
  const redirect=new URL(p.get('redirect_uri'));
  if(redirect.origin!==origin||redirect.pathname!==adsHelp[provider].base+'/callback'||redirect.username||redirect.password||redirect.search||redirect.hash)throw new Error();
  if(!(redirect.protocol==='https:'||redirect.protocol==='http:'&&['localhost','127.0.0.1'].includes(redirect.hostname)))throw new Error();
  if(provider==='meta'&&(url.hostname!=='www.facebook.com'||!/^\/v\d+\.\d+\/dialog\/oauth$/.test(url.pathname)||p.get('scope')!=='ads_read'))throw new Error();
  if(provider==='google'&&(url.hostname!=='accounts.google.com'||url.pathname!=='/o/oauth2/v2/auth'||p.get('scope')!=='https://www.googleapis.com/auth/adwords'||p.get('access_type')!=='offline'||p.get('prompt')!=='consent'))throw new Error();
  const allowed=provider==='meta'?['client_id','redirect_uri','state','scope','response_type']:['client_id','redirect_uri','state','scope','response_type','access_type','prompt','include_granted_scopes'];
  if([...p.keys()].some(key=>p.getAll(key).length!==1||!allowed.includes(key)))throw new Error();
  if(!(provider==='meta'?/^\d{1,64}$/:/^[a-zA-Z0-9_-]{1,200}\.apps\.googleusercontent\.com$/).test(p.get('client_id')))throw new Error();
  return url.href;
 }catch{throw new Error('ads_oauth_url_invalid')}
}
export function adsAccounts(provider,value){
 const data=provider==='meta'?value?.rows:value;
 if(provider==='meta'&&(!object(value)||typeof value.has_more!=='boolean'))throw new Error('ads_response_invalid');
 if(!adsHelp[provider]||!Array.isArray(data)||data.length>(provider==='meta'?50:5000))throw new Error('ads_response_invalid');
 const seen=new Set();return data.map(row=>{
  if(!object(row)||typeof row.id!=='string'||!(provider==='meta'?/^act_\d{1,32}$/:/^\d{10}$/).test(row.id)||seen.has(row.id)||(row.name!=null&&(typeof row.name!=='string'||row.name.length>500))||(row.currency!=null&&(typeof row.currency!=='string'||row.currency.length>16)))throw new Error('ads_response_invalid');
  seen.add(row.id);return {id:row.id,name:row.name||row.id,currency:row.currency||''};
 });
}
export function adsJobs(value){
 if(!Array.isArray(value)||value.length>20||!value.every(row=>object(row)&&typeof row.id==='string'&&/^[0-9a-f-]{36}$/i.test(row.id)&&['accounts','historical'].includes(row.kind)&&['queued','running','completed','failed','cancelled','unknown'].includes(row.status)&&Number.isSafeInteger(row.row_count)&&row.row_count>=0))throw new Error('ads_response_invalid');
 return value.map(row=>({id:row.id,kind:row.kind,status:row.status,row_count:row.row_count}));
}
export function adsSettingsError(code){
 if(code==='ads_popup_blocked')return 'Trình duyệt chặn popup. Cho phép cửa sổ bật lên rồi xác nhận lại; chưa gửi OAuth start.';
 if(code==='ads_oauth_url_invalid')return 'Không mở URL OAuth: máy chủ/phạm vi/địa chỉ nhận kết quả/state không đúng profile chỉ đọc. Đọc lại trạng thái, kiểm tra địa chỉ nhận kết quả đúng địa chỉ PAO; không tự chuyển sang URL khác. Phiên máy chủ đã tạo có thể cần chờ hết hạn.';
 if(code==='ads_connection_grant_denied')return 'Nguồn đã đăng ký quyền doanh nghiệp: danh mục cũ bị từ chối. Dùng Quyền dùng Meta/Google Ads và Đọc Ads bằng quyền đã cấp bên dưới; không chuyển dự phòng hoặc tìm danh mục toàn bộ tài khoản.';
 if(code==='meta_app_restart_required')return 'Meta App vận hành chưa nạp cấu hình mới. Nhờ quản trị viên kiểm tra/nạp lại API và tiến trình xử lý; không nhập lại App Secret hoặc tự restart từ biểu mẫu này.';
 if(['meta_not_configured','google_ads_not_configured'].includes(code))return 'Ứng dụng đã chọn hoặc chốt nền tảng chưa sẵn sàng. Đọc lại cấu hình ứng dụng của doanh nghiệp; nhờ quản trị viên kiểm tra App/Cloud project/địa chỉ nhận kết quả, không tự chuyển dự phòng.';
 if(code==='ads_app_binding_changed')return 'Ứng dụng/khóa đã đổi. Kết nối OAuth lại đúng doanh nghiệp rồi cấp quyền phiên bản mới; công việc cũ không tự sống lại.';
 if(code==='ads_oauth_origin_mismatch')return 'Địa chỉ PAO đang mở khác địa chỉ nhận kết quả do máy chủ cấu hình. Dùng đúng hostname/cổng hoặc nhờ quản trị máy chủ sửa; không mở URL OAuth khác để bỏ kiểm tra.';
 return 'Không xác nhận được kết quả. máy chủ có thể đã xử lý; bấm Đọc lại trạng thái Ads để đối chiếu. lần đọc GET khi yêu cầu cũ còn chạy chưa chứng minh kết quả cuối. Không tự gửi lại; xem quyền tài khoản/App/đám mây project, không dán khóa bí mật vào chat.';
}
