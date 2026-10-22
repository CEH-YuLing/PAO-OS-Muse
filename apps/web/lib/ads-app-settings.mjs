export function appStatus(value,workspace,provider){
 if(!value||typeof value!=='object'||Array.isArray(value)||value.workspace_id!==workspace||value.provider!==provider||!['managed','byo'].includes(value.mode)||!Number.isSafeInteger(value.revision)||value.revision<0)throw new Error('ads_app_response_invalid');
 for(const key of ['explicit_selection','secret_present','developer_token_present','platform_enabled','configured','external_verified','reconnect_required'])if(typeof value[key]!=='boolean')throw new Error('ads_app_response_invalid');
 for(const key of ['client_id','api_version','redirect_uri','login_customer_id'])if(typeof value[key]!=='string'||value[key].length>512)throw new Error('ads_app_response_invalid');
 const u=new URL(value.redirect_uri),path='/v1/integrations/'+(provider==='meta'?'meta':'google-ads')+'/callback';
 if(u.username||u.password||u.search||u.hash||u.pathname!==path||!(u.protocol==='https:'||u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname)))throw new Error('ads_app_response_invalid');
 return Object.fromEntries(['workspace_id','provider','mode','revision','explicit_selection','client_id','api_version','redirect_uri','secret_present','developer_token_present','login_customer_id','platform_enabled','configured','external_verified','reconnect_required'].map(k=>[k,value[k]]));
}
export function appPayload(status,form){
 if(!status||!['managed','byo'].includes(form.mode))throw new Error('ads_app_invalid_input');
 const body={mode:form.mode,expected_revision:status.revision,consent:true};
 if(form.mode==='managed')return body;
 if(!(status.provider==='meta'?/^\d{1,64}$/:/^[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/).test(form.clientId)||!/^[-A-Za-z0-9._~+/]{8,512}$/.test(form.secret)||!(status.provider==='meta'?/^v\d+\.\d+$/:/^v\d+$/).test(form.apiVersion))throw new Error('ads_app_invalid_input');
 Object.assign(body,{client_id:form.clientId,client_secret:form.secret,api_version:form.apiVersion});
 if(status.provider==='google'){
  if(form.developerToken&&!/^[-A-Za-z0-9._~+/]{8,512}$/.test(form.developerToken)||form.loginId&&!/^\d{10}$/.test(form.loginId))throw new Error('ads_app_invalid_input');
  Object.assign(body,{login_customer_id:form.loginId});if(form.developerToken)body.developer_token=form.developerToken;
 }
 return body;
}
export function appError(code){
 if(code==='ads_app_revision_conflict')return 'Cấu hình đã đổi ở phiên khác. Đọc lại trước khi nhập và xác nhận mới; không tự gửi lại.';
 if(code==='ads_app_invalid_input'||code==='ads_app_secret_required')return 'Thông tin chưa hợp lệ. Kiểm tra App/Client ID, phiên bản API và nhập khóa mới đúng trường; không dán token người dùng hoặc gửi khóa qua chat.';
 if(code==='ads_app_manager_required')return 'Chỉ chủ doanh nghiệp hoặc quản trị viên của doanh nghiệp này được cấu hình ứng dụng.';
 if(code==='ads_app_binding_changed')return 'Ứng dụng hoặc khóa đã thay đổi. Kết nối OAuth lại rồi cấp quyền theo phiên bản mới; công việc cũ không tự được chạy tiếp.';
 return 'Chưa xác nhận được kết quả. Đọc lại cấu hình để đối chiếu; máy chủ có thể đã lưu. Không tự gửi lại hoặc nhập lại khóa mù. Liên hệ quản trị viên nếu chưa đọc được.';
}
