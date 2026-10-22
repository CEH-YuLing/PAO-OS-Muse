'use client';
import {Plug,ShieldCheck} from 'lucide-react';
import CodexConnect from './CodexConnect';
import AntigravityConnect from './AntigravityConnect';
import MuseConnect from './MuseConnect';
import './model-access.css';
import {clientProviders} from '@/lib/model-provider-tabs.mjs';

export default function ClientModelSettings({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){
 void onDraftChange;
 return <section className="mp-client-settings" aria-label="Kết nối Client AI">
  <header><h2>Kết nối qua Client</h2><p>Client chạy trên máy cài PAO, không yêu cầu máy người dùng chạy LLM. Kết nối đăng nhập và chọn model là hai việc riêng: mỗi hội thoại hoặc trợ lý có thể dùng lựa chọn khác nhau.</p></header>
  <div className="mp-client-grid">{clientProviders.map(provider=><article key={provider.id} aria-label={'Client '+provider.name}>
   <header><ShieldCheck size={18}/><h3>{provider.name}</h3></header>
   <p className="mp-client-detail">{provider.detail}</p>
   {provider.metadata?<CodexConnect/>:provider.id==='antigravity'?<AntigravityConnect/>:provider.id==='muse'?<MuseConnect/>:<><button type="button" aria-label={'Kết nối '+provider.name} disabled aria-describedby={'client-unavailable-'+provider.id}><Plug size={15}/>Kết nối</button><small id={'client-unavailable-'+provider.id}>Adapter của Client này chưa được triển khai.</small></>}
  </article>)}</div>
  <details><summary>Hướng dẫn và giới hạn kết nối Client</summary><p>Chọn Client → bấm Kết nối → nếu cần, đăng nhập trên trang chính thức của nhà cung cấp. Không dán token hoặc mật khẩu OpenAI/Claude/Google vào PAO.</p><p>Đã đăng nhập hoặc đọc được danh mục chưa có nghĩa model đã chạy được. Hạn mức, quyền dùng chung và khả năng công cụ phải được kiểm tra riêng. Hồ sơ cũ được giữ để bảo toàn lịch sử; PAO không tự chuyển phiên cá nhân thành tài nguyên dùng chung. Claude chưa có adapter được nghiệm thu; ngắt PAO không tự đăng xuất ứng dụng khác.</p></details>
 </section>;
}
