"use client";
import {useEffect,useState} from "react";
type Status={enabled:boolean;configured:boolean;mode:string;allowed_peers:number;delivery_issues:{id:string;status:string;error_code:string}[]};
export default function TelegramPanel({api}:{api:<T>(path:string)=>Promise<T>}) {
  const [open,setOpen]=useState(false);
  const [status,setStatus]=useState<Status|null>(null);
  const [error,setError]=useState("");
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    if(!open)return;
    let live=true;
    api<Status>("/v1/telegram/status").then(data=>{if(live){setStatus(data);setError("");}}).catch(e=>{if(live)setError(e.message);});
    return()=>{live=false;};
  },[api,open,retry]);
  return <details className="pao-telegram" onToggle={e=>setOpen(e.currentTarget.open)}><summary>Telegram</summary>
    {status && <>
      <p role="status">{!status.configured ? "Chưa cấu hình bot Telegram." : !status.enabled ? "Telegram đang tắt." : !status.allowed_peers ? "Tài khoản này chưa được liên kết Telegram." : "Đã bật cấu hình Telegram cho tài khoản này."}</p>
      <p>Telegram cho phép giao việc và nhận kết quả trong chat riêng với bot. Chỉ người dùng đã được cấp quyền mới sử dụng được.</p>
      {!status.configured && <p>Tạo bot qua BotFather, sau đó thiết lập token và người dùng được phép bằng công cụ cấu hình trên máy. Không gửi token vào hội thoại.</p>}
      {!!status.delivery_issues.length && <p role="alert">Có {status.delivery_issues.length} thông báo chưa xác định được kết quả gửi. Hãy kiểm tra chat Telegram và nhật ký trên máy trước khi gửi lại để tránh trùng.</p>}
      <p className="pao-muted">Trạng thái cấu hình không xác nhận bot đang kết nối. Hội thoại và kết quả vẫn được lưu trong PAO.</p>
    </>}
    {error && <p role="alert" className="pao-error">{error}</p>}
    <button onClick={()=>setRetry(n=>n+1)}>Kiểm tra Telegram</button>
  </details>;
}
