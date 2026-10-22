'use client';
import {useEffect,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {museStatus,type MuseView} from '@/lib/muse-client.mjs';
import {chatEffortLabels} from '@/lib/chat-model-catalog.mjs';

/** Metadata only: no radio value, model selection or implicit connection. */
export default function MuseCatalogPreview({query}:{query:string}){
 const {apiRaw,activeWorkspace:workspace}=usePao(),[view,setView]=useState<MuseView|null>(null),[error,setError]=useState(false);
 useEffect(()=>{let live=true;const controller=new AbortController();setView(null);setError(false);
  if(workspace?.id)void apiRaw(`/v1/muse-client?workspace_id=${workspace.id}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])})
   .then(response=>response.json()).then(value=>{if(live)setView(museStatus(value))})
   .catch(()=>{if(live&&!controller.signal.aborted)setError(true)});
  return()=>{live=false;controller.abort()};
 },[apiRaw,workspace?.id]);
 const rows=view?.models.filter(row=>`${row.model} ${row.display_name}`.toLocaleLowerCase('vi').includes(query.trim().toLocaleLowerCase('vi')))||[];
 return <div className="pao-catalog-model-list" aria-label="Danh mục Muse chỉ xem">
  {!view&&!error&&<p role="status">Đang đọc danh mục Muse đã lưu…</p>}
  {error&&<p>Chưa tải được danh mục Muse.</p>}
  {view?.connected&&rows.map(row=><div className="pao-catalog-model is-unavailable" key={row.model}><span><strong>{row.display_name}</strong><small>{row.reasoning_efforts.map(value=>chatEffortLabels[value]||value).join(' · ')}</small></span></div>)}
  {view&&(!view.connected||!rows.length)&&<p>{view.connected?'Không có model khớp tìm kiếm.':'Chưa kết nối danh mục Muse.'}</p>}
  <p>Chưa bật chọn Muse cho hội thoại: bộ chạy cần hoàn tất kiểm tra cách ly công cụ/ngữ cảnh. Đọc được model không chứng minh còn quota.</p>
  <a href={`/settings?tab=ai&section=providers&model_connection=client&sme=${encodeURIComponent(workspace?.id||'')}`}>Kiểm tra kết nối Muse</a>
 </div>;
}
