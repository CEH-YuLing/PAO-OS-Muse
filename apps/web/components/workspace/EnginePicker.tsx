"use client";
import {useEffect,useId,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import {Check,Search,Settings2} from 'lucide-react';
import {chatModelTabs,chatModelProviders,chatModelKey as selectionKey,chatProviderName,chatModelSummary,chatModelOptions,filterChatModels,chatEffortLabels as effortLabels,type ChatModelOption} from '@/lib/chat-model-catalog.mjs';
import ChatControlPopover from './ChatControlPopover';
import MuseCatalogPreview from './MuseCatalogPreview';
import {codexModelPath} from '@/lib/codex-model-choice.mjs';
type Selection={provider:string;model:string;grant_id?:string;enterprise_source_id?:string;personal_cli_source_id?:string;installation_resource_id?:string;reasoning_effort?:string|null;capabilities?:{vision:boolean;tools:boolean;cancel:string;usage:string}};
type Config={available:boolean;version:number;selection:Selection|null;pinned:boolean;knowledge_override:boolean;error?:string};
type ModelDetail=import('@/lib/chat-model-catalog.mjs').ChatModelDetail;
type Catalog={available:boolean;scope?:string;engines:{provider:string;models:string[];model_details?:ModelDetail[];local:boolean;error:string|null;enterprise_source_id?:string;personal_cli_source_id?:string;personal_cli_source_version?:number;installation_resource_id?:string}[]};
type Grants={items:{grant_id:string;provider:string;model:string}[];has_more:boolean};
export default function EnginePicker({onBusy,placement='inline'}:{onBusy:(value:boolean)=>void;placement?:'inline'|'header'}){
  const runtime=usePao(),epoch=useRef(0),[config,setConfig]=useState<Config|null>(null),[catalog,setCatalog]=useState<Catalog|null>(null),[choice,setChoice]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(""),[snapshot,setSnapshot]=useState<Selection|null>(null);
  const base=`/v1/sessions/${runtime.sessionId}`,workspace=runtime.sessions.find(s=>s.id===runtime.sessionId)?.workspace_id;
  const [refresh,setRefresh]=useState(0);
  const loadedScope=useRef('');
  const [grants,setGrants]=useState<Grants|null>(null);
  const [effort,setEffort]=useState('');
  const [modality,setModality]=useState('all');
  const id=useId(),[tab,setTab]=useState('client'),[query,setQuery]=useState(''),[closeSignal,setCloseSignal]=useState(0);
  useEffect(()=>{setEffort(config?.selection?.reasoning_effort||'')},[config]);
  const brand=runtime.sessions.find(s=>s.id===runtime.sessionId)?.brand_id;
  useEffect(()=>{const reload=()=>setRefresh(value=>value+1),events=['pao:chat-config','pao:codex-profile','pao:ai-resources'];events.forEach(event=>window.addEventListener(event,reload));return()=>events.forEach(event=>window.removeEventListener(event,reload))},[]);
  useEffect(()=>{const ticket=++epoch.current,scope=`${runtime.sessionId||''}:${workspace||''}:${brand||''}`,changed=loadedScope.current!==scope;loadedScope.current=scope;setCatalog(null);setGrants(null);setError("");setSnapshot(null);setBusy(false);if(changed){setConfig(null);setQuery('');setTab('client');setChoice('')}
    if(runtime.sessionId&&workspace)void runtime.api<Config>(`${base}/engine`).then(async value=>{
      if(ticket!==epoch.current)return;setConfig(value);setChoice(previous=>!changed&&previous?previous:value.selection?selectionKey(value.selection):"");
      if(value.available){
        const rows=await runtime.api<Catalog>(`/v1/engines?workspace_id=${workspace}`);
        if(ticket!==epoch.current)return;setCatalog(rows);
        if(rows.scope!=='installation'){
          const allowed=await runtime.api<Grants>(`/v1/workspaces/${workspace}/model-grants${brand?`?brand_id=${brand}`:""}`);
          if(ticket===epoch.current)setGrants(allowed);
        }
      }
    }).catch(reason=>{if(ticket===epoch.current)setError((reason as Error).message)});
    return()=>{epoch.current++};
  },[base,workspace,brand,runtime.api,runtime.sessionId,refresh]);
  useEffect(()=>{let live=true;setSnapshot(null);if(runtime.runId&&config?.available)void runtime.api<{snapshot:Selection|null}>(`/v1/runs/${runtime.runId}/engine`).then(value=>{if(live)setSnapshot(value.snapshot)}).catch(()=>{});return()=>{live=false}},[runtime.runId,runtime.run?.status,config?.available,runtime.api]);
  useEffect(()=>{let live=true;if(runtime.runId&&config?.available&&!runtime.active&&!busy)void runtime.api<Config>(`${base}/engine`).then(value=>{if(live){setConfig(value);if(value.selection)setChoice(selectionKey(value.selection))}}).catch(()=>{});return()=>{live=false}},[base,runtime.runId,runtime.run?.status,runtime.active,config?.available,busy,runtime.api]);
  useEffect(()=>()=>onBusy(false),[onBusy]);
  async function save(){if(!config||!choice)return;const ticket=epoch.current;setBusy(true);onBusy(true);setError("");try{const [provider,model,grant_id,enterprise_source_id,personal_cli_source_id,installation_resource_id]=JSON.parse(choice);const value=await runtime.api<Config>(`${base}/engine`,"PUT",{provider,model,...(provider==='muse'?{prepare_muse_context:true}:{}),...(grant_id?{grant_id}:{}),...(enterprise_source_id?{enterprise_source_id}:{}),...(personal_cli_source_id?{personal_cli_source_id}:{}),...(installation_resource_id?{installation_resource_id,reasoning_effort:effort||null}:{}),version:config.version});if(ticket===epoch.current){setConfig(value);setChoice(value.selection?selectionKey(value.selection):'');setCloseSignal(value=>value+1)}}catch(reason){if(ticket===epoch.current)setError((reason as Error).message)}finally{if(ticket===epoch.current)setBusy(false);onBusy(false)}}
  async function refreshCodex(){
    const source=catalog?.engines.find(row=>row.provider==='codex_cli'&&row.personal_cli_source_id&&row.personal_cli_source_version);
    if(!workspace||!source?.personal_cli_source_id||busy||runtime.active)return;
    const ticket=epoch.current;setBusy(true);onBusy(true);setError('');
    try{await runtime.api(codexModelPath(workspace,source.personal_cli_source_id,'models'),'POST',{version:source.personal_cli_source_version});if(ticket===epoch.current)setRefresh(value=>value+1)}
    catch{if(ticket===epoch.current)setError('Chưa tải được danh mục Codex. Kiểm tra đăng nhập hoặc Docker rồi chủ động thử lại; PAO không tự đổi nguồn.')}
    finally{if(ticket===epoch.current)setBusy(false);onBusy(false)}
  }
  if(!runtime.sessionId)return null;
  if(!config?.available)return error?<p role="alert">Không tải được cấu hình engine: {error}</p>:null;
  const current=config.selection,locked=busy||runtime.active;
  const options=chatModelOptions(catalog,grants,current),chosen=options.find(option=>option.key===choice),detail=chosen?.detail;
  const visible=filterChatModels(options,query,modality),providers=chatModelProviders.filter(provider=>provider.tab===tab);
  const additional=options.filter(option=>!chatModelProviders.some(provider=>provider.id===option.selection.provider));
  function choose(option:ChatModelOption){setChoice(option.key);setEffort('')}
  function modelRow(option:ChatModelOption){
    const duplicate=options.filter(row=>row.selection.provider===option.selection.provider&&row.selection.model===option.selection.model).length>1;
    return <label key={option.key} className={`pao-catalog-model${choice===option.key?' is-selected':''}${!option.available?' is-unavailable':''}`}>
      <input type="radio" name={`${id}-model`} aria-label={`${chatProviderName(option.selection.provider)} — ${option.selection.model}${duplicate?' · '+option.origin:''}`} value={option.key} checked={choice===option.key} disabled={locked||!catalog||!option.available} onChange={()=>choose(option)}/>
      <span><strong>{option.label}</strong>{option.label!==option.selection.model&&<small>{option.selection.model}</small>}{(duplicate||!option.available)&&<small>{option.origin}</small>}{option.detail?.model_capabilities?.chat_supported===false&&<small>Không dùng cho hội thoại văn bản · cần bộ kết nối chuyên dụng.</small>}</span>
      {choice===option.key&&<Check size={15} aria-hidden="true"/>}
    </label>;
  }
  const content=<>
    <p className="pao-catalog-intro">Chọn nhà cung cấp và mô hình cho hội thoại. Chỉ thay đổi sau khi bấm <strong>Áp dụng mô hình</strong>.</p>
    <div className="pao-catalog-tabs" role="tablist" aria-label="Loại kết nối mô hình" onKeyDown={event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();
      const next=event.key==='Home'?'client':event.key==='End'?'api':tab==='client'?'api':'client';
      setTab(next);document.getElementById(`${id}-${next}`)?.focus();
    }}>{chatModelTabs.map(item=><button key={item.id} id={`${id}-${item.id}`} type="button" role="tab" aria-selected={tab===item.id} aria-controls={`${id}-panel`} tabIndex={tab===item.id?0:-1} onClick={()=>setTab(item.id)}>{item.label}</button>)}</div>
    <label className="pao-catalog-search"><Search size={16} aria-hidden="true"/><input data-popover-autofocus aria-label="Tìm mô hình" placeholder="Tìm mô hình hoặc nhà cung cấp…" value={query} onChange={event=>setQuery(event.target.value)}/></label>
    <label>Loại đầu ra<select aria-label="Lọc loại đầu ra mô hình" value={modality} onChange={event=>setModality(event.target.value)}><option value="all">Tất cả loại đầu ra</option><option value="text">Văn bản</option><option value="image">Hình ảnh</option><option value="audio">Âm thanh</option><option value="video">Video</option><option value="embedding">Vector tri thức</option><option value="unknown">Chưa xác minh</option></select></label>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${tab}`}>
      <div className="pao-catalog-provider-grid" role="radiogroup" aria-label="Mô hình hội thoại">{providers.map(provider=>{
        const all=options.filter(option=>option.selection.provider===provider.id),rows=visible.filter(option=>option.selection.provider===provider.id),count=all.filter(option=>option.available).length;
        return <section key={provider.id} className="pao-catalog-provider" aria-label={`${provider.name} qua ${tab==='client'?'Client':'API'}`}>
          <header><span className="pao-catalog-provider-mark" aria-hidden="true">{provider.name.slice(0,2)}</span><h3>{provider.name}</h3><small>{modality!=='all'&&all.length?`${rows.length} / ${all.length} mô hình`:count?`${count} mô hình`:provider.id==='muse'?'Chưa bật hội thoại':provider.planned?'Chưa triển khai':'Chưa khả dụng'}</small></header>
          {provider.id==='codex_cli'&&catalog?.engines.some(row=>row.personal_cli_source_id&&row.personal_cli_source_version)&&<button type="button" disabled={locked} onClick={()=>void refreshCodex()}>Cập nhật danh mục Codex</button>}
          {provider.id==='muse'&&!all.length?<MuseCatalogPreview query={query}/>:<div className="pao-catalog-model-list">{rows.length?rows.map(modelRow):<div className="pao-catalog-empty"><p>{!catalog?'Đang đọc danh mục…':all.length?'Không có mô hình khớp tìm kiếm.':provider.id==='claude_code'?'Bộ kết nối hội thoại Claude Code chưa được triển khai.':provider.id==='antigravity'?'Kết nối Antigravity hiện chỉ đọc danh mục; chưa hỗ trợ hội thoại trong PAO.':`Chưa có mô hình ${provider.name} khả dụng trong PAO AI.`}</p>{catalog&&!all.length&&!provider.planned&&<a href={`/settings?tab=ai&section=providers&model_connection=${tab}&sme=${encodeURIComponent(workspace||'')}`}>Kiểm tra kết nối {provider.name}</a>}</div>}</div>}
        </section>;
      })}</div>
    </div>
    {!!additional.length&&<details className="pao-catalog-help"><summary>Mô hình trên máy và nguồn khác</summary><div role="radiogroup" aria-label="Mô hình bổ sung">{filterChatModels(additional,query).map(modelRow)}</div></details>}
    {config.error&&<p role="alert">Lựa chọn mặc định chưa dùng được. Hãy kiểm tra kết nối hoặc chủ động chọn mô hình khác.</p>}
    {error&&<p role="alert">{error}</p>}
    {locked&&<p role="status">{busy?'Đang xử lý yêu cầu…':'Hội thoại đang xử lý. Bạn có thể đổi mô hình sau khi lượt chạy kết thúc.'}</p>}
    {config.knowledge_override&&<p className="pao-catalog-notice">Nguồn trong chat đang bật: lượt chạy dùng đoạn trích local, không gọi mô hình đã chọn.</p>}
    <div className="pao-catalog-selection" aria-live="polite"><div><small>Lựa chọn sẽ áp dụng</small><strong>{chosen?chatModelSummary(chosen.selection):'Chưa chọn mô hình'}</strong></div>
      {chosen?.selection.provider==='muse'&&<p className="pao-catalog-native-budget">Muse dùng thêm token hướng dẫn native. Ngữ cảnh và đầu ra theo mô hình, không áp trần token PAO cho lượt mới. Giữ quyền riêng tư và quyền công cụ; không chuyển API tính phí.</p>}
      {detail&&<label>Mức suy luận<select aria-label="Mức suy luận" value={effort} disabled={locked||!detail.reasoning_efforts.length} onChange={event=>setEffort(event.target.value)}><option value="">Mặc định{detail.default_effort?` · ${effortLabels[detail.default_effort]||detail.default_effort}`:''}</option>{detail.reasoning_efforts.map(value=><option key={value} value={value}>{effortLabels[value]||value} · {value}</option>)}</select></label>}
      <button className="pao-catalog-apply" type="button" disabled={locked||!chosen?.available||!catalog} onClick={()=>void save()}>{busy?'Đang xử lý…':'Áp dụng mô hình'}</button>
      {detail&&<small className="pao-catalog-effort-help">{chosen?.selection.personal_cli_source_id?'Codex hiện dùng mức suy luận mặc định của bộ kết nối. Đổi model chỉ áp dụng cho hội thoại này, không đổi hồ sơ hoặc hội thoại khác.':detail.reasoning_efforts.length?'Suy luận cao hơn có thể chậm hơn và dùng nhiều hạn mức hơn.':'Chưa có thông tin mức suy luận cho mô hình này; PAO không tự giả định hỗ trợ.'}</small>}
    </div>
    <details className="pao-catalog-help"><summary><Settings2 size={14} aria-hidden="true"/>Thông tin lựa chọn và kết nối</summary>
      <p>Danh mục từ kết nối PAO hiện có, không phải kiểm tra hạn mức hay suy luận thật. Không tự chuyển nguồn hoặc gọi API tính phí.</p>
      <button type="button" disabled={locked} onClick={()=>setRefresh(value=>value+1)}>Tải lại danh mục kết nối</button>
      <p>{config.pinned?'Mô hình đã ghim cho hội thoại.':'Sẽ chốt mô hình mặc định ở lượt chạy đầu tiên.'} Đổi mô hình không xóa lịch sử/tri thức và không cấp thêm quyền dữ liệu hoặc công cụ.</p>
      {grants?.has_more&&<p>Danh sách quyền cũ còn trang tiếp theo; chưa hiển thị hết.</p>}
      {catalog?.engines.filter(row=>row.error).map((row,index)=><p key={`${row.provider}-${index}`}>{chatProviderName(row.provider)}: nguồn chưa khả dụng. Kiểm tra ở Cài đặt và kết nối.</p>)}
      {runtime.runId&&<p aria-label="Model đã chốt run">Lượt chạy đã chốt: {snapshot?chatModelSummary(snapshot):'chưa có thông tin'}</p>}
    </details>
  </>;
  const label=`${chatModelSummary(current)}${current?.reasoning_effort?' · '+(effortLabels[current.reasoning_effort]||current.reasoning_effort):''}`;
  return placement==='header'?<ChatControlPopover label={label} title="Chọn mô hình hội thoại" variant="models" closeSignal={closeSignal}>{content}</ChatControlPopover>:<details className="pao-engine-picker pao-catalog-inline" aria-label="Model hội thoại"><summary>{label}</summary>{content}</details>;
}
