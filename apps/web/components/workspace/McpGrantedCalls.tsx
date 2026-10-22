"use client";
import {useEffect,useRef,useState} from "react";
import {settingsError} from '@/lib/settings-vi';
import {usePao} from "@/lib/PaoRuntimeContext";

type Grant={grant_id:string;connection_id:string;expires_at:string;tools:{id:string;name:string;schema_hash:string}[]};
type Catalog={items:Grant[];has_more:boolean};
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function McpGrantedCalls(){
  const {api,activeWorkspace}=usePao(),workspace=activeWorkspace?.id||"",epoch=useRef(0);
  const [runId,setRunId]=useState(""),[catalog,setCatalog]=useState<Catalog|null>(null),[choice,setChoice]=useState("");
  const [key,setKey]=useState(""),[ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  useEffect(()=>{const scopeEpoch=epoch;scopeEpoch.current++;return()=>{scopeEpoch.current++}},[workspace,runId]);
  function selectRun(value:string){epoch.current++;setRunId(value);setCatalog(null);setChoice("");setKey("");setAck(false);setNotice("");setError("")}
  async function work(task:(ticket:number)=>Promise<void>){
    if(busy)return;const ticket=epoch.current;setBusy(true);setError("");setNotice("");
    try{await task(ticket)}catch(reason){if(ticket===epoch.current)setError((reason as Error).message)}
    finally{if(ticket===epoch.current)setBusy(false)}
  }
  const selected=catalog?.items.flatMap(grant=>grant.tools.map(tool=>({grant,tool,value:JSON.stringify([grant.grant_id,tool.id])}))).find(row=>row.value===choice);
  return <section className="pao-model-access" aria-label="Chạy MCP bằng quyền đã cấp">
    <h3>Dùng MCP bằng quyền đã cấp</h3>
    <p>Chọn lượt xử lý của chính bạn trong doanh nghiệp này. PAO lấy phạm vi nhãn hàng/kho tri thức từ lượt xử lý, không cho chọn tùy ý để vượt quyền. Cần kỹ năng đã công bố/thẩm định và quyền công cụ với tham số do người quản lý khóa.</p>
    <label>lượt xử lý ID<input aria-label="MCP granted lượt xử lý ID" value={runId} disabled={busy} onChange={event=>selectRun(event.target.value.trim())}/></label>
    <button type="button" disabled={busy||!UUID.test(runId)} onClick={()=>void work(async ticket=>{
      const rows=await api<Catalog>(`/v1/connectors/grants?workspace_id=${workspace}&run_id=${runId}`);
      if(ticket===epoch.current){setCatalog(rows);setChoice("");if(!rows.items.length)setNotice("Không có quyền MCP hợp lệ trong phạm vi của lượt xử lý này.")}
    })}>Tải quyền MCP của lượt xử lý</button>
    <label>Quyền và công cụ<select aria-label="Quyền MCP đã cấp" value={choice} disabled={busy||!catalog} onChange={event=>{setChoice(event.target.value);setAck(false);setKey("")}}>
      <option value="">Chọn quyền cụ thể…</option>{catalog?.items.flatMap(grant=>grant.tools.map(tool=>
        <option key={grant.grant_id+tool.id} value={JSON.stringify([grant.grant_id,tool.id])}>{tool.name} · quyền {grant.grant_id.slice(0,8)} · kết nối {grant.connection_id.slice(0,8)}</option>))}
    </select></label>
    {selected&&<p>Hết hạn {new Date(selected.grant.expires_at).toLocaleString("vi-VN")}. Thông tin quyền không xác nhận máy chủ đang hoạt động hoặc đã nghiệm thu thật.</p>}
    {catalog?.has_more&&<p>Danh sách đang phân trang; không thể hiện toàn bộ quyền.</p>}
    <label><input aria-label="Đồng ý chạy MCP chỉ đọc đã cấp" type="checkbox" checked={ack} disabled={busy||!selected} onChange={event=>setAck(event.target.checked)}/>Tôi yêu cầu gọi công cụ chỉ đọc này với tham số đã duyệt. Không tự gửi lệnh ghi hoặc dùng quyền mô hình thay cho công cụ.</label>
    <button type="button" disabled={busy||!selected||!ack} onClick={()=>void work(async ticket=>{
      if(!selected)return;const requestKey=key||crypto.randomUUID();setKey(requestKey);
      const result=await api<{id:string;status:string}>(`/v1/connectors/connections/${selected.grant.connection_id}/calls`,"POST",{
        run_id:runId,tool_id:selected.tool.id,grant_id:selected.grant.grant_id,request_key:requestKey});
      if(ticket===epoch.current)setNotice(`Tác vụ ${result.id.slice(0,8)} · ${result.status}. đang chờ không có nghĩa công cụ đã chạy hoặc đã có kết quả.`);
    })}>Xếp hàng MCP chỉ đọc bằng quyền này</button>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{settingsError()}</p>}
  </section>;
}
