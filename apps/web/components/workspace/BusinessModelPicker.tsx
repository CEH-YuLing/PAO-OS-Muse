'use client';
import {useEffect,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {modelGrantEligible} from '@/lib/settings-navigation.mjs';
type Reference={id:string;workspace_id:string;kind:string;provider:string;manager_id:string;status:string;revision:number};
type Grant={id:string;workspace_id:string;reference_id:string;reference_revision:number;grantee_id:string;brand_id:string|null;status:string;expires_at:string;model_consent_recorded:boolean};
// Read metadata only. Selecting an option does not stage/activate/test a connection.
export default function BusinessModelPicker({mode,value,onChange,label,provider,brand=null}:{mode:'reference'|'grant';value:string;onChange:(value:string)=>void;label:string;provider?:string;brand?:string|null}){
 const {api,me,activeWorkspace}=usePao(),wid=activeWorkspace?.id||'',actor=me?.id||'';
 const [rows,setRows]=useState<{id:string;label:string}[]>([]),[state,setState]=useState('loading'),[revision,setRevision]=useState(0);
 useEffect(()=>{let live=true;setRows([]);setState('loading');
  const base=`/v1/workspaces/${wid}/connection-inventory`;
  async function pages<T>(path:string):Promise<T[]>{const result:T[]=[];for(let offset=0;offset<=10000;offset+=100){const page=await api<{items:T[];has_more:boolean}>(path+`?limit=100&offset=${offset}`);if(!live)return [];result.push(...page.items);if(!page.has_more)return result;}throw new Error('catalog_limit');}
  void (async()=>{try{const references=(await pages<Reference>(base+'/references')).filter(r=>r.workspace_id===wid&&r.manager_id===actor&&r.kind==='model'&&r.status==='staged'&&(!provider||r.provider===provider));
   let options:{id:string;label:string}[]=[];
   if(mode==='reference')options=references.map(r=>({id:r.id,label:`${r.provider} · kết nối ${r.id.slice(0,8)} · v${r.revision}`}));
   else for(const ref of references){const grants=await pages<Grant>(base+'/references/'+ref.id+'/grants');options.push(...grants.filter(g=>modelGrantEligible(g,ref,actor,wid,brand)).map(g=>({id:g.id,label:`${ref.provider} · ${g.brand_id?'Nhãn hàng đang chọn':'Toàn doanh nghiệp'} · hết hạn ${new Date(g.expires_at).toLocaleString('vi-VN')} · ${g.id.slice(0,8)}`})));}
   if(live){setRows(options);setState('ready');}
  }catch{if(live){setRows([]);setState('error');}}})();return()=>{live=false};
 },[api,wid,actor,mode,provider,brand,revision]);
 return <span className="bp-picker"><select aria-label={label} value={value} disabled={state!=='ready'} onChange={e=>onChange(e.target.value)}><option value="">{state==='loading'?'Đang đọc danh mục…':state==='error'?'Chưa đọc được danh mục':mode==='grant'?'Không dùng quyền đám mây (Ollama)':'Chọn kết nối đã đăng ký'}</option>{value&&!rows.some(r=>r.id===value)&&<option value={value}>Lựa chọn cũ — cần đọc lại và kiểm tra quyền</option>}{rows.map(r=><option key={r.id} value={r.id}>{r.label}</option>)}</select><small>{state==='error'?'Không suy ra chưa có kết nối. Kiểm tra quyền quản lý rồi đọc lại.':state==='ready'&&!rows.length?'Chưa có lựa chọn phù hợp trong danh mục của bạn.':'Danh mục chỉ hỗ trợ chọn; máy chủ kiểm tra lại toàn bộ quyền khi thực hiện.'} Không nhập khóa bí mật tại đây.</small><a href="/settings?tab=ai">Thiết lập model và quyền</a><button type="button" onClick={()=>setRevision(v=>v+1)}>Đọc lại danh mục</button></span>;
}
