import {validateSettingsStatus} from './settings-status.mjs';
import {resourceErrorHelp} from './resource-quota.mjs';
export const modelHelp={
 openai:{name:'OpenAI',url:'https://developers.openai.com/api/reference/overview',text:'Dùng khóa API của dự án có quyền đọc mô hình và gọi mô hình cần dùng. Không dùng khóa quản trị. API key khác App Secret/OAuth. Danh mục mô hình không chứng minh suy luận AI hoặc hạn mức còn lại.'},
 anthropic:{name:'Anthropic',url:'https://platform.claude.com/docs/en/manage-claude/authentication',text:'Dùng API key dành riêng cho một workspace Claude. PAO chưa có trường anthropic-workspace-id cho key đa workspace, Workload Identity hoặc đám mây IAM. Backend giữ anthropic-phiên bản 2023-06-01; không nhập phiên bản vào ô key.'},
 gemini:{name:'Google Gemini',url:'https://ai.google.dev/gemini-api/docs/api-key',text:'Tạo API key trong Google AI Studio cho đúng Google Cloud project; giới hạn key theo Gemini API và môi trường máy chủ. PAO dùng x-goog-api-key, không đưa key vào URL. Không dùng service-account JSON hay Vertex AI IAM tại biểu mẫu này.'},
 openrouter:{name:'OpenRouter',url:'https://openrouter.ai/docs/api_reference/authentication',text:'Dùng API key OpenRouter với credit limit phù hợp. PAO dùng Bearer ở backend; chỉ dán giá trị key, không dán chữ Bearer. Danh mục không chứng minh quyền gọi từng mô hình, credit còn lại hay hóa đơn thực tế.'},
};
export function providerRows(value){validateSettingsStatus('providers',value);return value}
export function modelKeyState(row,draft=''){
 const hint=/^••••([A-Za-z0-9_-]{4})$/.exec(row.key_hint||'');
 return {label:draft?'Đã nhập · chưa lưu':row.configured?'Đã lưu khóa':'Chưa lưu khóa',
  masked:row.configured?'••••'+(hint?hint[1]:'••••'):''};
}
export function modelSaveConsent(name,enterprise){
 return `Lưu cấu hình ${name} cho ${enterprise}? PAO sẽ lưu khóa và gọi nhà cung cấp để tải danh mục mô hình. Chưa chạy suy luận AI hoặc cấp quyền công cụ; gói API tính phí riêng với thuê bao Client.`;
}
export function cleanModelKey(value){
 const key=value.trim();if(key.length<12||key.length>4096||/[\s\x00-\x1f\x7f"']/.test(key))throw new Error('model_key_invalid');return key;
}
export function modelIds(value,secret=''){
 if(!Array.isArray(value)||value.length>500||!value.every(x=>typeof x==='string'&&x.length>0&&x.length<=160&&!/[\s\x00-\x1f\x7f]/.test(x)&&(!secret||!x.includes(secret))))throw new Error('model_response_invalid');
 return [...new Set(value)];
}
export function modelRequest(provider,action,workspace,body,nonce){
 if(!modelHelp[provider]||!workspace)throw new Error('model_scope_invalid');
 const metadata=['connect','catalogue','select'].includes(action);
 if(metadata&&!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(nonce||''))throw new Error('model_nonce_invalid');
 const base=`/v1/model-providers/${provider}`,query=`?workspace_id=${encodeURIComponent(workspace)}`;
 const path=action==='connect'?base+'/connect':action==='select'?base+'/model':action==='catalogue'?base+'/models'+query:action==='default'?base+'/default'+query:action==='probe'?base+'/test'+query:action==='disconnect'?base+query:null;
 if(!path)throw new Error('model_action_invalid');
 return {path,method:action==='catalogue'?'GET':action==='disconnect'?'DELETE':action==='select'?'PUT':'POST',
   headers:{...(metadata?{'Idempotency-Key':nonce}:{}),...(body?{'Content-Type':'application/json'}:{})},
   ...(body?{body:JSON.stringify({...body,workspace_id:workspace})}:{})};
}
export function modelSettingsError(code){
 if(code==='model_key_invalid')return 'Nhập API key nguyên bản dài 12–4096 ký tự, không dấu ngoặc kép, khoảng trắng bên trong hoặc chữ Bearer. Khóa trong biểu mẫu đã được xóa.';
 if(code==='model_probe_requires_explicit_grant_run')return 'doanh nghiệp đã đăng ký quyền mô hình: không dùng kiểm tra thử cũ. Dùng quyền mô hình đã kích hoạt và lượt xử lý đúng phạm vi ở phần Quyền dùng mô hình; không cấp quyền công cụ.';
 if(['model_metadata_authority_changed','model_probe_authority_changed'].includes(code))return 'Quyền/tài khoản đã thay đổi. Đọc lại trạng thái và quyền thành viên; không tự gửi lại tác vụ.';
 if(['model_metadata_source_changed','tenant_metadata_replay_denied'].includes(code))return 'Nguồn kết nối đã đổi hoặc yêu cầu đã dùng. Đọc lại trạng thái trước thao tác mới; không ghi đè hay gửi lại yêu cầu cũ.';
 if(code.startsWith('tenant_')&&code.includes('exhausted'))return resourceErrorHelp(code);
 return 'Không xác nhận được kết quả. máy chủ có thể đã xử lý: bấm Đọc lại trạng thái mô hình để đối chiếu trước một ý định mới. Không tự gửi lại; xem quyền/key/hóa đơn tại nhà cung cấp nếu cần.';
}
