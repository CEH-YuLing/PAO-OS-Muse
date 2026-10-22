"use client";
import {useState} from 'react';
import Link from 'next/link';
import {usePao} from '@/lib/PaoRuntimeContext';
import './lifecycle.css';

type Member={id:string;email:string;role:string};
type Invitation={id:string;email:string;role:string;status:string;expired:boolean;expires_at:string};
type LoginSession={id:string;current:boolean;revoked:boolean;created_at:string;expires_at:string};
type DataRequest={id:string;kind:string;status:string;preview_hash:string;expires_at:string;summary:Record<string,unknown>};
const ROLES=[['viewer','Người xem'],['analyst','Người phân tích'],['operator','Người thực thi'],['admin','Quản trị viên']];
function role(value:string){return value==='owner'?'Chủ doanh nghiệp':ROLES.find(row=>row[0]===value)?.[1]||value}
function state(value:string){return ({pending:'Chờ nhận',accepted:'Đã nhận',revoked:'Đã thu hồi',ready:'Sẵn sàng tải',preview:'Bản xem trước',requested:'Đã yêu cầu',confirmed:'Đã xác nhận, chưa xóa'} as Record<string,string>)[value]||value}
function collectionLabel(value:string){return ({brands:'Nhãn hàng',projects:'Dự án',goals:'Mục tiêu',tasks:'Công việc',business_profiles:'Hồ sơ doanh nghiệp',business_profile_versions:'Phiên bản hồ sơ',monthly_plans:'Kế hoạch tháng',monthly_plan_versions:'Phiên bản kế hoạch',business_jobs:'Công việc AI',business_budgets:'Ngân sách mô phỏng',business_actions:'Hành động',business_reports:'Báo cáo'} as Record<string,string>)[value]||(value.startsWith('brain:')?'Kho tri thức đã chọn':value)}

