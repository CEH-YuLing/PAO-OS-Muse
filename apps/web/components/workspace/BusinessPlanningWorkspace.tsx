'use client';
import {useCallback,useEffect,useRef,useState,type FormEvent} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import PaoAppShell from './PaoAppShell';
import BusinessPlanReviewPanel from './BusinessPlanReviewPanel';
import BusinessRoutingPanel from './BusinessRoutingPanel';
import BusinessOperationsPanel from './BusinessOperationsPanel';
import {businessDraftKey,saveBusinessDraft,readBusinessDraft,discardBusinessDraft} from '@/lib/business-drafts.mjs';
import {readBusinessLocation,businessLocationUrl} from '@/lib/settings-navigation.mjs';
import './business-planning.css';
import {SectionTabs,SectionPanel,useSection} from './SectionNavigation';
const PLAN_VIEWS=[{id:'plan',label:'Kế hoạch'},{id:'routing',label:'Phân công AI'},{id:'jobs',label:'Công việc'},{id:'review',label:'Phê duyệt'},{id:'report',label:'Báo cáo'}];

type Content={description:string;products:string[];audience:string;brand_voice:string;objectives:string[];kpis:{name:string;target:string|null;unit:string}[];resources:string;monthly_budget:string|null;currency:string;timezone:string};
type Profile={id:string;workspace_id:string;revision:number;current_revision:number;version_id:string;content:Content;content_hash:string;missing_fields:string[]};
type Item={key:string;title:string;specialist:'content'|'creative'|'ads'|'analyst';due_date:string;brief:string;acceptance:string[];depends_on:string[]};
type DraftItem=Omit<Item,'acceptance'|'depends_on'>&{acceptance:string;depends_on:string};
type Plan={id:string;profile_id:string;revision:number;currency:string;content_hash:string;content:{title:string;month:string;campaign_brief:string;deliverables:Item[]};profile_revision:number;profile_stale:boolean};
type Status={available:boolean;can_manage:boolean;execution_enabled:boolean};
type AuthoringDraft={profileHash:string|null;plan:Plan|null;form:Content;products:string;objectives:string;kpis:Content['kpis'];title:string;month:string;brief:string;items:DraftItem[]};
const empty:Content={description:'',products:[],audience:'',brand_voice:'',objectives:[],kpis:[],resources:'',monthly_budget:null,currency:'VND',timezone:'Asia/Ho_Chi_Minh'};
const labels:Record<string,string>={description:'Mô tả doanh nghiệp',products:'Sản phẩm',audience:'Khách hàng mục tiêu',brand_voice:'Giọng thương hiệu',objectives:'Mục tiêu',kpis:'KPI',resources:'Nguồn lực',monthly_budget:'Ngân sách tháng'};
const lines=(value:string)=>value.split('\n').map(item=>item.trim()).filter(Boolean);

