"use client";
import {useCallback, useEffect, useRef, useState} from "react";
import {settingsLabel,settingsError} from '@/lib/settings-vi';
import {usePao} from "@/lib/PaoRuntimeContext";

type Reference = {id:string;source_id:string;kind:string;revision:number;status:string;generation?:number;supersedes_id?:string|null};
type Grant = {id:string;grantee_id:string;brand_id:string|null;account_id?:string|null;revision:number;status:string;expires_at:string;model_consent_recorded:boolean;read_consent_recorded?:boolean};
type Source = {identity:{kind:string;connection_id:string;provider:string};stored_status:string;config_version:number|null};
type Options = {members:{id:string;email:string;role:string}[];brands:{id:string;name:string}[];has_more:boolean};
type Group = {reference:Reference;items:Grant[];has_more:boolean};

// Parent keys this panel by workspace. Epoch also discards refresh/unmount results.
export default function ConnectionGrantPanel({kind="model"}:{kind?:"model"|"cli_model"|"mcp"|"meta_ads"|"google_ads"}){
  const runtime=usePao(), member=runtime.activeWorkspace, workspace=member?.id||"";
  const {api}=runtime, actor=runtime.me?.id||"",cli=kind==="cli_model",model=kind==="model"||cli, ads=kind==="meta_ads"||kind==="google_ads", label=cli?"Codex cá nhân":kind==="model"?"mô hình":kind==="mcp"?"MCP":kind==="meta_ads"?"Meta Ads":"Google Ads";
  const managing=member?.role==="owner"||member?.role==="admin";
  const base=`/v1/workspaces/${workspace}/connection-inventory`;
  const epoch=useRef(0), keys=useRef(new Map<string,string>());
  const [sources,setSources]=useState<Source[]>([]),[options,setOptions]=useState<Options|null>(null),[groups,setGroups]=useState<Group[]>([]);
  const [source,setSource]=useState(""),[grantee,setGrantee]=useState(""),[brand,setBrand]=useState(""),[ttl,setTtl]=useState(60);
  const [accounts,setAccounts]=useState<string[]>([]),[account,setAccount]=useState("");
  const [reapplyAck,setReapplyAck]=useState(false);
  useEffect(()=>{setReapplyAck(false)},[workspace,managing,source,grantee,brand,account,ttl]);
  const [dataAck,setDataAck]=useState(false),[callAck,setCallAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [loaded,setLoaded]=useState(false),[needsRead,setNeedsRead]=useState(false),working=useRef(false);
  const blocked=cli&&(!loaded||needsRead);
  useEffect(()=>{if(cli){setDataAck(false);setCallAck(false)}},[cli,source,grantee,brand,ttl]);
  const load=useCallback(async(ticket:number)=>{
    const [inventory,choices,references]=await Promise.all([
      api<{items:Source[];has_more?:boolean}>(base),api<Options>(base+"/options"),
      api<{items:Reference[];has_more:boolean}>(base+"/references")]);
    const matching=references.items.filter(row=>row.kind===kind);
    const rows=await Promise.all(matching.map(row=>api<Group>(`${base}/references/${row.id}/grants`)));
    if(ticket!==epoch.current)return;
    setSources(inventory.items.filter(row=>row.identity.kind===kind));setOptions(choices);setGroups(rows);
    setLoaded(!inventory.has_more&&!choices.has_more&&!references.has_more&&!rows.some(row=>row.has_more));setNeedsRead(false);
    if(choices.has_more||references.has_more||rows.some(row=>row.has_more))setNotice("Danh sách đang giới hạn; không thể hiện toàn bộ quyền. Dùng API phân trang để xem phần còn lại.");
  },[base,api,kind]);
  useEffect(()=>{const panelEpoch=epoch,ticket=++panelEpoch.current;keys.current.clear();setError("");setBusy(false);setLoaded(false);setNeedsRead(false);setNotice("");setSources([]);setOptions(null);setGroups([]);setSource("");setGrantee(cli?actor:"");setBrand("");setDataAck(false);setCallAck(false);if(workspace&&managing)void load(ticket).catch(reason=>{if(ticket===panelEpoch.current)setError((reason as Error).message)});return()=>{panelEpoch.current++}},[workspace,actor,cli,managing,load]);
  useEffect(()=>{let current=true;setAccounts([]);setAccount("");setDataAck(false);if(ads&&source&&managing)void api<{items:{account_id:string}[];has_more:boolean}>(`${base}/ads-accounts?kind=${kind}&connection_id=${source}`).then(rows=>{if(current){setAccounts(rows.items.map(row=>row.account_id));if(rows.has_more)setNotice("Tài khoản đang phân trang; dùng API để xem phần còn lại.")}}).catch(reason=>{if(current)setError((reason as Error).message)});return()=>{current=false}},[ads,source,managing,api,base,kind]);
  function requestKey(action:string){let value=keys.current.get(action);if(!value){value=crypto.randomUUID();keys.current.set(action,value)}return value}
  async function work(action:string,operation:()=>Promise<unknown>){
    if(working.current||blocked)return;working.current=true;
    const ticket=epoch.current;setBusy(true);setError("");setNotice("");
    try{await operation();keys.current.delete(action);if(ticket!==epoch.current)return;setCallAck(false);setDataAck(false);setNotice("Đã lưu. Đây là kiểm tra quyền trên máy, chưa xác nhận nhà cung cấp hoạt động.");await load(ticket)}
    catch(reason){if(ticket===epoch.current){setError((reason as Error).message);if(cli){setNeedsRead(true);setDataAck(false);setCallAck(false)}}}
    finally{working.current=false;if(ticket===epoch.current)setBusy(false)}
  }
  async function stage(parent?:Reference){
    const proposal={kind,connection_id:source,expected_version:kind==="model"?null:sources.find(row=>row.identity.connection_id===source)?.config_version,
      brand_id:brand||null,grantee_id:grantee,permission:"read_only",...(ads?{account_id:account}:{})};
    const action=JSON.stringify([parent?"reapply":"stage",parent?.id,parent?.revision,proposal,ttl]);
    const ticket=epoch.current;
    await work(action,async()=>{
      const preview=await runtime.api<{preview_hash:string}>(base+"/mapping-preview","POST",proposal);
      if(ticket!==epoch.current)throw new Error('connection_scope_changed');
      const result=await runtime.api(base+"/references"+(parent?`/${parent.id}/reapply`:""),"POST",{...proposal,preview_hash:preview.preview_hash,request_key:requestKey(action),
        ttl_minutes:ttl,manager_id:model?actor:null,apply_data_only_ack:true,
        ...(parent?{reference_revision:parent.revision,revoke_old_generation_ack:true}:{})});
      setReapplyAck(false);return result;
    });
  }
  if(!workspace)return null;
  const activated=(grant:Grant)=>model?grant.model_consent_recorded:grant.read_consent_recorded;
  if(!managing)return <section aria-label={`Quyền dùng ${label}`}><h3>Quyền dùng {label} theo doanh nghiệp</h3><p>Người quản lý cấp quyền. Chọn đúng kết nối và quyền đã cấp; không tự dùng kết nối của đồng nghiệp. Quyền mô hình không cấp quyền công cụ.</p></section>;
  return <section className="pao-model-access" aria-label={`Quyền dùng ${label}`}>
    <h3>Quyền dùng {label} theo doanh nghiệp</h3>
    {cli?<p>Chỉ cấp cho chính tài khoản PAO đang đăng nhập, không chia sẻ thuê bao cho nhân viên. Chọn hồ sơ Codex đã đăng nhập, phạm vi nhãn hàng và thời hạn. Lưu quyền chưa cho phép gọi AI; kích hoạt riêng có thể tiêu hạn mức thuê bao, không cấp quyền công cụ hoặc tự chọn model cho hội thoại.</p>:kind==="model"?<p>Đăng ký kết nối sẽ chặn đường dùng chung cũ. Lưu mapping chưa cho phép gọi AI. Kích hoạt riêng chỉ cho mô hình suy luận AI, không cấp quyền Ads, công cụ hoặc kho tri thức. mô hình đám mây có thể tiêu token; không kích hoạt nếu chưa đồng ý sử dụng.</p>
      :ads?<p>Đăng ký kết nối chặn đồng bộ/report/action theo đường chủ doanh nghiệp cũ. Chỉ chọn tài khoản đã tìm danh mục thành công tại phiên bản kết nối hiện tại. Mapping chưa cấp quyền chạy; kích hoạt riêng chỉ đọc lịch sử warehouse và báo cáo đúng tài khoản, không cấp quyền sửa Ads, chi tiền hoặc cấu hình OAuth.</p>
      :<p>Đăng ký MCP chặn đường dùng chủ doanh nghiệp cũ. Tenant quyền được cấp cần credential đã cấu hình. Mapping chưa cấp quyền chạy. Kích hoạt chỉ đọc vẫn cần công cụ/tham số đã duyệt, kỹ năng đã công bố/thẩm định và quyền kho tri thức của nhân viên. Không cấp quyền cấu hình token, ghi dữ liệu, shell hoặc Ads.</p>}
    <label>Kết nối {label}<select aria-label="Kết nối cấp quyền" value={source} disabled={busy} onChange={e=>setSource(e.target.value)}>
      <option value="">Chọn kết nối…</option>{sources.map(row=><option key={row.identity.connection_id} value={row.identity.connection_id}>{row.identity.provider} · {settingsLabel(row.stored_status)} · {row.identity.connection_id.slice(0,8)}</option>)}
    </select></label>
    {ads&&<label>Tài khoản đã tìm danh mục<select aria-label={`Tài khoản cấp ${label}`} value={account} disabled={busy||!source} onChange={e=>setAccount(e.target.value)}><option value="">Chọn tài khoản…</option>{accounts.map(id=><option key={id} value={id}>{id}</option>)}</select></label>}
    <label>{cli?'Người sử dụng (chỉ chính bạn)':'Nhân viên'}<select aria-label={`Nhân viên được cấp ${label}`} value={grantee} disabled={busy||cli} onChange={e=>setGrantee(e.target.value)}>
      <option value="">Chọn thành viên…</option>{options?.members.filter(row=>!cli||row.id===actor).map(row=><option key={row.id} value={row.id}>{row.email} · {settingsLabel(row.role)}</option>)}
    </select></label>
    <label>Nhãn hàng<select aria-label={`Nhãn hàng cấp ${label}`} value={brand} disabled={busy} onChange={e=>setBrand(e.target.value)}>
      <option value="">Chỉ hội thoại không gắn nhãn hàng</option>{options?.brands.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}
    </select></label>
    <label>Thời hạn (phút)<input aria-label={`Thời hạn quyền ${label}`} type="number" min={1} max={43200} value={ttl} disabled={busy} onChange={e=>setTtl(Number(e.target.value))}/></label>
    <label><input type="checkbox" checked={dataAck} disabled={busy} onChange={e=>setDataAck(e.target.checked)}/>Tôi xác nhận doanh nghiệp, kết nối, thành viên, nhãn hàng và thời hạn; chỉ lưu mapping.</label>
    <button type="button" disabled={busy||blocked||!dataAck||!source||!grantee||(ads&&!account)||!Number.isInteger(ttl)||ttl<1||ttl>43200} onClick={()=>void stage()}>Lưu quyền chờ kích hoạt</button>
    <label><input aria-label={model?"Đồng ý kích hoạt mô hình suy luận AI":ads?`Đồng ý kích hoạt ${label} chỉ đọc`:"Đồng ý kích hoạt MCP chỉ đọc"} type="checkbox" checked={callAck} disabled={busy||blocked} onChange={e=>setCallAck(e.target.checked)}/>{model?"Tôi cho phép quyền được chọn gọi mô hình AI theo chính sách hiện tại, có thể tiêu token; không cho phép công cụ hoặc hành động bên ngoài.":ads?"Tôi cho phép đọc số liệu tài khoản đã chọn; không cho phép sửa quảng cáo hoặc chi tiền.":"Tôi cho phép nhân viên dùng MCP chỉ đọc trong phạm vi đã chọn; vẫn phải có quyền công cụ, kỹ năng và kho tri thức riêng."}</label>
    <label><input aria-label={`Đồng ý cấp lại phiên bản ${label}`} type="checkbox" checked={reapplyAck} disabled={busy} onChange={e=>setReapplyAck(e.target.checked)}/>Nếu cấu hình đã đổi hoặc reference bị thu hồi: tôi xác nhận thu hồi toàn bộ quyền của phiên bản cũ trên kết nối đã chọn, tạo mapping mới từ biểu mẫu trên. công việc/quyền/TTL cũ không sống lại; bản mới còn phải kích hoạt riêng.</label>
    {groups.map(group=><div key={group.reference.id} aria-label={`${label} reference ${group.reference.id}`}>
      <h4>Kết nối {group.reference.source_id.slice(0,8)} · phiên bản quyền {group.reference.generation||1} · {settingsLabel(group.reference.status)}</h4>
      <button type="button" disabled={busy||blocked||!reapplyAck||!dataAck||source!==group.reference.source_id||!grantee||(ads&&!account)||!Number.isInteger(ttl)||ttl<1||ttl>43200}
        onClick={()=>void stage(group.reference)}>Cấp lại bằng phiên bản mới</button>
      {group.items.map(grant=><article key={grant.id} aria-label={`Quyền ${label} ${grant.id}`}>
        <p>{options?.members.find(row=>row.id===grant.grantee_id)?.email||grant.grantee_id} · {options?.brands.find(row=>row.id===grant.brand_id)?.name||(grant.brand_id?grant.brand_id:"Không gắn nhãn hàng")} · {grant.account_id||""} · {settingsLabel(grant.status)} · hết hạn {new Date(grant.expires_at).toLocaleString("vi-VN")}</p>
        <p>{activated(grant)?"Đã ghi nhận đồng ý kích hoạt; quyền vẫn cần kiểm tra ở mỗi tác vụ":"Chưa kích hoạt"}</p>
        <button type="button" disabled={busy||blocked||!callAck||Boolean(activated(grant))||grant.status!=="staged"||group.reference.status!=="staged"||Date.parse(grant.expires_at)<=Date.now()}
          onClick={()=>{const action="activate:"+grant.id;void work(action,()=>runtime.api(`${base}/references/${group.reference.id}/grants/${grant.id}/activate-${model?"model":ads?"ads":kind}`,"POST",{
            reference_revision:group.reference.revision,grant_revision:grant.revision,request_key:requestKey(action),
            ...(model?{capability:"model_inference",allow_model_inference_ack:true}:ads?{capability:"ads_read",allow_ads_read_ack:true}:{capability:"mcp_read",allow_mcp_read_ack:true})}))}}>Kích hoạt quyền này</button>
        <button type="button" disabled={busy||blocked||grant.status!=="staged"} onClick={()=>void work("revoke:"+grant.id,()=>runtime.api(`${base}/references/${group.reference.id}/grants/${grant.id}/revoke`,"POST",{
          reference_revision:group.reference.revision,grant_revision:grant.revision}))}>Thu hồi quyền này</button>
      </article>)}
    </div>)}
    {!sources.length&&<p>Chưa có kết nối {label} trong doanh nghiệp này.</p>}
    {cli&&<><button type="button" disabled={busy} onClick={()=>{setDataAck(false);setCallAck(false);setLoaded(false);setBusy(true);const ticket=epoch.current;void load(ticket).catch(()=>{if(ticket===epoch.current)setError('read_failed')}).finally(()=>{if(ticket===epoch.current)setBusy(false)})}}>Đọc lại quyền Codex</button><p>Nếu mất phản hồi, đọc lại trước khi thử tiếp; PAO không tự gửi lại. Không tự cấp lại phiên bản cũ hoặc nối lại quyền đã thu hồi. Khi danh mục bị giới hạn/phân trang, tạm chặn thay đổi để tránh chọn thiếu phạm vi.</p>{blocked&&<p role="status">Chưa đủ dữ liệu xác minh. Đọc lại quyền trước khi thay đổi.</p>}</>}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{settingsError()}</p>}
  </section>;
}
