'use client';
import {useEffect,useRef,useState} from 'react';
import {Plug} from 'lucide-react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {agyPath,agyView,agyError,agySmoke,type AgyView} from '@/lib/antigravity-native.mjs';

export default function AntigravityConnect(){
 const {apiRaw,activeWorkspace,me}=usePao();
 const workspace=activeWorkspace?.id||'',actor=me?.id||'',manage=['owner','admin'].includes(activeWorkspace?.role||'');
 const [state,setState]=useState<AgyView|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [result,setResult]=useState('');
 const epoch=useRef(0),controller=useRef<AbortController|null>(null);
 useEffect(()=>{const ticket=++epoch.current;const abort=new AbortController();controller.current=abort;setState(null);setBusy(false);setError('');setResult('');
  if(manage&&workspace&&actor)void apiRaw(agyPath(workspace),{method:'GET',signal:abort.signal}).then(r=>r.json()).then(v=>{if(epoch.current===ticket)setState(agyView(v,workspace,actor))}).catch(()=>{});
  return()=>{epoch.current++;abort.abort()};
 },[workspace,actor,manage,apiRaw]);
 async function action(kind:'connect'|'disconnect'|'test'){
  if(busy||!manage||!workspace||!actor)return;
  if(kind==='connect'&&!window.confirm('Dùng Antigravity CLI đã đăng nhập trên máy cài PAO để đọc danh mục model? Không nhập lại mật khẩu PAO/Google. Google không hỗ trợ bọc CLI trong ứng dụng bên thứ ba dưới gói cá nhân; có rủi ro đình chỉ tài khoản. Lượt này chưa gửi prompt, chưa chạy AI hoặc bật công cụ.'))return;
  if(kind==='test'&&!window.confirm('Thử đúng một câu cố định bằng gemini-3.8-flash-low qua phiên Antigravity trên máy? Có thể dùng quota thuê bao nếu kiểm tra khóa công cụ đạt. Không gửi dữ liệu doanh nghiệp, không dùng API tính phí hoặc tự thử lại. Google không hỗ trợ consumer CLI wrapper; rủi ro tài khoản vẫn áp dụng.'))return;
  const ticket=epoch.current;setBusy(true);setError('');setResult('');
  try{
   const response=await apiRaw(agyPath(workspace,kind),{method:'POST',headers:{'Content-Type':'application/json'},
    body:kind!=='disconnect'?JSON.stringify({acknowledge_local_session:true,acknowledge_unsupported_consumer_wrapper:true,...(kind==='test'?{acknowledge_fixed_model_test:true}:{})}):undefined,
    signal:AbortSignal.any([controller.current!.signal,AbortSignal.timeout(40000)])});
   const raw=await response.json();
   if(kind==='test'){const value=agySmoke(raw,workspace,actor);if(epoch.current===ticket)setResult(value)}
   else {const value=agyView(raw,workspace,actor);if(epoch.current===ticket)setState(value)}
  }catch(reason){if(epoch.current===ticket){if(kind!=='test')setState(null);setError(agyError(reason instanceof Error?reason.message:''))}}
  finally{if(epoch.current===ticket)setBusy(false)}
 }
 return <div className="agy-native-connect">
  <button type="button" disabled={!manage||busy} onClick={()=>void action('connect')}><Plug size={15}/>{busy?'Đang kiểm tra…':state?.status==='catalog_available'?'Kiểm tra lại':'Kết nối'}</button>
  {state?.status==='catalog_available'?<><p role="status">Đã nhận Client · {state.models.length} model</p><details><summary>Danh sách model từ CLI</summary><ul>{state.models.map(model=><li key={model}>{model}</li>)}</ul></details><button type="button" disabled={busy} onClick={()=>void action('disconnect')}>Ngắt trong PAO</button></>:<small>Đọc phiên CLI có sẵn. Không yêu cầu nhập lại mật khẩu PAO.</small>}
  {state?.status==='catalog_available'&&<button type="button" disabled={busy||!manage} onClick={()=>void action('test')}>Thử model an toàn</button>}
  {result&&<p role="status">Câu thử trả về: {result}. Chưa bật hội thoại hoặc agent Antigravity.</p>}
  {error&&<p role="alert">{error}</p>}
  <details><summary>Hướng dẫn và giới hạn</summary><p>Client phải được cài và đăng nhập bằng đúng tài khoản Windows chạy backend PAO. Chỉ hồ sơ cá nhân local được quản trị máy cấp quyền mới kết nối; không tự chia sẻ phiên cho SME hoặc người dùng khác.</p><p>Kết nối chỉ đọc danh mục. Thử model là một lượt riêng, chỉ gửi câu cố định nếu CLI xác nhận không có công cụ trước khi nhận câu hỏi. Bản CLI hiện tại chưa đạt chốt này; PAO sẽ báo rõ thay vì tự bỏ qua. Chưa dùng Antigravity cho hội thoại PAO; danh mục không cho biết quota còn lại và không chứng minh nhà cung cấp hỗ trợ.</p><p>Nếu CLI chưa đăng nhập, mở Antigravity chính chủ để đăng nhập. Không dán token/API key vào đây. Ngắt chỉ xóa trạng thái PAO, không đăng xuất Antigravity/Javis; sau khi khởi động lại backend cần Kiểm tra lại. Khi CLI cập nhật, quản trị máy phải xác minh lại bản được phép.</p><a href="https://www.antigravity.google/docs/faq/" target="_blank" rel="noopener noreferrer">Giới hạn sử dụng theo Google</a></details>
 </div>;
}