export default function BusinessPlanningWorkspace(){
 const {me,activeWorkspace}=usePao();
 return <BusinessPlanningScope key={JSON.stringify([me?.id,activeWorkspace?.id,activeWorkspace?.role])}/>;
}
function BusinessPlanningScope(){
 const {api,me,activeWorkspace:member}=usePao(),wid=member?.id||'',base=`/v1/workspaces/${wid}/business-planning`;
 const [view,setView]=useSection(PLAN_VIEWS,'view','plan',{'bp-profile':'plan','bp-plan':'plan','bp-routing':'routing','bp-review':'review','bp-run':'jobs','bp-report':'report'});
 const epoch=useRef(0),lock=useRef(false),request=useRef(''),planId=useRef('');
 const [status,setStatus]=useState<Status|null>(null),[brands,setBrands]=useState<{id:string;name:string}[]>([]),[brand,setBrand]=useState('');
 const [navigationReady,setNavigationReady]=useState(false);
 useEffect(()=>{setBrand(readBusinessLocation(location.search,wid).brand);setNavigationReady(true)},[wid]);
 const [profile,setProfile]=useState<Profile|null>(null),[form,setForm]=useState<Content>({...empty});
 const [products,setProducts]=useState(''),[objectives,setObjectives]=useState(''),[kpis,setKpis]=useState<Content['kpis']>([]);
 const [plan,setPlan]=useState<Plan|null>(null),[plans,setPlans]=useState<Plan[]>([]),[more,setMore]=useState(false);
 const [title,setTitle]=useState(''),[month,setMonth]=useState(''),[brief,setBrief]=useState(''),[items,setItems]=useState<DraftItem[]>([]);
 const [busy,setBusy]=useState(false),[unknown,setUnknown]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[dirty,setDirty]=useState(false);
 const [history,setHistory]=useState<Profile|null>(null),[historyRevision,setHistoryRevision]=useState('1');
 const [routingDirty,setRoutingDirty]=useState(false);
 const [operationsDirty,setOperationsDirty]=useState(false);
 const [routingRevision,setRoutingRevision]=useState(0);
 const [reviewRevision,setReviewRevision]=useState(0);
 const reviewChanged=useCallback(()=>setReviewRevision(value=>value+1),[]);
 const [planHistory,setPlanHistory]=useState<Plan|null>(null),[planHistoryRevision,setPlanHistoryRevision]=useState('1');
 useEffect(()=>{setPlanHistory(null);setPlanHistoryRevision('1')},[plan?.id,plan?.revision]);
 const draftKey=businessDraftKey(me?.id||'',wid,brand,member?.role||'');
 useEffect(()=>{if(dirty&&!busy&&!unknown&&status?.available&&status.can_manage)saveBusinessDraft(draftKey,{profileHash:profile?.content_hash||null,plan,form,products,objectives,kpis,title,month,brief,items});},[dirty,busy,unknown,status,draftKey,profile,plan,form,products,objectives,kpis,title,month,brief,items]);
 useEffect(()=>{if(!dirty&&!busy&&status?.available&&status.can_manage)discardBusinessDraft(draftKey);},[dirty,busy,status,draftKey]);
 const fillProfile=useCallback((row:Profile|null)=>{setProfile(row);setForm(row?row.content:{...empty});setProducts(row?.content.products.join('\n')||'');setObjectives(row?.content.objectives.join('\n')||'');setKpis(row?.content.kpis||[]);setHistory(null)},[]);
 const fillPlan=useCallback((row:Plan|null)=>{setPlan(row);setTitle(row?.content.title||'');setMonth(row?.content.month.slice(0,7)||'');setBrief(row?.content.campaign_brief||'');setItems(row?.content.deliverables.map(item=>({...item,acceptance:item.acceptance.join('\n'),depends_on:item.depends_on.join(',')}))||[]);planId.current='';window.history.replaceState(window.history.state,'',businessLocationUrl(location.href,wid,brand,row?.id||''))},[wid,brand]);
 const load=useCallback(async()=>{
  if(lock.current||!wid||!navigationReady)return;const selected=readBusinessLocation(location.search,wid);lock.current=true;const ticket=++epoch.current;setBusy(true);setError('');setNotice('');setStatus(null);setProfile(null);setPlans([]);setHistory(null);
  try{
   const state=await api<Status>(base+'/status');if(ticket!==epoch.current)return;setStatus(state);
   if(!state.available||!state.can_manage){discardBusinessDraft(draftKey);setUnknown(false);setDirty(false);return}
   const [source,availableBrands]=await Promise.all([api<{item:Profile|null}>(base+'/profile'+(brand?'?brand_id='+brand:'')),api<{id:string;name:string}[]>('/v1/brands?workspace_id='+wid)]);
   if(ticket!==epoch.current)return;setBrands(availableBrands);fillProfile(source.item);fillPlan(null);request.current='';setMore(false);
   if(source.item){const listed=await api<{items:Plan[];has_more:boolean}>(base+'/plans?profile_id='+source.item.id);if(ticket!==epoch.current)return;setPlans(listed.items);setMore(listed.has_more)}
   const draft=readBusinessDraft(draftKey) as AuthoringDraft|null;
   if(draft){const current=draft.plan?await api<Plan>(base+'/plans/'+draft.plan.id):null;if(ticket!==epoch.current)return;
    if(draft.profileHash===(source.item?.content_hash||null)&&(!draft.plan||current?.content_hash===draft.plan.content_hash)){
     fillPlan(current);setForm(draft.form);setProducts(draft.products);setObjectives(draft.objectives);setKpis(draft.kpis);setTitle(draft.title);setMonth(draft.month);setBrief(draft.brief);setItems(draft.items);setDirty(true);setNotice('Đã khôi phục bản nháp riêng của doanh nghiệp/nhãn hàng này trong phiên làm việc. Chưa lưu lên máy chủ hoặc thực hiện tác vụ.');
    }else{discardBusinessDraft(draftKey);setDirty(false);setNotice('Phiên bản máy chủ đã thay đổi. Không tự ghép hoặc áp dụng bản nháp cũ; hãy đọc lịch sử trước khi chỉnh sửa.');}
   }else{if(selected.plan&&source.item){const linked=await api<Plan>(base+'/plans/'+selected.plan);if(ticket!==epoch.current)return;if(linked.profile_id!==source.item.id)throw new Error('scope_changed');fillPlan(linked);}setDirty(false);}setUnknown(false);
  }catch{if(ticket===epoch.current){setUnknown(true);setError('Chưa đọc được dữ liệu S5. Máy chủ có thể chưa phát hành hoặc chưa bật chức năng; không nhập lại khóa kết nối.')}}
  finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[api,base,wid,brand,draftKey,fillProfile,fillPlan,navigationReady]);
 useEffect(()=>{const e=epoch,l=lock;void load();return()=>{e.current++;l.current=false}},[load]);
 useEffect(()=>{if(!dirty)return;const leave=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};window.addEventListener('beforeunload',leave);return()=>window.removeEventListener('beforeunload',leave)},[dirty]);
 function leave(){const accepted=(!dirty&&!routingDirty&&!operationsDirty)||window.confirm('Bỏ bản nháp chưa lưu? Thao tác đã gửi không tự bị hủy hoặc hoàn tác.');if(accepted)discardBusinessDraft(draftKey);return accepted}
 async function work(action:(ticket:number)=>Promise<void>){if(lock.current||unknown)return;lock.current=true;const ticket=epoch.current;setBusy(true);setError('');setNotice('');try{await action(ticket)}catch{if(ticket===epoch.current){setUnknown(true);setError('Chưa xác nhận được kết quả. Không tự gửi lại; hãy đọc lại và kiểm tra phiên bản, quyền hoặc thông tin nhập.')}}finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}}
 function edit<K extends keyof Content>(key:K,value:Content[K]){setForm(previous=>({...previous,[key]:value}));setDirty(true)}
 async function saveProfile(event:FormEvent){event.preventDefault();if(dirty&&items.length&&!window.confirm('Lưu hồ sơ sẽ đóng bản nháp kế hoạch đang mở. Kế hoạch đã lưu giữ nguyên lịch sử; phần kế hoạch chưa lưu sẽ bị bỏ. Tiếp tục?'))return;
  await work(async ticket=>{request.current ||=crypto.randomUUID();const row=await api<Profile>(base+'/profile'+(brand?'?brand_id='+brand:''),'PUT',{expected_revision:profile?.revision||0,request_key:request.current,content:{...form,products:lines(products),objectives:lines(objectives),kpis}});if(ticket!==epoch.current)return;fillProfile(row);request.current='';setDirty(false);setNotice('Đã lưu hồ sơ phiên bản '+row.revision+'. Kế hoạch cũ vẫn giữ nguồn đã ghim; chưa giao việc hoặc chi tiền.');setPlans([]);fillPlan(null)})}
 async function savePlan(event:FormEvent){event.preventDefault();if(!profile)return;await work(async ticket=>{planId.current ||=plan?.id||crypto.randomUUID();const row=await api<Plan>(base+'/plans/'+planId.current,'PUT',{expected_revision:plan?.revision||0,request_key:crypto.randomUUID(),profile_id:profile.id,profile_revision:profile.revision,content:{title,month:month+'-01',campaign_brief:brief,deliverables:items.map(item=>({...item,acceptance:lines(item.acceptance),depends_on:item.depends_on.split(',').map(key=>key.trim()).filter(Boolean)}))}});if(ticket!==epoch.current)return;fillPlan(row);setPlans(previous=>[row,...previous.filter(item=>item.id!==row.id)]);setDirty(false);setNotice('Đã lưu bản nháp kế hoạch phiên bản '+row.revision+'. Chưa duyệt, chưa tạo task hoặc chạy AI.');})}
 function changeItem(index:number,key:keyof DraftItem,value:string){setDirty(true);setItems(previous=>previous.map((item,i)=>i===index?{...item,[key]:value}:item))}
 function clonePlan(){
  if(lock.current||unknown||!plan||dirty||routingDirty||operationsDirty)return;
  if(!window.confirm('Tạo bản nháp kế hoạch mới từ nội dung đang mở? Không sao chép quyền duyệt, task hoặc chạy lại AI.'))return;
  setPlan(null);planId.current='';window.history.replaceState(window.history.state,'',businessLocationUrl(location.href,wid,brand));
  setTitle(title+' — điều chỉnh');setDirty(true);
  setNotice('Đang soạn kế hoạch mới. Rà soát nội dung, lưu và xin phê duyệt riêng trước khi chạy.');
  document.getElementById('bp-plan')?.focus();
 }
 return <PaoAppShell pageTitle="Kế hoạch kinh doanh" pageSubtitle="Hồ sơ, kế hoạch, công việc AI và báo cáo có kiểm soát."><div className="bp-workspace" aria-busy={busy}>
  <SectionTabs id="business-view" label="Hành trình kế hoạch kinh doanh" items={PLAN_VIEWS} value={view} onChange={setView}/>
  <p className="bp-context" role="note">Phạm vi: <strong>{member?.name}</strong> · {brands.find(b=>b.id===brand)?.name||'Toàn doanh nghiệp'}. {busy?'Đang đọc hoặc xử lý…':dirty?'Có bản nháp chưa lưu':'Đang xem phiên bản đã đọc; không phải trạng thái thời gian thực'}</p>
  <details><summary>Hướng dẫn bắt đầu cho người mới</summary><ol><li>Chọn doanh nghiệp và phạm vi nhãn hàng, nhập hồ sơ rồi lưu.</li><li>Soạn kế hoạch tháng và các đầu việc, chọn kỹ năng và model phù hợp.</li><li>Chủ doanh nghiệp duyệt đúng phiên bản và tạo công việc nháp.</li><li>Xem trước lựa chọn AI, xác nhận chạy riêng từng việc và duyệt kết quả.</li><li>Kiểm tra đề xuất mô phỏng và báo cáo; thiếu dữ liệu không có nghĩa bằng 0.</li></ol><p>Bản nháp hồ sơ/kế hoạch được giữ tối đa 30 phút trong bộ nhớ của tab, tách theo tài khoản, doanh nghiệp, nhãn hàng và vai trò. Đóng/tải lại tab hoặc đăng xuất sẽ mất bản chưa lưu. Khóa kết nối, cấu hình AI chưa lưu và quyền duyệt/chạy không được lưu cùng bản nháp.</p></details>
  <p className="bp-warning">AI chỉ chạy khi bạn xác nhận và đủ quyền/phê duyệt. Ngân sách và hành động chiến dịch tại đây là mô phỏng để nghiệm thu an toàn; không tự đăng bài, gửi tin hoặc bật quảng cáo thật. Chức năng còn phụ thuộc cờ máy chủ và worker.</p>
  <div className="bp-toolbar"><strong>{member?.name}</strong><button disabled={busy} onClick={()=>{if(leave())void load()}}>Đọc lại hồ sơ và kế hoạch</button></div>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {status&&!status.available&&<p role="status">Chức năng S5 chưa được quản trị máy chủ bật.</p>}
  {status&&!status.can_manage&&<p role="note">Hiện chỉ chủ doanh nghiệp/quản trị viên soạn hồ sơ và kế hoạch. Không tự cấp quyền từ quyền xem task.</p>}
  {status?.available&&status.can_manage&&<>
   <label>Phạm vi hồ sơ<select aria-label="Phạm vi hồ sơ kinh doanh" disabled={busy} value={brand} onChange={event=>{if(leave()){discardBusinessDraft(draftKey);setDirty(false);window.history.replaceState(window.history.state,'',businessLocationUrl(location.href,wid,event.target.value));setBrand(event.target.value)}}}><option value="">Toàn doanh nghiệp</option>{brands.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
   <SectionPanel id="business-view" name="plan" active={view==='plan'}><aside className="ux-context-note"><strong>Hồ sơ nguồn: {profile?'phiên bản '+profile.revision:'chưa có'}</strong><p>Dùng cùng hồ sơ với Kho tri thức; kế hoạch đã lưu giữ nguyên nguồn đã chốt.</p><a href={'/knowledge?tab='+(brand?'brands':'enterprise')+(brand?'&brand='+encodeURIComponent(brand):'')}>Mở hồ sơ trong Kho tri thức</a></aside>
   <details className="ux-profile-compat"><summary>Hồ sơ nguồn và lịch sử — chỉnh sửa nhanh nâng cao</summary><section id="bp-profile" tabIndex={-1}><h2>1. Hồ sơ {brand?'nhãn hàng':'doanh nghiệp'}</h2><p>Thông tin chia sẻ với người quản lý trong doanh nghiệp. Không nhập mật khẩu hoặc token. Ngân sách/KPI chưa biết để trống/null, không tự coi là 0.</p><p>{profile?'Phiên bản '+profile.revision+' · '+profile.content_hash.slice(0,12):'Chưa có hồ sơ'}</p>
    {profile?.missing_fields.length?<p className="bp-warning">Cần bổ sung: {profile.missing_fields.map(key=>labels[key]||'Giá trị mục tiêu KPI').join(', ')}.</p>:null}
    <form onSubmit={saveProfile}><fieldset disabled={busy||unknown}><div className="bp-grid">
     {(['description','audience','brand_voice','resources'] as const).map(key=><label key={key}>{labels[key]}<textarea aria-label={labels[key]} rows={3} maxLength={key==='description'?4000:2000} value={form[key]} onChange={event=>edit(key,event.target.value)}/></label>)}
     <label>Sản phẩm — mỗi dòng một mục<textarea aria-label="Sản phẩm" rows={3} value={products} onChange={event=>{setProducts(event.target.value);setDirty(true)}}/></label>
     <label>Mục tiêu — mỗi dòng một mục<textarea aria-label="Mục tiêu" rows={3} value={objectives} onChange={event=>{setObjectives(event.target.value);setDirty(true)}}/></label>
     <label>Ngân sách dự kiến tháng<input aria-label="Ngân sách dự kiến tháng" inputMode="decimal" placeholder="Để trống nếu chưa biết" value={form.monthly_budget??''} onChange={event=>edit('monthly_budget',event.target.value||null)}/><small>Không phải số dư hoặc quyền chi tiền.</small></label>
     <label>Tiền tệ<input aria-label="Tiền tệ kế hoạch" maxLength={3} value={form.currency} onChange={event=>edit('currency',event.target.value.toUpperCase())}/><small>Mã ba chữ cái, ví dụ VND/USD; không quy đổi tự động.</small></label>
     <label>Múi giờ<input aria-label="Múi giờ kế hoạch" value={form.timezone} onChange={event=>edit('timezone',event.target.value)}/><small>Ví dụ Asia/Ho_Chi_Minh.</small></label>
    </div><h3>Chỉ số mục tiêu (KPI)</h3><p>Ví dụ: tên “Đơn hàng”, mục tiêu “100”, đơn vị “đơn”. Để trống mục tiêu nếu chưa biết; đây không phải số liệu đã đo.</p>{kpis.map((kpi,index)=><div className="bp-deliverable" key={index}><div className="bp-grid">{(['name','target','unit'] as const).map(field=><label key={field}>{field==='name'?'Tên chỉ số':field==='target'?'Giá trị mục tiêu':'Đơn vị'}<input aria-label={`KPI ${index+1} ${field==='name'?'tên':field==='target'?'mục tiêu':'đơn vị'}`} value={kpi[field]??''} required={field!=='target'} onChange={event=>{setKpis(previous=>previous.map((item,i)=>i===index?{...item,[field]:field==='target'?(event.target.value||null):event.target.value}:item));setDirty(true)}}/></label>)}</div><button type="button" onClick={()=>{setKpis(previous=>previous.filter((_,i)=>i!==index));setDirty(true)}}>Bỏ chỉ số {index+1}</button></div>)}<button type="button" disabled={kpis.length>=20} onClick={()=>{setKpis(previous=>[...previous,{name:'',target:null,unit:''}]);setDirty(true)}}>Thêm chỉ số mục tiêu</button><button type="submit">Lưu phiên bản hồ sơ</button></fieldset></form>
    {profile&&<details><summary>Lịch sử hồ sơ</summary><label>Phiên bản cần đọc<input aria-label="Phiên bản hồ sơ cần đọc" type="number" min={1} max={profile.current_revision} value={historyRevision} onChange={event=>setHistoryRevision(event.target.value)}/></label><button disabled={busy||unknown} onClick={()=>void work(async ticket=>{const old=await api<Profile>(base+'/profiles/'+profile.id+'/versions/'+historyRevision);if(ticket===epoch.current)setHistory(old)})}>Đọc phiên bản hồ sơ</button>{history&&<pre aria-label="Hồ sơ lịch sử">{JSON.stringify(history.content,null,2)}</pre>}</details>}
   </section></details>
   <section id="bp-plan" tabIndex={-1}><h2>2. Kế hoạch tháng — bản nháp</h2><p>Kế hoạch ghim hồ sơ và giữ lịch sử. Duyệt kế hoạch chỉ cho chuẩn bị công việc nháp, không phải quyền chạy AI hoặc quảng cáo.</p>
    {!profile?<p>Lưu hồ sơ trước khi soạn kế hoạch.</p>:<>
     <div className="bp-plan-list"><button disabled={busy||unknown} onClick={()=>{if(leave()){fillPlan(null);setDirty(false)}}}>Soạn kế hoạch mới</button>{plans.map(row=><button key={row.id} disabled={busy||unknown} onClick={()=>{if(!leave())return;void work(async ticket=>{const current=await api<Plan>(base+'/plans/'+row.id);if(ticket===epoch.current){fillPlan(current);setDirty(false)}})}}>{row.content.title} · v{row.revision}</button>)}</div>{more&&<p>Danh sách giới hạn; chưa phải toàn bộ kế hoạch.</p>}
     {plan&&<p>Phiên bản {plan.revision} · Hồ sơ nguồn v{plan.profile_revision} · {plan.profile_stale?'Hồ sơ đã thay đổi: đọc lại trước khi lưu phiên bản mới.':'Xem hiệu lực phê duyệt tại mục Duyệt kế hoạch; mở kế hoạch không cấp quyền chạy.'}</p>}
     <form onSubmit={savePlan}><fieldset disabled={busy||unknown} onChange={()=>setDirty(true)}><div className="bp-grid"><label>Tên kế hoạch<input aria-label="Tên kế hoạch tháng" required maxLength={200} value={title} onChange={event=>setTitle(event.target.value)}/></label><label>Tháng triển khai<input aria-label="Tháng triển khai" type="month" required value={month} onChange={event=>setMonth(event.target.value)}/></label></div><label>Brief chiến dịch<textarea aria-label="Brief chiến dịch" required maxLength={8000} rows={4} value={brief} onChange={event=>setBrief(event.target.value)}/></label>
      {items.map((item,index)=><article className="bp-deliverable" key={index}><h3>Đầu việc dự kiến {index+1}</h3><div className="bp-grid"><label>Mã đầu việc<input aria-label={'Mã đầu việc '+(index+1)} value={item.key} onChange={event=>changeItem(index,'key',event.target.value)}/></label><label>Chuyên môn<select aria-label={'Chuyên môn '+(index+1)} value={item.specialist} onChange={event=>changeItem(index,'specialist',event.target.value)}><option value="content">Nội dung</option><option value="creative">Sáng tạo</option><option value="ads">Quảng cáo</option><option value="analyst">Phân tích</option></select></label><label>Tên đầu việc<input aria-label={'Tên đầu việc '+(index+1)} required maxLength={200} value={item.title} onChange={event=>changeItem(index,'title',event.target.value)}/></label><label>Hạn hoàn thành<input aria-label={'Hạn đầu việc '+(index+1)} type="date" required value={item.due_date} onChange={event=>changeItem(index,'due_date',event.target.value)}/></label></div><label>Brief đầu việc<textarea aria-label={'Brief đầu việc '+(index+1)} required maxLength={4000} value={item.brief} onChange={event=>changeItem(index,'brief',event.target.value)}/></label><label>Tiêu chí nghiệm thu — mỗi dòng một mục<textarea aria-label={'Tiêu chí đầu việc '+(index+1)} value={item.acceptance} onChange={event=>changeItem(index,'acceptance',event.target.value)}/></label><fieldset className="bp-dependencies"><legend>Việc cần hoàn thành và duyệt trước</legend>{items.filter(other=>other.key!==item.key).length===0?<p>Chưa có đầu việc khác để chọn.</p>:items.filter(other=>other.key!==item.key).map(other=><label key={other.key}><input type="checkbox" aria-label={'Phụ thuộc '+(index+1)+' vào '+other.key} checked={item.depends_on.split(',').includes(other.key)} onChange={event=>changeItem(index,'depends_on',event.target.checked?[...item.depends_on.split(',').filter(Boolean),other.key].join(','):item.depends_on.split(',').filter(key=>key!==other.key).join(','))}/>{other.title||'Đầu việc chưa đặt tên'}</label>)}</fieldset><button type="button" onClick={()=>{setItems(previous=>previous.filter((_,i)=>i!==index));setDirty(true)}}>Bỏ đầu việc {index+1}</button></article>)}
      <button type="button" disabled={items.length>=50} onClick={()=>{setItems(previous=>[...previous,{key:'job_'+crypto.randomUUID().slice(0,8),title:'',specialist:'content',due_date:'',brief:'',acceptance:'',depends_on:''}]);setDirty(true)}}>Thêm đầu việc dự kiến</button><button type="submit" disabled={!items.length}>Lưu bản nháp kế hoạch</button>
     </fieldset></form>
    </>}
   </section>
   {plan&&<details><summary>Lịch sử và điều chỉnh kế hoạch</summary><p>Đọc phiên bản cũ không thay phiên bản đang vận hành. Công việc đã có lượt chạy không được gửi lại mù; nếu cần làm lại, nhân bản thành kế hoạch mới, rà nội dung và duyệt riêng. Không tự sao chép phê duyệt hoặc kết quả.</p><label>Phiên bản kế hoạch cần đọc<input aria-label="Phiên bản kế hoạch cần đọc" type="number" min={1} max={plan.revision} value={planHistoryRevision} onChange={e=>setPlanHistoryRevision(e.target.value)}/></label><button disabled={busy||unknown} onClick={()=>void work(async ticket=>{const old=await api<Plan>(base+'/plans/'+plan.id+'/versions/'+planHistoryRevision);if(ticket===epoch.current)setPlanHistory(old)})}>Đọc phiên bản kế hoạch</button>{planHistory&&<article aria-label="Kế hoạch lịch sử"><h3>{planHistory.content.title} · v{planHistory.revision}</h3><p>Hồ sơ nguồn v{planHistory.profile_revision} · {planHistory.content.month}</p><p>{planHistory.content.campaign_brief}</p><ul>{planHistory.content.deliverables.map(d=><li key={d.key}>{d.title} · {d.due_date} · {d.brief}</li>)}</ul></article>}<button disabled={busy||unknown||dirty||routingDirty||operationsDirty} onClick={clonePlan}>Nhân bản thành kế hoạch mới</button></details>}
   </SectionPanel>
   {!plan&&view!=='plan'&&<div className="bp-grid" aria-label="Các bước đang chờ kế hoạch"><p id="bp-review" tabIndex={-1}>Duyệt kế hoạch: lưu hoặc mở kế hoạch trước; chưa có phiên bản để duyệt.</p><p id="bp-run" tabIndex={-1}>Chạy AI: cần kế hoạch đã lưu, kỹ năng, model và phê duyệt riêng.</p><p id="bp-report" tabIndex={-1}>Báo cáo: mở kế hoạch để đọc dữ liệu vận hành; chưa có số liệu không có nghĩa bằng 0.</p></div>}
   <SectionPanel id="business-view" name="routing" active={view==='routing'}><BusinessRoutingPanel brandId={brand||null} key={wid+':'+brand} plan={plan} draftDirty={dirty} onDirty={setRoutingDirty} onSaved={setRoutingRevision}/></SectionPanel>
   <section role="tabpanel" id={['jobs','review','report'].includes(view)?'business-view-panel-'+view:'business-operations-inactive'} aria-labelledby={'business-view-tab-'+view} hidden={!['jobs','review','report'].includes(view)}><div hidden={view!=='review'}>{plan&&<BusinessPlanReviewPanel key={plan.id+':'+plan.revision} planId={plan.id} revision={plan.revision} contentHash={plan.content_hash} draftDirty={dirty} onChanged={reviewChanged}/>}</div>
   {plan&&<BusinessOperationsPanel view={view as 'jobs'|'review'|'report'} brandId={brand||null} key={wid+':'+plan.id+':'+plan.revision} plan={plan} draftDirty={dirty||routingDirty} onDirty={setOperationsDirty} refreshRevision={routingRevision+reviewRevision} onRework={()=>{clonePlan();setView('plan')}}/>}</section>
  </>}
 </div></PaoAppShell>;
}
