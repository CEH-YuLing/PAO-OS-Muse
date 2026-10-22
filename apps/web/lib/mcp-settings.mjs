import {resourceErrorHelp} from './resource-quota.mjs';
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,hash=/^[0-9a-f]{64}$/;
const object=x=>Boolean(x&&typeof x==='object'&&!Array.isArray(x));
export function mcpEndpoint(value){
 if(typeof value!=='string'||value.length>1000||/[^\x21-\x7e]/.test(value))throw new Error('mcp_endpoint_invalid');
 const match=/^https:\/\/([a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?)(?::443)?(\/[a-zA-Z0-9_/-]{0,200})$/.exec(value);
 if(!match||!match[1].includes('.')||match[1].includes('..')||match[2].includes('..')||/^\d+\.\d+\.\d+\.\d+$/.test(match[1]))throw new Error('mcp_endpoint_invalid');
 return 'https://'+match[1].toLowerCase()+match[2];
}
export function mcpToken(value,required=false){
 if(value===''&&!required)return '';
 if(typeof value!=='string'||value.length<12||value.length>2048||/[^\x21-\x7e]/.test(value)||/^Bearer/i.test(value))throw new Error('mcp_token_invalid');
 return value;
}
export function mcpRows(value,workspace){
 if(!uuid.test(workspace)||!Array.isArray(value)||value.length>20)throw new Error('mcp_response_invalid');
 const ids=new Set();
 for(const row of value){
  if(!object(row)||!uuid.test(row.id)||ids.has(row.id)||row.workspace_id!==workspace||!['draft','connected','revoked'].includes(row.status)||
    row.protocol!=='2025-11-25'||!Number.isSafeInteger(row.version)||row.version<1||typeof row.secret_present!=='boolean'||typeof row.circuit_open!=='boolean'||
    !(row.manifest_hash===null||hash.test(row.manifest_hash))||!Array.isArray(row.tools)||row.tools.length>32||!Array.isArray(row.permissions))throw new Error('mcp_response_invalid');
  try{if(mcpEndpoint(row.endpoint)!==row.endpoint)throw new Error()}catch{throw new Error('mcp_response_invalid')}
  const tools=new Set();for(const tool of row.tools){
   if(!object(tool)||typeof tool.name!=='string'||!/^[a-zA-Z][a-zA-Z0-9_-]{0,19}$/.test(tool.name)||
     tool.id!=='mcp.'+row.id.replaceAll('-','')+'.'+tool.name||tools.has(tool.id)||!hash.test(tool.hash)||!object(tool.input_schema)||!object(tool.output_schema))throw new Error('mcp_response_invalid');
   tools.add(tool.id);
  }
  if(new Set(row.permissions).size!==row.permissions.length||!row.permissions.every(id=>tools.has(id)))throw new Error('mcp_response_invalid');
  ids.add(row.id);
 }
 return value;
}
export function mcpArguments(value){
 try{if(new TextEncoder().encode(value).length>65536)throw new Error();const result=JSON.parse(value);if(!object(result))throw new Error();return result}catch{throw new Error('mcp_arguments_invalid')}
}
export function mcpDiscoveryRequest(id,version,nonce){
 if(!uuid.test(id)||!uuid.test(nonce)||!Number.isSafeInteger(version)||version<1)throw new Error('mcp_request_invalid');
 return {path:`/v1/connectors/connections/${id}/test`,method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':nonce},body:JSON.stringify({version})};
}
export function mcpAudit(value){
 if(!Array.isArray(value)||value.length>100||!value.every(row=>object(row)&&uuid.test(row.id)&&typeof row.action==='string'&&/^[a-z_]{1,64}$/.test(row.action)))throw new Error('mcp_response_invalid');
 return value.map(row=>({id:row.id,action:row.action}));
}
export function mcpSettingsError(code){
 if(code==='mcp_endpoint_invalid')return 'địa chỉ dịch vụ cần HTTPS tên miền công khai, cổng 443, đường dẫn đơn giản; không IP, user/password, query/token hoặc fragment. Máy chủ tiếp tục kiểm tra DNS/SSRF.';
 if(code==='mcp_token_invalid')return 'Chỉ dán giá trị bearer token 12–2048 ký tự ASCII, không khoảng trắng hay chữ Bearer. Token trong biểu mẫu đã xóa.';
 if(code==='mcp_arguments_invalid')return 'Tham số phải là JSON object tối đa 64 KiB. Máy chủ vẫn kiểm tra cấu trúc dữ liệu và quyền đọc; chưa gửi yêu cầu.';
 if(code==='mcp_request_invalid')return 'lượt xử lý ID phải là UUID; yêu cầu key gồm 1–64 chữ/số/gạch dưới/gạch ngang. Chưa gửi yêu cầu; bản nháp đã xóa.';
 if(code==='connector_auth_denied')return 'máy chủ từ chối xác thực. Đọc lại danh mục; kiểm tra token đúng MCP máy chủ/tài khoản doanh nghiệp, hạn dùng và phạm vi chỉ đọc. đổi khóa tại máy chủ rồi nhập token mới; PAO không tự OAuth/refresh hoặc gửi lại tự động.';
 if(code==='connector_circuit_open')return 'Circuit đang mở sau các lỗi tìm danh mục. Chờ cooldown và đọc lại danh mục; không tự tìm danh mục lại hoặc dùng doanh nghiệp khác để tránh giới hạn.';
 if(['connector_capabilities_unsupported','connector_protocol_invalid','connector_content_type'].includes(code))return 'máy chủ không đáp ứng profile MCP 2025-11-25 JSON/SSE/cấu trúc dữ liệu của PAO. Kiểm tra tài liệu máy chủ và đọc lại danh mục; không tự đổi giao thức, transport hoặc cài mã chương trình.';
 if(['connector_owner_required','connector_probe_authority_changed','connector_probe_brain_changed','connector_probe_scope_changed'].includes(code))return 'Quyền quản trị/doanh nghiệp/kho tri thức đã thay đổi. Tải lại quyền thành viên và danh mục; không dùng quyền chủ doanh nghiệp của doanh nghiệp khác hoặc tự gửi lại.';
 if(code.startsWith('tenant_')&&code.includes('exhausted'))return resourceErrorHelp(code)+' Đọc lại danh mục trước ý định mới; không tự gửi lại tìm danh mục.';
 if(code==='connector_revision_conflict'||code==='connector_probe_source_changed'||code==='tenant_metadata_replay_denied')return 'phiên bản/nguồn/yêu cầu đã thay đổi. Đọc lại danh mục rồi kiểm tra quyền, cấu trúc dữ liệu và tham số; không ghi đè hoặc tự gửi lại.';
 return 'Không xác nhận được kết quả. Máy chủ có thể đã xử lý; hãy đọc lại danh mục để đối chiếu trước ý định mới. lần đọc GET khi yêu cầu cũ còn chạy chưa chứng minh kết quả cuối. Không tự gửi lại; token/bản nháp đã xóa.';
}
