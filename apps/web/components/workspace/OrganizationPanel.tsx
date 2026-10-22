"use client";
import {FormEvent,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import './organization.css';

export type Brand={id:string;workspace_id:string;name:string;revision:number};
type Company={id:string;name:string;revision:number};
type Organization={enterprise:Company;brands:Brand[];has_more:boolean;can_create_enterprise:boolean;can_rename_enterprise:boolean;can_manage_brands:boolean};
export default function OrganizationPanel({view='all'}:{view?:'all'|'enterprise'|'brands'}){
 const runtime=usePao(),wid=runtime.activeWorkspace?.id||'';
 const [data,setData]=useState<Organization|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[unknown,setUnknown]=useState(false),[created,setCreated]=useState<Company|null>(null);
 const live=useRef(true),sequence=useRef(0);
 useEffect(()=>{live.current=true;return()=>{live.current=false;sequence.current++}},[]);
 async function load(){const seq=++sequence.current;setData(null);setError('');try{const next=await runtime.api<Organization>(`/v1/workspaces/${wid}/organization`);if(live.current&&seq===sequence.current){setData(next);setUnknown(false)}}catch{if(live.current)setError('Chưa đọc được doanh nghiệp. Kiểm tra quyền và thử đọc lại; không gửi lại yêu cầu tạo khi chưa rõ kết quả.')}}
 useEffect(()=>{if(wid)void load()},[wid,runtime.api]); // Scope changes remount this panel through PaoRuntimeProvider.
 async function change(event:FormEvent<HTMLFormElement>,path:string,extra:object={},enter=false){event.preventDefault();if(busy||unknown)return;const form=event.currentTarget,name=String(new FormData(form).get('name')||'').trim();if(!name)return;
  if(!window.confirm(enter?'Tạo doanh nghiệp độc lập do bạn sở hữu? Không sao chép nhân viên, kết nối, bộ nhớ hoặc quyền.':'Lưu tên trong doanh nghiệp đang chọn? Dữ liệu và lịch sử hiện có được giữ nguyên.'))return;
  setBusy(true);setError('');setNotice('');try{const value=await runtime.api<Company>(`/v1/workspaces/${wid}/organization${path}`,'POST',{name,request_key:crypto.randomUUID(),...extra});if(!live.current)return;form.reset();if(enter)setCreated(value);setNotice(enter?'Đã tạo doanh nghiệp riêng. Chọn “Chuyển sang doanh nghiệp mới” để làm việc.':'Đã lưu tên.');await runtime.refreshMemberships();if(live.current)await load()}catch{if(live.current){setUnknown(true);setError('Yêu cầu chưa được xác nhận hoặc bị từ chối. Đọc lại danh sách trước khi thao tác tiếp; không bấm tạo lại mù.')}}finally{if(live.current)setBusy(false)}
 }
 return <section className="org-panel" aria-label="Quản lý doanh nghiệp và nhãn hàng"><header><h2>Doanh nghiệp và nhãn hàng</h2><button onClick={()=>void load()} disabled={busy}>Đọc lại danh sách</button></header><p>Chọn đúng doanh nghiệp ở đầu trang. Tài khoản vẫn chỉ tham gia qua lời mời; tạo doanh nghiệp không mở đăng ký công khai. Không hỗ trợ xóa doanh nghiệp tại đây.</p>
 {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 {created&&<aside><strong>Doanh nghiệp mới: {created.name}</strong><button disabled={busy} onClick={async()=>{await runtime.refreshMemberships();if(live.current)await runtime.selectWorkspace(created.id)}}>Chuyển sang doanh nghiệp mới</button></aside>}
 {!data?<p role="status">Chưa tải được danh sách hoặc đang đọc…</p>:<>
 {view!=='brands'&&<div className="org-grid"><article><h3>{data.enterprise.name}</h3><p>Phiên bản quản lý {data.enterprise.revision}. Chỉ chủ doanh nghiệp được đổi tên và tạo doanh nghiệp mới.</p><NameForm label="Tên doanh nghiệp hiện tại" button="Lưu tên doanh nghiệp" initial={data.enterprise.name} disabled={busy||unknown||!data.can_rename_enterprise} submit={e=>void change(e,'/name',{expected_revision:data.enterprise.revision})}/></article>
 <article><h3>Tạo thêm doanh nghiệp</h3><p>Bạn là chủ của doanh nghiệp mới. Nhân viên, nhãn hàng, dữ liệu và kết nối bắt đầu riêng biệt, không kế thừa từ doanh nghiệp này. Tối đa 20 doanh nghiệp sở hữu, 10 lượt tạo mỗi giờ.</p><NameForm label="Tên doanh nghiệp mới" button="Tạo doanh nghiệp độc lập" disabled={busy||unknown||!data.can_create_enterprise} submit={e=>void change(e,'/enterprises',{},true)}/></article></div>}
 {view!=='enterprise'&&<><h3>Nhãn hàng thuộc {data.enterprise.name}</h3><p>Trong khu vực này, chủ doanh nghiệp và quản trị viên quản lý tên nhãn hàng; đổi tên không chuyển dữ liệu hoặc cấp thêm quyền. Hồ sơ chi tiết nằm ở Kho tri thức.</p>
 <NameForm label="Tên nhãn hàng mới" button="Tạo nhãn hàng" disabled={busy||unknown||!data.can_manage_brands} submit={e=>void change(e,'/brands')}/>
 {!data.brands.length&&<p>Chưa có nhãn hàng. Tạo tên trước, sau đó bổ sung sản phẩm, khách hàng và giọng thương hiệu ở Kho tri thức.</p>}
 <div className="org-grid">{data.brands.map(b=><article key={b.id}><NameForm key={b.name+':'+b.revision} label={`Tên nhãn hàng ${b.name}`} initial={b.name} button="Lưu tên nhãn hàng" disabled={busy||unknown||!data.can_manage_brands} submit={e=>void change(e,`/brands/${b.id}/name`,{expected_revision:b.revision})}/><small>Phiên bản tên {b.revision}</small></article>)}</div>{data.has_more&&<p role="status">Danh sách giới hạn 100 nhãn hàng. Liên hệ quản trị vận hành để xử lý phần còn lại.</p>}
 </>}
 </>}
 <nav aria-label="Quản lý liên quan"><a href="/knowledge?tab=enterprise">Hồ sơ doanh nghiệp</a><a href="/knowledge?tab=brands">Hồ sơ nhãn hàng</a><a href="/settings?tab=team&section=members">Nhân viên và lời mời</a><a href="/settings?tab=integrations">Kết nối và quyền</a></nav></section>
}
function NameForm({label,button,initial='',disabled,submit}:{label:string;button:string;initial?:string;disabled:boolean;submit:(event:FormEvent<HTMLFormElement>)=>void}){return <form onSubmit={submit}><label>{label}<input name="name" required maxLength={120} defaultValue={initial} disabled={disabled}/></label><button disabled={disabled}>{button}</button></form>}