export default function LifecyclePanel({view='all'}:{view?:'all'|'account'|'members'|'invitations'|'exports'|'deletions'}){
 const runtime=usePao(),workspace=runtime.activeWorkspace?.id||'',owning=runtime.activeWorkspace?.role==='owner';
 const base=`/v1/workspaces/${workspace}/lifecycle`;
 const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
 const [members,setMembers]=useState<Member[]>([]),[invitations,setInvitations]=useState<Invitation[]>([]),[sessions,setSessions]=useState<LoginSession[]>([]);
 const [email,setEmail]=useState(''),[newRole,setNewRole]=useState('viewer'),[code,setCode]=useState('');
 const [offset,setOffset]=useState(0),[more,setMore]=useState(false),[inviteOffset,setInviteOffset]=useState(0),[inviteMore,setInviteMore]=useState(false);
 const [brains,setBrains]=useState<{id:string;name:string}[]>([]),[selected,setSelected]=useState<string[]>([]),[includeBusiness,setIncludeBusiness]=useState(true);
 const [requests,setRequests]=useState<DataRequest[]>([]),[preview,setPreview]=useState<DataRequest|null>(null);
 async function work(action:()=>Promise<void>){if(busy)return;setBusy(true);setError('');setNotice('');try{await action()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function loadMembers(next=0){const value=await runtime.api<{members:Member[];has_more:boolean}>(base+`/members?offset=${next}`);setMembers(value.members);setOffset(next);setMore(value.has_more)}
 async function loadInvites(next=0){const value=await runtime.api<{invitations:Invitation[];has_more:boolean}>(base+`/invitations?offset=${next}`);setInvitations(value.invitations);setInviteOffset(next);setInviteMore(value.has_more)}
 async function loadSessions(){const value=await runtime.api<{sessions:LoginSession[]}>('/v1/auth/sessions');setSessions(value.sessions)}
 const scope={include_business:includeBusiness,brain_ids:selected};
 return <section className="lc-panel" aria-label="Quản lý tài khoản và dữ liệu SaaS">
  <h2>{({account:"Phiên đăng nhập của tôi",members:"Thành viên doanh nghiệp",invitations:"Lời mời tham gia",exports:"Xuất dữ liệu doanh nghiệp",deletions:"Yêu cầu xóa dữ liệu",all:"Tài khoản, nhân viên và dữ liệu"})[view]}</h2>
  <p>Doanh nghiệp: <strong>{runtime.activeWorkspace?.name}</strong>. Chủ doanh nghiệp quản lý thành viên và yêu cầu dữ liệu; mỗi người tự quản lý phiên của mình. Không gửi khóa hoặc mã mời trong chat với AI.</p>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {(view==='all'||view==='account')&&<fieldset disabled={busy}><legend>Phiên đăng nhập của bạn</legend>
   <p>Thu hồi một phiên sẽ chặn token của phiên đó trên máy chủ. Đăng xuất tất cả ảnh hưởng tài khoản của bạn ở mọi doanh nghiệp, không xóa thành viên hoặc dữ liệu. Công việc đã được chấp nhận vẫn chịu kiểm tra quyền nghiệp vụ; logout không phải lệnh hủy công việc.</p>
   <div className="lc-actions"><button onClick={()=>void work(loadSessions)}>Đọc phiên đăng nhập</button><button onClick={()=>void runtime.logout()}>Đăng xuất phiên hiện tại</button>
    <button onClick={()=>{if(window.confirm('Đăng xuất mọi phiên của bạn trên tất cả doanh nghiệp?'))void work(()=>runtime.logoutAll())}}>Đăng xuất tất cả phiên</button></div>
   <ul>{sessions.map(row=><li key={row.id}><span>{row.current?'Phiên hiện tại':'Phiên khác'} · {row.revoked?'Đã thu hồi':'Còn hiệu lực'} · hết hạn {new Date(row.expires_at).toLocaleString('vi-VN')}</span>
    {!row.revoked&&<button onClick={()=>{if(window.confirm('Thu hồi phiên này?'))void work(async()=>{if(row.current)await runtime.logout();else{await runtime.api(`/v1/auth/sessions/${row.id}/revoke`,'POST');await loadSessions()}})}}>Thu hồi phiên</button>}</li>)}</ul>
  </fieldset>}
  <p>Đã có mã mời vào doanh nghiệp khác? <Link href="/join">Nhận lời mời</Link>. Chỉ chuyển mã qua kênh riêng tin cậy; PAO không tự gửi email hoặc Telegram.</p>
  {owning?<>
   {(view==='all'||view==='invitations')&&<fieldset disabled={busy}><legend>Mời nhân viên</legend><p>Mã có hiệu lực 24 giờ, dùng một lần và chỉ hiển thị khi tạo. Nếu mất mã, thu hồi rồi tạo lại. Không thể mời vai trò chủ doanh nghiệp ở đây.</p>
    <form onSubmit={e=>{e.preventDefault();void work(async()=>{setCode('');const value=await runtime.api<{code:string}>(base+'/invitations','POST',{email,role:newRole,hours:24});setCode(value.code);setEmail('');await loadInvites();setNotice('Đã tạo mã mời; chưa gửi cho người nhận.')})}}>
     <label>Email người nhận<input type="email" autoComplete="off" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/></label>
     <label>Vai trò<select value={newRole} onChange={e=>setNewRole(e.target.value)}>{ROLES.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><button>Tạo mã mời</button>
    </form>
    {code&&<div><label>Mã mời — chỉ hiển thị lần này<textarea readOnly autoComplete="off" value={code}/></label><button onClick={()=>setCode('')}>Ẩn mã sau khi đã lưu riêng</button></div>}
    <div className="lc-actions"><button onClick={()=>void work(()=>loadInvites())}>Đọc danh sách lời mời</button><button disabled={!inviteOffset} onClick={()=>void work(()=>loadInvites(inviteOffset-100))}>Lời mời trước</button><button disabled={!inviteMore} onClick={()=>void work(()=>loadInvites(inviteOffset+100))}>Lời mời tiếp</button></div>
    <ul>{invitations.map(row=><li key={row.id}><span>{row.email} · {role(row.role)} · {row.expired?'Đã hết hạn':state(row.status)}</span>{row.status==='pending'&&<button onClick={()=>void work(async()=>{await runtime.api(base+`/invitations/${row.id}/revoke`,'POST');await loadInvites(inviteOffset)})}>Thu hồi lời mời</button>}</li>)}</ul>
   </fieldset>}
   {(view==='all'||view==='members')&&<fieldset disabled={busy}><legend>Thành viên doanh nghiệp</legend><p>Đổi vai trò sẽ thu hồi các cấp quyền kết nối/Brain và kênh cũ của người đó trong doanh nghiệp này để cấp lại rõ ràng. Gỡ thành viên không khóa tài khoản ở doanh nghiệp khác; không có chuyển chủ tại đây.</p>
    <div className="lc-actions"><button onClick={()=>void work(()=>loadMembers())}>Đọc thành viên</button><button disabled={!offset} onClick={()=>void work(()=>loadMembers(offset-100))}>Trang trước</button><button disabled={!more} onClick={()=>void work(()=>loadMembers(offset+100))}>Trang tiếp</button></div>
    <ul>{members.map(row=><li key={row.id}><span>{row.email} · {role(row.role)}</span>{row.role!=='owner'&&<>
     <label>Đổi vai trò<select value={row.role} onChange={e=>{const next=e.target.value;if(window.confirm(`Đổi vai trò và thu hồi cấp quyền cũ của ${row.email} trong doanh nghiệp này?`))void work(async()=>{await runtime.api(base+`/members/${row.id}`,'PATCH',{role:next});await loadMembers(offset)})}}>{ROLES.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
     <button onClick={()=>{if(window.confirm(`Gỡ ${row.email} khỏi doanh nghiệp này? Công việc đang chạy sẽ được yêu cầu dừng; dữ liệu và quyền tại doanh nghiệp khác được giữ.`))void work(async()=>{await runtime.api(base+`/members/${row.id}/remove`,'POST',{confirm:true});await loadMembers(offset)})}}>Gỡ khỏi doanh nghiệp</button>
    </>}</li>)}</ul>
   </fieldset>}
   {(view==='all'||view==='exports'||view==='deletions')&&<fieldset disabled={busy}><legend>{view==='exports'?'Xuất dữ liệu':view==='deletions'?'Phạm vi yêu cầu xóa':'Xuất dữ liệu và yêu cầu xóa'}</legend><p>Bản xuất theo danh mục có giới hạn 2.000 bản ghi/2 MiB, không phải dump database toàn hệ thống. Loại trừ thông tin xác thực hệ thống, ciphertext kết nối, chat riêng và audit/backup. Brain được chọn gồm ghi chú và file mã hóa base64; Brain lớn dùng xuất Brain riêng. Quyền được kiểm lại lúc tải, bản tải hết hạn sau 15 phút.</p>
    <label><input type="checkbox" checked={includeBusiness} onChange={e=>{setIncludeBusiness(e.target.checked);setPreview(null)}}/> Hồ sơ và dữ liệu nghiệp vụ trong danh mục</label>
    <button onClick={()=>void work(async()=>setBrains(await runtime.api<{id:string;name:string}[]>(`/v1/brains?workspace_id=${workspace}`)))}>Đọc Brain được cấp quyền</button>
    <div>{brains.map(brain=><label key={brain.id}><input type="checkbox" checked={selected.includes(brain.id)} onChange={e=>{setSelected(old=>e.target.checked?[...old,brain.id]:old.filter(id=>id!==brain.id));setPreview(null)}}/>{brain.name}</label>)}</div>
    <div className="lc-actions">{view!=='deletions'&&<button onClick={()=>void work(async()=>{const value=await runtime.api<DataRequest>(base+'/data/exports','POST',scope);await runtime.download(base+`/data/exports/${value.id}/download`,`pao-export-${value.id}.json`);setNotice('Đã tạo và tải bản xuất riêng tư; bản lưu có thời hạn tải, không được tự xóa.')})}>Tạo và tải bản xuất</button>}
     {view!=='exports'&&<button onClick={()=>void work(async()=>setPreview(await runtime.api<DataRequest>(base+'/data/deletions/preview','POST',scope)))}>Xem trước phạm vi yêu cầu xóa</button>}</div>
    {view!=='exports'&&preview&&<section aria-label="Bản xem trước yêu cầu xóa"><p>Trạng thái: {state(preview.status)}. Chỉ yêu cầu đối với phạm vi trong bản xem trước; chưa xóa bất kỳ dữ liệu nào. Dữ liệu thay đổi hoặc hết hạn thì cần xem trước lại.</p>
     <dl>{Object.entries((preview.summary.collections||{}) as Record<string,number>).map(([name,count])=><div key={name}><dt>{collectionLabel(name)}</dt><dd>{count} bản ghi</dd></div>)}</dl>
     <p>Không nằm trong phạm vi:</p><ul>{((preview.summary.exclusions||[]) as string[]).map((item,index)=><li key={index}>{item}</li>)}</ul>
     {preview.status==='preview'&&<button onClick={()=>{if(window.confirm('Tạo yêu cầu từ bản xem trước này? Thao tác chưa xóa dữ liệu.'))void work(async()=>setPreview(await runtime.api<DataRequest>(base+`/data/deletions/${preview.id}/request`,'POST',{confirm:true,preview_hash:preview.preview_hash})))}}>Tạo yêu cầu — chưa xóa</button>}
     {preview.status==='requested'&&<button onClick={()=>{if(window.confirm('Xác nhận riêng yêu cầu này để quản trị xem xét? Vẫn chưa thực thi xóa.'))void work(async()=>setPreview(await runtime.api<DataRequest>(base+`/data/deletions/${preview.id}/confirm`,'POST',{confirm:true,preview_hash:preview.preview_hash})))}}>Xác nhận yêu cầu — không tự xóa</button>}</section>}
    <button onClick={()=>void work(async()=>setRequests((await runtime.api<{requests:DataRequest[]}>(base+'/data/requests')).requests))}>Đọc lịch sử yêu cầu của tôi</button>
    <ul>{requests.filter(row=>view==='all'||row.kind===(view==='exports'?'export':'deletion')).map(row=><li key={row.id}><span>{row.kind==='export'?'Bản xuất':'Yêu cầu xóa'} · {state(row.status)} · {new Date(row.expires_at).toLocaleString('vi-VN')}</span>{row.kind==='export'&&new Date(row.expires_at)>new Date()&&<button onClick={()=>void work(()=>runtime.download(base+`/data/exports/${row.id}/download`,`pao-export-${row.id}.json`))}>Tải lại</button>}</li>)}</ul>
    <p>Không bật job tự xóa. Xác nhận yêu cầu không đồng nghĩa xóa thật; audit bất biến, backup, công việc đang chạy và hành động chưa rõ kết quả cần quản trị kiểm tra riêng.</p>
   </fieldset>}
  </>:<p>Chỉ chủ doanh nghiệp được quản lý lời mời, thành viên và yêu cầu dữ liệu. Vai trò hiện tại của bạn: {role(runtime.activeWorkspace?.role||'')}.</p>}
 </section>;
}
