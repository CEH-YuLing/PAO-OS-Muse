'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
type Admission={id:string;project_id:string;goal_id:string;tasks:{key:string;task_id:string}[];execution_enabled:boolean};
type Review={id?:string;status:string;effective:boolean;expires_at?:string;admission_id?:string|null;admission?:Admission|null};

export default function BusinessPlanReviewPanel({planId,revision,contentHash,draftDirty,onChanged}:{planId:string;revision:number;contentHash:string;draftDirty:boolean;onChanged:()=>void}){
 const {api,activeWorkspace:member}=usePao(),base=`/v1/workspaces/${member?.id||''}/business-planning/plans/${planId}`;
 const epoch=useRef(0),lock=useRef(false),key=useRef('');
 const [data,setData]=useState<Review|null>(null),[busy,setBusy]=useState(false),[unknown,setUnknown]=useState(false),[error,setError]=useState('');
 const [self,setSelf]=useState(false),[missing,setMissing]=useState(false),[drafts,setDrafts]=useState(false);
 const load=useCallback(async()=>{if(lock.current)return;lock.current=true;const ticket=++epoch.current;setData(null);setBusy(true);setError('');setSelf(false);setMissing(false);setDrafts(false);key.current='';
  try{const row=await api<Review>(base+'/review');if(ticket===epoch.current){setData(row);setUnknown(false);onChanged()}}catch{if(ticket===epoch.current){setUnknown(true);setError('Chưa đọc được phê duyệt. Không tự suy ra đã duyệt hoặc chưa thực hiện.')}}finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[api,base,onChanged]);
 useEffect(()=>{const e=epoch,l=lock;void load();return()=>{e.current++;l.current=false}},[load]);
 async function act(action:'approve'|'reject'|'materialize'){
  if(lock.current||unknown||draftDirty||!data||member?.role!=='owner')return;
  if(!window.confirm(action==='materialize'?'Tạo Project/Goal/Task ở trạng thái nháp từ đúng phiên bản đã duyệt? Chưa giao AI, không tạo lượt chạy hoặc chi tiền.':action==='approve'?'Duyệt phiên bản này để chuẩn bị công việc nội bộ? Không cấp quyền đăng bài, chạy AI hoặc quảng cáo.':'Từ chối phiên bản này? Muốn duyệt lại phải lưu phiên bản kế hoạch mới.'))return;
  lock.current=true;const ticket=++epoch.current;setBusy(true);setError('');key.current ||=crypto.randomUUID();
  try{
   if(action==='materialize'){
    await api<Admission>(base+'/materialize','POST',{request_key:key.current,revision,review_id:data.id,content_hash:contentHash,confirm_drafts_only:drafts});
   }else await api<Review>(base+'/review','POST',{request_key:key.current,revision,content_hash:contentHash,decision:action,self_review:self,acknowledge_missing:missing,expiry_hours:168});
   if(ticket!==epoch.current)return;const row=await api<Review>(base+'/review');if(ticket===epoch.current){setData(row);key.current='';setSelf(false);setMissing(false);setDrafts(false);onChanged()}
  }catch{if(ticket===epoch.current){setUnknown(true);setData(null);setError('Kết quả chưa được xác nhận. Không tự gửi lại; bấm Đọc lại phê duyệt để đối soát phiên bản và công việc đã tạo.')}}finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 }
 return <section id="bp-review" tabIndex={-1} aria-label="Duyệt kế hoạch và chuẩn bị công việc"><h2>4. Duyệt và chuẩn bị công việc</h2><p>Duyệt chỉ cho chuẩn bị bản nháp nội bộ. Phê duyệt nội dung và hành động bên ngoài là các bước riêng. Sửa kế hoạch/hồ sơ hoặc mất quyền người duyệt làm mất hiệu lực phê duyệt cũ; không sửa ngầm công việc lịch sử.</p>
  <button disabled={busy} onClick={()=>void load()}>Đọc lại phê duyệt</button>
  {data&&<p role="status">{data.status==='not_requested'?'Chưa có quyết định':data.status==='reject'?'Đã từ chối':data.effective?'Đã duyệt cho chuẩn bị nội bộ':'Quyết định cũ không còn hiệu lực'}{data.expires_at?' · Hết hạn '+new Date(data.expires_at).toLocaleString('vi-VN'):''}</p>}
  {error&&<p role="alert">{error}</p>}
  {draftDirty&&<p role="note">Có thay đổi chưa lưu. Lưu hoặc đọc lại bản nháp trước khi phê duyệt; quyết định chỉ áp dụng cho phiên bản đã lưu.</p>}
  {member?.role==='owner'?<fieldset disabled={busy||unknown||draftDirty||!data}>
   {data?.status==='not_requested'&&<><label><input type="checkbox" aria-label="Xác nhận tự duyệt kế hoạch" checked={self} onChange={event=>setSelf(event.target.checked)}/>Tôi xác nhận việc tự duyệt nếu chính tôi soạn phiên bản này.</label><label><input type="checkbox" aria-label="Xác nhận dữ liệu kế hoạch còn thiếu" checked={missing} onChange={event=>setMissing(event.target.checked)}/>Tôi đã kiểm tra những dữ liệu còn thiếu; duyệt chuẩn bị nội bộ không có nghĩa đã đủ điều kiện chạy thật.</label><button disabled={!self||!missing} onClick={()=>void act('approve')}>Duyệt chuẩn bị nội bộ</button><button disabled={!self} onClick={()=>void act('reject')}>Từ chối phiên bản kế hoạch</button></>}
   {data?.effective&&!data.admission_id&&<><label><input type="checkbox" aria-label="Xác nhận chỉ tạo công việc nháp" checked={drafts} onChange={event=>setDrafts(event.target.checked)}/>Chỉ tạo công việc nháp, chưa phân công và không tự thực thi.</label><button disabled={!drafts} onClick={()=>void act('materialize')}>Tạo công việc nháp từ kế hoạch</button></>}
  </fieldset>:<p>Chủ doanh nghiệp là người phê duyệt mặc định. Vai trò quản trị viên không tự có quyền duyệt hoặc chi tiền.</p>}
  {data?.admission&&<div aria-label="Công việc đã tạo từ kế hoạch"><p>Đã tạo {data.admission.tasks.length} công việc nháp. Chưa có model run hoặc quyền thực thi bên ngoài.</p><a href="/tasks">Mở bảng công việc</a><ul>{data.admission.tasks.map(task=><li key={task.task_id}>{task.key} · {task.task_id}</li>)}</ul></div>}
 </section>;
}
