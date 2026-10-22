'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {telegramConnections,telegramTeam,pairingCommand,telegramError,telegramState,type TelegramConnections,type TelegramTeam} from '@/lib/telegram-settings.mjs';
import './telegram-settings.css';

export default function TelegramSettings(){
 const {apiRaw,activeWorkspace:member}=usePao(),workspace=member?.id||'';
 const [data,setData]=useState<TelegramConnections|null>(null),[team,setTeam]=useState<TelegramTeam|null>(null),[selected,setSelected]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[ack,setAck]=useState(false),[command,setCommand]=useState('');
 const token=useRef<HTMLInputElement>(null),createToken=useRef<HTMLInputElement>(null),bot=useRef<HTMLInputElement>(null),identityBot=useRef<HTMLInputElement>(null),tgid=useRef<HTMLInputElement>(null),brain=useRef<HTMLInputElement>(null);
 const epoch=useRef(0),locked=useRef(false),abort=useRef<AbortController|null>(null),choice=useRef('');
 const clear=useCallback(()=>{if(token.current)token.current.value='';if(createToken.current)createToken.current.value='';setAck(false);setCommand('')},[]);
 const load=useCallback(async(id=choice.current)=>{
  if(locked.current||!workspace)return;locked.current=true;const turn=++epoch.current,c=new AbortController();abort.current=c;setBusy(true);setData(null);setTeam(null);setError('');clear();
  try{
   const signal=AbortSignal.any([c.signal,AbortSignal.timeout(15000)]),result=telegramConnections(await (await apiRaw('/v1/telegram/scoped?workspace_id='+workspace,{signal})).json(),workspace);
   const found=result.connections.some(row=>row.id===id);let people:TelegramTeam|null=null;
   if(found&&result.can_pair)people=telegramTeam(await (await apiRaw('/v1/telegram/scoped/'+id+'/team',{signal})).json());
   if(turn!==epoch.current||c.signal.aborted)return;setData(result);setTeam(people);if(!found){choice.current='';setSelected('')}
  }catch{if(turn===epoch.current)setError(telegramError())}
  finally{if(turn===epoch.current){locked.current=false;setBusy(false)}}
 },[apiRaw,workspace,clear]);
 useEffect(()=>{const e=epoch,a=abort,l=locked;void load();return()=>{e.current++;a.current?.abort();l.current=false}},[load]);
 useEffect(()=>{const hide=()=>{if(document.hidden)clear()};document.addEventListener('visibilitychange',hide);window.addEventListener('pagehide',clear);return()=>{document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',clear)}},[clear]);
 useEffect(()=>{if(!command)return;const timer=setTimeout(()=>setCommand(''),600000);return()=>clearTimeout(timer)},[command]);
 const connection=data?.connections.find(row=>row.id===selected),admin=!!data?.can_manage,available=!!data?.runtime_available;
 async function write(path:string,body:object,kind='change'){
  if(locked.current||!data)return;if(kind!=='pairing'&&!ack)return;
  locked.current=true;const turn=++epoch.current,c=new AbortController();abort.current=c;setBusy(true);setError('');setNotice('');clear();setData(null);setTeam(null);
  let success=false;
  try{
   const response=await apiRaw(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.any([c.signal,AbortSignal.timeout(35000)])});
   const result=await response.json();if(turn!==epoch.current||c.signal.aborted)return;
   if(kind==='pairing')setCommand(pairingCommand(result));
   else if(kind==='test')setNotice('Đã kiểm tra danh tính bot bằng getMe. Chưa nghiệm thu gửi/nhận thật.');
   else setNotice('Thao tác đã được server xác nhận. Đọc lại trạng thái trước khi thực hiện bước tiếp theo. Không tự bật bot hoặc cấp thêm quyền.');
   success=true;
  }catch(e){if(turn===epoch.current)setError(telegramError(e instanceof Error?e.message:undefined))}
  finally{if(turn===epoch.current){locked.current=false;setBusy(false)}}
  // Manual refresh is deliberate: a lost response may have committed. Never
  // auto retry writes or show a stale generation as current authority.
  if(success&&kind==='pairing')setNotice('Mã chỉ hiển thị lần này trong 10 phút. Gửi tới đúng bot, sau đó đọc lại và xác nhận trong PAO. Chưa có quyền điều khiển.');
 }
 const base='/v1/telegram/scoped/'+selected;
 const control=(action:string)=>void write(base+'/control',{action,generation:connection?.generation,request_key:crypto.randomUUID(),consent:true},action==='test'?'test':'change');
 return <section className="tg-settings" aria-label="Thiết lập Telegram doanh nghiệp" data-testid="telegram-settings">
  <header><h2>Telegram của doanh nghiệp · {member?.name}</h2><button type="button" disabled={busy} onClick={()=>void load()}>Đọc lại Telegram</button></header>
  <p>Mỗi bot thuộc đúng một doanh nghiệp; doanh nghiệp có thể có nhiều bot. Mỗi nhân viên liên kết tài khoản của mình, sau đó được quản trị viên cấp quyền riêng. Nhận báo cáo không tự có quyền giao việc, dùng công cụ hoặc phê duyệt.</p>
  <details><summary>Hướng dẫn cài đặt và an toàn</summary><ol>
   <li>Chủ doanh nghiệp hoặc quản trị viên tạo bot trong <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">BotFather chính thức</a> bằng /newbot. ID bot là phần số trước dấu hai chấm trong token. Không nhập App ID/Secret Facebook vào đây.</li>
   <li>Nhập ID bot và token để xác minh quyền sở hữu qua getMe trước khi tạo kết nối. Bước này chưa lưu token hoặc bật bot. Sau đó chọn bot, nhập token trong ô bí mật rồi lưu mã hóa; lưu không gọi Telegram.</li>
   <li>Xác nhận kiểm tra danh tính để gọi getMe. Chọn lấy tin định kỳ khi chạy local; webhook cần máy chủ HTTPS đã cấu hình. Đổi chế độ gọi Telegram nhưng luôn giữ kết nối tắt.</li>
   <li>Bật xử lý chỉ sau kiểm tra và xác nhận. Nhân viên nhập Telegram user ID dạng số và tùy chọn mã kho tri thức được phép; gửi mã một lần tới đúng bot rồi quay lại PAO xác nhận. Không chuyển tiếp mã.</li>
   <li>Quản trị viên xác nhận đúng người/đích nhận và cấp riêng quyền giao việc hoặc nhận báo cáo. Quyền PAO vẫn kiểm lại khi chạy và trước gửi; tên người dùng và quản trị nhóm Telegram không cấp quyền.</li>
  </ol><p>Chỉ hỗ trợ hội thoại riêng; chưa cấp quyền nhóm hoặc phê duyệt nhạy cảm qua bot. Quyền model không cấp quyền công cụ. Không nhập khóa qua chat hỗ trợ. Lỗi hoặc mất phản hồi: đọc lại, không tự gửi lại. Tin không rõ đã gửi không được phát lại.</p>
  <p>Đổi khóa, đổi chế độ hoặc tắt/bật bot vô hiệu quyền và lượt chờ phiên bản cũ; cần kiểm tra, liên kết/cấp quyền lại. Kho tri thức của liên kết cũ không thể đổi để diễn giải lại lịch sử: dùng bot/kết nối khác cho kho khác. Ngắt kết nối trong PAO không tự thu hồi token hoặc xóa webhook tại Telegram: dùng BotFather /revoke nếu cần. Dữ liệu và bằng chứng cũ được giữ theo chính sách; không nhập lịch sử tự động.</p>
  <a href="https://core.telegram.org/bots/api" target="_blank" rel="noopener noreferrer">Tài liệu Telegram chính thức</a></details>
  {busy&&<p role="status">Đang đối chiếu Telegram…</p>}{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {command&&<section aria-label="Mã liên kết một lần"><p>Gửi nguyên lệnh sau vào hội thoại riêng với đúng bot; không gửi cho người khác:</p><output>{command}</output><button type="button" onClick={()=>setCommand('')}>Ẩn mã liên kết</button></section>}
  {data&&<>
   {!available&&<p role="note">Vận hành Telegram theo doanh nghiệp đang tắt trên máy chủ hoặc xung đột với bot dùng chung. Chỉ xem cấu hình; thao tác xác minh, lưu khóa, bật và liên kết bị khóa. Nhờ quản trị hệ thống kiểm tra, không nhập lại token để thử.</p>}
   {admin&&<fieldset disabled={busy||!available}><legend>Xác minh và tạo kết nối đang tắt</legend><label>ID bot dạng số<input ref={bot} inputMode="numeric" autoComplete="off" aria-label="ID bot Telegram"/></label><p>Lấy phần số trước dấu hai chấm của token từ BotFather. PAO chỉ đăng ký bot sau getMe đúng ID; không cho phép chiếm ID bot của doanh nghiệp khác.</p><label>Token xác minh tạo bot<input ref={createToken} type="password" autoComplete="new-password" spellCheck={false} aria-label="Token xác minh tạo bot"/></label><button type="button" disabled={!ack} onClick={()=>void write('/v1/telegram/scoped',{workspace_id:workspace,bot_user_id:bot.current?.value.trim(),token:createToken.current?.value||'',consent:true})}>Xác minh và tạo kết nối Telegram</button></fieldset>}
   <label>Bot cần thiết lập<select value={selected} disabled={busy} onChange={e=>{const id=e.target.value;choice.current=id;setSelected(id);clear();void load(id)}} aria-label="Chọn bot Telegram"><option value="">Chọn rõ bot cần thao tác</option>{data.connections.map(row=><option value={row.id} key={row.id}>{row.bot_user_id||'Bot cũ đã chuyển đổi'} · {telegramState(row.status)}</option>)}</select></label>
   {!data.connections.length&&<p>Chưa có bot trong doanh nghiệp này. Không tự dùng bot của doanh nghiệp khác.</p>}
   {connection&&<>
    <p>ID {connection.bot_user_id||'chưa có'} · {telegramState(connection.status)} · phiên bản khóa {connection.generation} · {telegramState(connection.mode)}</p>
    <p>Danh tính: {connection.identity_verified?'đã xác minh':'chưa xác minh'} · Tình trạng gửi/nhận thật: chưa nghiệm thu.</p>
    {connection.editable?<fieldset disabled={busy||!available||connection.status==='revoked'}><legend>Khóa và vận hành bot</legend><label>Token bot (bí mật)<input ref={token} type="password" autoComplete="new-password" spellCheck={false} aria-label="Token bot Telegram"/></label><p>Chỉ người quản trị đã tạo kết nối đổi khóa. Token không được trả lại trình duyệt sau lưu.</p>
     {!connection.identity_verified&&<><label>ID bot cần xác minh<input ref={identityBot} defaultValue={connection.bot_user_id||''} inputMode="numeric" aria-label="ID xác minh bot Telegram"/></label><p>Bot cũ đã chuyển đổi cần xác minh ID bằng getMe trước khi lưu token; không lấy ID nhân viên làm ID bot.</p><button type="button" disabled={!ack} onClick={()=>void write(base+'/identity',{bot_user_id:identityBot.current?.value.trim(),token:token.current?.value||'',request_key:crypto.randomUUID(),consent:true},'test')}>Xác minh token bằng getMe</button></>}
     <button type="button" disabled={!ack} onClick={()=>void write(base+'/credential',{generation:connection.generation,request_key:crypto.randomUUID(),token:token.current?.value||'',consent:true})}>Lưu hoặc đổi token</button>
     {connection.generation>0&&<><button type="button" disabled={!ack} onClick={()=>control('test')}>Kiểm tra danh tính bot</button><button type="button" disabled={!ack||connection.status!=='disabled'||!connection.identity_verified} onClick={()=>control('enable')}>Bật xử lý Telegram</button><button type="button" disabled={!ack||connection.status!=='enabled'} onClick={()=>control('disable')}>Tắt xử lý Telegram</button><button type="button" disabled={!ack} onClick={()=>control('revoke')}>Ngắt kết nối Telegram</button><button type="button" disabled={!ack||connection.status!=='disabled'} onClick={()=>control('polling')}>Chuyển sang lấy tin định kỳ</button><button type="button" disabled={!ack||connection.status!=='disabled'} onClick={()=>control('webhook')}>Cấu hình webhook HTTPS</button></>}
    </fieldset>:<p>Bạn không phải người quản trị đã tạo kết nối; không thể đổi khóa hoặc cấu hình bot này.</p>}
    {data.can_pair&&<fieldset disabled={busy||!available||connection.status!=='enabled'}><legend>Liên kết chính tài khoản của bạn</legend><label>Telegram user ID của bạn<input ref={tgid} inputMode="numeric" aria-label="Telegram user ID của tôi"/></label><p>Nhập ID số đã xác minh của tài khoản Telegram cá nhân, không phải @username, ID bot hoặc ID nhóm. Nếu không biết chính xác ID, dừng và nhờ quản trị viên hỗ trợ; không đoán.</p><label>Mã kho tri thức (tùy chọn)<input ref={brain} autoComplete="off" aria-label="Kho tri thức Telegram"/></label><p>Lấy mã kho từ PAO. Chỉ chọn kho bạn đã có quyền trong doanh nghiệp này; để trống không cấp quyền truy cập mọi kho.</p><button type="button" onClick={()=>void write(base+'/pairing',{expected_user_id:tgid.current?.value.trim(),brain_id:brain.current?.value.trim()||null},'pairing')}>Tạo mã liên kết của tôi</button></fieldset>}
    {team&&<><h3>Liên kết của tôi</h3>{team.pairings.map(row=><div key={row.id}><p>{row.expected_user_id} · {telegramState(row.status)}{row.expired?' · mã đã hết hạn':''}</p>{row.status==='observed'&&!row.expired&&<button type="button" disabled={!ack||busy} onClick={()=>void write(base+'/pairing/confirm',{pairing_id:row.id,consent:true})}>Xác nhận ID {row.observed_user_id} là của tôi</button>}</div>)}
     <h3>Danh tính và quyền trong bot</h3>{!team.peers.length&&<p>Chưa có danh tính được liên kết. /start không tự cấp quyền.</p>}{team.peers.map(peer=><div key={peer.id} className="tg-person"><p>Telegram ID {peer.telegram_user_id} · tài khoản PAO {peer.user_id}</p><p>Giao việc: {peer.allow_chat?'có':'không'} · Báo cáo: {peer.allow_reports?'có':'không'}</p>{admin&&<><p>Chỉ cấp khi đã đối chiếu đúng người và chấp thuận gửi đến hội thoại riêng này.</p>{[{chat:true,reports:false,label:'Chỉ cấp quyền giao việc'},{chat:false,reports:true,label:'Chỉ cấp quyền nhận báo cáo'},{chat:true,reports:true,label:'Cấp giao việc và báo cáo'},{chat:false,reports:false,label:'Thu hồi quyền Telegram'}].map(action=><button type="button" key={action.label} disabled={!ack||busy||!available} onClick={()=>void write(base+'/team/grant',{peer_id:peer.id,version:peer.version,request_key:crypto.randomUUID(),allow_chat:action.chat,allow_reports:action.reports,confirm_destination:action.chat||action.reports})}>{action.label}</button>)}</>}</div>)}</>}
   </>}
   <label className="tg-consent"><input type="checkbox" aria-label="Xác nhận thao tác Telegram" checked={ack} disabled={busy} onChange={e=>setAck(e.target.checked)}/>Tôi đã đối chiếu doanh nghiệp, bot, người nhận và hiểu tác động của thao tác sắp chọn. Kiểm tra/bật/đổi chế độ có thể gọi Telegram; không tự duyệt việc nhạy cảm.</label>
  </>}
 </section>;
}
