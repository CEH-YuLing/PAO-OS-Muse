import {connectionEvidence,evidenceValue} from '@/lib/settings-status.mjs';

export default function ConnectionEvidence({kind,record}:{kind:string;record:{configured:boolean;status?:string}|null}){
  const value=connectionEvidence(kind,record);
  return <div className="st-readiness" aria-label={`Bằng chứng ${kind}`}>
    <small>Cấu hình: {evidenceValue(value.configured)} · Đã lưu kết nối: {evidenceValue(value.connected)}</small>
    <small>Hoạt động ổn định: {evidenceValue(value.healthy)} · Nghiệm thu thật: {evidenceValue(value.accepted)}</small>
    <small>{kind==='telegram'?'Đây là trạng thái Telegram cũ dùng chung máy chủ; xem bot theo doanh nghiệp trong phần thiết lập riêng.':'Trạng thái đã lưu kết nối không cấp quyền công cụ, tài khoản quảng cáo hoặc kho tri thức.'}</small>
  </div>;
}
