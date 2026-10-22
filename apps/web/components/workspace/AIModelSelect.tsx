'use client';
import {useEffect,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
export type AIModelPreference={provider:'openai'|'anthropic'|'gemini'|'openrouter'|'codex_cli'|'muse'|'ollama';model:string;installation_resource_id?:string;reasoning_effort?:string|null};
type Entry={provider:AIModelPreference['provider'];installation_resource_id?:string;error:string|null;models:string[];model_details?:{model:string;display_name:string;reasoning_efforts:string[];default_effort:string|null}[]};
const key=(v:AIModelPreference)=>JSON.stringify([v.provider,v.model,v.installation_resource_id||null]);
const labels:Record<string,string>={none:'Tắt suy luận tùy chọn',minimal:'Tối thiểu',low:'Thấp',medium:'Trung bình',high:'Cao',xhigh:'Rất cao',max:'Tối đa'};

export default function AIModelSelect({value,onChange,label='Model của agent',inherit=true}:{value:AIModelPreference|null;onChange:(value:AIModelPreference|null)=>void;label?:string;inherit?:boolean}){
 const {api,activeWorkspace:workspace}=usePao();
 const [rows,setRows]=useState<Entry[]>([]),[state,setState]=useState('loading'),[refresh,setRefresh]=useState(0);
 useEffect(()=>{let live=true;setRows([]);setState('loading');if(workspace?.id)void api<{engines:Entry[]}>(`/v1/engines?workspace_id=${workspace.id}`).then(result=>{if(live){setRows(result.engines.filter(row=>row.installation_resource_id&&!row.error));setState('ready')}}).catch(()=>{if(live)setState('error')});return()=>{live=false}},[api,workspace?.id,refresh]);
 const options=rows.flatMap(row=>row.models.map(model=>({provider:row.provider,model,installation_resource_id:row.installation_resource_id})));
 const detail=rows.find(row=>row.installation_resource_id===value?.installation_resource_id)?.model_details?.find(row=>row.model===value?.model);
 return <div className="ai-model-select"><label>{label}<select aria-label={label} disabled={state!=='ready'} value={value?key(value):''} onChange={event=>{const found=options.find(option=>key(option)===event.target.value);onChange(found||null)}}><option value="">{inherit?'Kế thừa model của hội thoại/công việc':'Chọn model đã kết nối'}</option>{value&&!options.some(option=>key(option)===key(value))&&<option value={key(value)}>Lựa chọn đã lưu · {value.provider} · {value.model} — cần kiểm tra lại</option>}{options.map(option=><option key={key(option)} value={key(option)}>{option.provider} · {option.model}</option>)}</select></label>
  {value?.installation_resource_id&&<label>Mức suy luận<select aria-label={label+' — mức suy luận'} disabled={!detail?.reasoning_efforts.length||state!=='ready'} value={value.reasoning_effort||''} onChange={event=>onChange({...value,reasoning_effort:event.target.value||null})}><option value="">Theo mặc định nhà cung cấp</option>{detail?.reasoning_efforts.map(level=><option key={level} value={level}>{labels[level]||level} · {level}</option>)}</select></label>}
  {value?.provider==='muse'&&<small>Muse chỉ tạo văn bản, có khoảng 14.000 token hướng dẫn native mỗi lần gọi. Lượt mới theo khả năng của mô hình, không có trần token PAO riêng. Model vẫn có hạn mức và cửa sổ ngữ cảnh của nhà cung cấp.</small>}
  <small>{state==='error'?'Chưa đọc được danh mục; không suy ra kết nối bị mất.':!options.length&&state==='ready'?'Chưa có model dùng chung sẵn sàng. Quản trị bản cài cần kết nối và bật tài nguyên AI.':'Lựa chọn được kiểm tra lại khi chạy; không cấp quyền công cụ hoặc đổi dữ liệu lịch sử.'}</small><button type="button" onClick={()=>setRefresh(v=>v+1)}>Đọc lại model</button>
 </div>;
}
