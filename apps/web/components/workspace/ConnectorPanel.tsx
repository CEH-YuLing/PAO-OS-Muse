"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {settingsLabel} from '@/lib/settings-vi';
import {usePao} from '@/lib/PaoRuntimeContext';
import {mcpEndpoint,mcpToken,mcpRows,mcpArguments,mcpDiscoveryRequest,mcpAudit,mcpSettingsError,type McpConnection} from '@/lib/mcp-settings.mjs';
import './mcp-settings.css';
type Action='create'|'discover'|'rotate'|'disconnect'|'permissions'|'audit'|'call';
export default function ConnectorPanel(){
 const {apiRaw,activeWorkspace:member}=usePao(),workspace=member?.id||'',manage=member?.role==='owner'||member?.role==='admin';
 const epoch=useRef(0),lock=useRef(false),abort=useRef<AbortController|null>(null);
 const [rows,setRows]=useState<McpConnection[]>([]),[available,setAvailable]=useState(false),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false);
 const [url,setUrl]=useState(''),[credential,setCredential]=useState(''),[selected,setSelected]=useState(''),[toolId,setToolId]=useState('');
 const [ack,setAck]=useState(false),[discoverAck,setDiscoverAck]=useState(false),[rotateAck,setRotateAck]=useState(false),[removeAck,setRemoveAck]=useState(false),[grantAck,setGrantAck]=useState(false),[callAck,setCallAck]=useState(false);
 const [argumentsJson,setArguments]=useState('{}'),[runId,setRunId]=useState(''),[requestKey,setRequestKey]=useState(''),[error,setError]=useState(''),[result,setResult]=useState('');
 const connection=rows.find(row=>row.id===selected),tool=connection?.tools.find(row=>row.id===toolId);
 const clear=useCallback(()=>{setCredential('');setUrl('');setAck(false);setDiscoverAck(false);setRotateAck(false);setRemoveAck(false);setGrantAck(false);setCallAck(false);setArguments('{}');setRunId('');setRequestKey('')},[]);
 const read=useCallback(async(ticket:number,controller:AbortController)=>{
  const init={signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])};
  const state=await (await apiRaw('/v1/connectors/templates?workspace_id='+workspace,init)).json();
  if(typeof state.available!=='boolean')throw new Error('mcp_response_invalid');
  const data=state.available?mcpRows(await (await apiRaw('/v1/connectors/connections?workspace_id='+workspace,init)).json(),workspace):[];
  if(ticket!==epoch.current||controller.signal.aborted)return false;
  setAvailable(state.available);setRows(data);setConfirmed(true);return true;
 },[apiRaw,workspace]);
 const refresh=useCallback(async()=>{
  if(lock.current||!workspace)return;lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  clear();setSelected('');setToolId('');setRows([]);setConfirmed(false);setBusy(true);setError('');setResult('');
  try{await read(ticket,controller)}catch(reason){if(ticket===epoch.current)setError(mcpSettingsError((reason as Error).message))}
  finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[workspace,clear,read]);
 useEffect(()=>{const currentEpoch=epoch,currentAbort=abort,currentLock=lock;void refresh();return()=>{currentEpoch.current++;currentAbort.current?.abort();currentLock.current=false}},[refresh]);
 useEffect(()=>{const hide=()=>{if(document.hidden)clear()},leave=()=>clear();document.addEventListener('visibilitychange',hide);window.addEventListener('pagehide',leave);return()=>{document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',leave)}},[clear]);
 async function work(action:Action){
  if(lock.current||!confirmed||!available||!manage)return;
  if(action==='create'&&!ack||action==='discover'&&!discoverAck||action==='rotate'&&!rotateAck||action==='disconnect'&&!removeAck||action==='permissions'&&!grantAck||action==='call'&&!callAck)return;
  if(action!=='create'&&!connection||['permissions','call'].includes(action)&&!tool)return;
  if(action==='disconnect'&&!window.confirm('Ngắt MCP trong '+member?.name+'? PAO xóa token và quyền đọc; token tại máy chủ không tự bị thu hồi.'))return;
  let path='/v1/connectors/connections',method='POST',body:unknown,headers:Record<string,string>={'Content-Type':'application/json'},secret='';
  try{
   if(action==='create'){secret=mcpToken(credential);body={workspace_id:workspace,endpoint:mcpEndpoint(url),...(secret?{token:secret}:{}),readonly_credentials_ack:true}}
   else if(connection){
    path+='/'+connection.id;
    if(action==='discover'){const request=mcpDiscoveryRequest(connection.id,connection.version,crypto.randomUUID());path=request.path;headers=request.headers;body={version:connection.version}}
    if(action==='rotate'){secret=mcpToken(credential,true);path+='/credential';method='PUT';body={version:connection.version,token:secret}}
    if(action==='disconnect'){path+='/disconnect';body={version:connection.version}}
    if(action==='audit'){path+='/audit';method='GET'}
    if(action==='permissions'&&tool){path+='/permissions';method='PUT';body={version:connection.version,tool_id:tool.id,schema_hash:tool.hash,bound_arguments:mcpArguments(argumentsJson),readonly_server_ack:true}}
    if(action==='call'&&tool){if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(runId)||!/^[a-zA-Z0-9_-]{1,64}$/.test(requestKey))throw new Error('mcp_request_invalid');path+='/calls';body={run_id:runId,tool_id:tool.id,request_key:requestKey}}
   }
  }catch(reason){clear();setError(mcpSettingsError((reason as Error).message));return}
  lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  clear();setBusy(true);setError('');setResult('');
  try{
   const response=await apiRaw(path,{method,headers,...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.any([controller.signal,AbortSignal.timeout(60000)])});
   const value=await response.json();let message='';
   if(action==='audit')message=JSON.stringify(mcpAudit(value),null,2);
   else if(action==='call'){
    if(typeof value.id!=='string'||!/^[0-9a-f-]{36}$/i.test(value.id)||!['queued','running','completed','failed','cancelled','unknown'].includes(value.status))throw new Error('mcp_response_invalid');
    message=JSON.stringify({id:value.id,status:value.status},null,2)+'\nXem kết quả tác vụ trong lượt xử lý; đang chờ không chứng minh máy chủ đã trả kết quả.';
   }else{
    mcpRows([value],workspace);if(action!=='create'&&value.id!==connection?.id)throw new Error('mcp_response_invalid');
    message=action==='create'?'Đã tạo bản nháp; chưa gọi máy chủ dịch vụ và chưa cấp quyền.':action==='disconnect'?'Đã ngắt bản lưu PAO, xóa phần lưu token và quyền đọc. Hãy thu hồi/đổi khóa token tại MCP máy chủ riêng; quyền được cấp/công việc cũ không tự sống lại.':action==='rotate'?'Đã đổi token; trạng thái bản nháp, quyền đọc cũ đã bỏ. Cần tìm danh mục/thẩm định/quyền được cấp mới.':action==='permissions'?'Đã lưu quyền đọc với cấu trúc dữ liệu/tham số đã duyệt. Vẫn cần kỹ năng công bố, quyền được cấp và lượt xử lý đúng phạm vi; không tự xếp hàng công cụ.':'Đã xác nhận phiên bản/cấu trúc dữ liệu mới; tìm danh mục không cấp quyền công cụ hoặc nghiệm thu máy chủ thật.';
   }
   if(ticket!==epoch.current||controller.signal.aborted)return;
   if(!await read(ticket,controller))return;
   if(action!=='audit'&&action!=='call'){setSelected(value.id);setToolId('')}
   setResult(message);
  }catch(reason){if(ticket===epoch.current){clear();setRows([]);setSelected('');setToolId('');setConfirmed(false);setError(mcpSettingsError((reason as Error).message))}}
  finally{secret='';if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 }
 return <section aria-label="Kết nối công cụ chỉ đọc" className="mcp-settings">
  <h2>Kết nối MCP chỉ đọc</h2><p>doanh nghiệp: {member?.name}. Mẫu cấu hình chưa phải kết nối. Chưa nghiệm thu máy chủ dịch vụ thật. Chạy chương trình trên máy, cài mã mở rộng và thao tác ghi đều tắt.</p>
  <p>Profile PAO: HTTPS Streamable HTTP, MCP 2025-11-25, JSON/SSE có giới hạn dung lượng và cấu trúc dữ liệu đóng. Không OAuth login/refresh, giao thức khác hay MCP máy chủ trên IP/localhost. Không dùng khóa bí mật ứng dụng thay khóa truy cập Bearer.</p>
  <details><summary>Chuẩn bị kết nối MCP</summary><p>Lấy địa chỉ dịch vụ và token chỉ đọc tại nhà cung cấp máy chủ, chọn đúng tài khoản/dữ liệu doanh nghiệp. Không dán token vào URL hoặc chat. Cấu hình quyền hạn ở máy chủ trước; readOnlyHint chỉ là khai báo, không chứng minh máy chủ không ghi dữ liệu. PAO vẫn kiểm cấu trúc dữ liệu, tham số đã giới hạn, kỹ năng công bố, quyền được cấp và lượt xử lý đúng phạm vi.</p><p>tìm danh mục chỉ sau xác nhận: initialize và tools/list có thể tiêu tài nguyên máy chủ. danh mục/nhật ký PAO không gọi máy chủ. Token hết hạn: đổi khóa ở máy chủ rồi nhập token mới bên dưới; không tự gia hạn.</p><a href="https://modelcontextprotocol.io/specification/2025-11-25/basic/transports" target="_blank" rel="noopener noreferrer">Giao thức vận chuyển MCP 2025-11-25</a>{' · '}<a href="https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization" target="_blank" rel="noopener noreferrer">Xác thực MCP</a>{' · '}<a href="https://modelcontextprotocol.io/specification/2025-11-25/server/tools" target="_blank" rel="noopener noreferrer">Khai báo công cụ và xác nhận</a></details>
  <button type="button" disabled={busy} onClick={()=>void refresh()}>Đọc lại danh mục trên PAO</button>
  {!confirmed&&<p>Chưa có trạng thái được xác nhận; thao tác thay đổi bị khóa. Đọc lại bỏ token/bản nháp, không gửi lại thao tác cũ.</p>}
  {confirmed&&!available&&<p>Kết nối đang tắt. danh mục chỉ mô tả cấu hình; không gọi máy chủ.</p>}
  {error&&<p role="alert">{error}</p>}
  {manage?<fieldset disabled={!confirmed||!available||busy}><legend>Tạo kết nối do người quản trị chọn</legend>
   <label>Địa chỉ HTTPS máy chủ MCP<input aria-label="Địa chỉ HTTPS máy chủ MCP" value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://server.example/mcp" autoComplete="off"/></label>
   <label>Khóa truy cập Bearer (tùy chọn)<input aria-label="Khóa truy cập MCP" type="password" value={credential} onChange={e=>setCredential(e.target.value)} autoComplete="new-password"/></label>
   <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/> Tôi chọn máy chủ này và khóa truy cập chỉ có quyền đọc.</label>
   <button type="button" disabled={!ack||!url} onClick={()=>void work('create')}>Tạo kết nối bản nháp</button>
  </fieldset>:<p>Chỉ chủ doanh nghiệp/quản trị viên quản lý kết nối riêng của mình. Nhân viên dùng quyền MCP được cấp bên dưới; không xem hay nhập token.</p>}
  <label>Kết nối<select aria-label="Kết nối MCP" disabled={busy||!confirmed} value={selected} onChange={e=>{clear();setResult('');setError('');setSelected(e.target.value);setToolId('')}}><option value="">Chọn kết nối</option>{rows.map(row=><option key={row.id} value={row.id}>{row.endpoint} — {settingsLabel(row.status)}</option>)}</select></label>
  {connection&&manage&&<fieldset disabled={!confirmed||!available||busy}><legend>Tìm danh mục và quyền đọc</legend>
   <p>phiên bản {connection.version} · {connection.circuit_open?'Đang tạm ngắt do lỗi':'Không tạm ngắt'} · token {connection.secret_present?'đã lưu':'không có'}. đã kết nối chỉ xác nhận tìm danh mục, không chứng minh công cụ đã kiểm tra thử. danh mục native tối đa 20 kết nối của chính người quản lý, không phải toàn bộ doanh nghiệp.</p>
   <label><input aria-label="Đồng ý tìm danh mục MCP" type="checkbox" checked={discoverAck} onChange={e=>setDiscoverAck(e.target.checked)}/>Tôi cho phép đọc thông tin mô tả/cấu trúc dữ liệu từ máy chủ; không cấp quyền gọi công cụ.</label>
   <button type="button" disabled={!discoverAck||connection.status==='revoked'||connection.circuit_open} onClick={()=>void work('discover')}>Kiểm tra và tìm danh mục công cụ</button>
   <label><input aria-label="Đồng ý ngắt MCP" type="checkbox" checked={removeAck} onChange={e=>setRemoveAck(e.target.checked)}/>Ngắt bản lưu PAO, xóa phần lưu token/quyền và hủy các lượt gọi đang chờ hoặc đang chạy; không thu hồi token tại máy chủ.</label>
   <button type="button" disabled={!removeAck||connection.status==='revoked'} onClick={()=>void work('disconnect')}>Ngắt kết nối và xóa khóa</button>
   <button type="button" onClick={()=>void work('audit')}>Xem nhật ký cấu hình</button>
   <p>nhật ký chỉ hiển thị mã định danh/hành động, tối đa 100 sự kiện gần nhất; không phải toàn bộ lịch sử hay kiểm tra thử hiện tại.</p>
   {connection.status!=='revoked'&&<details><summary>Đổi khóa truy cập Bearer</summary><p>Dùng ô khóa truy cập phía trên để nhập khóa mới. đổi khóa tăng phiên bản, đưa về bản nháp và bỏ quyền đọc/lượt gọi cũ; không tự tìm danh mục hoặc cấp lại quyền được cấp.</p><label><input aria-label="Đồng ý đổi token MCP" type="checkbox" checked={rotateAck} onChange={e=>setRotateAck(e.target.checked)}/>Tôi muốn thay token của đúng kết nối này.</label><button type="button" disabled={!rotateAck||!credential} onClick={()=>void work('rotate')}>Đổi khóa truy cập MCP</button></details>}
   <label>Công cụ<select aria-label="Công cụ MCP" value={toolId} onChange={e=>{clear();setResult('');setToolId(e.target.value)}}><option value="">Chọn công cụ đã tìm được</option>{connection.tools.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
   {tool&&<><p>Mã công cụ: {tool.id}<br/>Mã băm cấu trúc: {tool.hash}</p><details><summary>Cấu trúc dữ liệu đầu vào/đầu ra</summary><pre>{JSON.stringify({input:tool.input_schema,output:tool.output_schema},null,2)}</pre></details>
    <label>Tham số JSON đã được quản trị viên giới hạn<textarea aria-label="Tham số công cụ MCP đã giới hạn" rows={4} value={argumentsJson} onChange={e=>{setArguments(e.target.value);setGrantAck(false);setCallAck(false)}}/></label>
    <label><input type="checkbox" checked={grantAck} onChange={e=>setGrantAck(e.target.checked)}/> Tôi đã kiểm tra máy chủ/công cụ và phạm vi tham số chỉ đọc.</label>
    <button type="button" disabled={!grantAck||connection.status!=='connected'} onClick={()=>void work('permissions')}>Duyệt quyền đọc với tham số giới hạn</button>
    <p>Thêm công cụ ID vào allowed_tools của kỹ năng, fixture/thẩm định/công bố phiên bản mới. doanh nghiệp đã đăng ký quyền được cấp phải dùng phần Chạy MCP bằng quyền đã cấp; biểu mẫu này không tự kích hoạt quyền được cấp, lượt xử lý hoặc gọi MCP từ LLM.</p>
    <label>Mã lượt Studio thuộc quyền của bạn<input aria-label="Mã lượt cha MCP" value={runId} onChange={e=>{setRunId(e.target.value);setCallAck(false)}}/></label>
    <label>Mã yêu cầu chống xử lý trùng<input aria-label="Mã yêu cầu MCP" value={requestKey} onChange={e=>{setRequestKey(e.target.value);setCallAck(false)}}/></label>
    <label><input aria-label="Đồng ý xếp hàng MCP cũ" type="checkbox" checked={callAck} onChange={e=>setCallAck(e.target.checked)}/>Tôi cho phép xếp hàng một lượt đọc qua Gateway; có thể dùng tài nguyên máy chủ.</label>
    <button type="button" disabled={!callAck||!runId||!requestKey||!connection.permissions.includes(tool.id)||connection.status!=='connected'} onClick={()=>void work('call')}>Xếp hàng lượt đọc đã được duyệt</button>
   </>}
  </fieldset>}
  {result&&<pre aria-label="Kết quả thao tác MCP" role="status">{result}</pre>}
  <p>Token chỉ ở bộ nhớ biểu mẫu, xóa khi bắt đầu thao tác, lỗi, đọc lại, đổi lựa chọn, rời trang/ẩn tab hoặc đổi doanh nghiệp/role; không lưu bộ nhớ trình duyệt. tìm danh mục mã một lần chỉ thuộc một ý định. phiên bản/đối chiếu phiên bản/SSRF và quyền do máy chủ quyết định; không tự gửi lại.</p>
 </section>;
}
