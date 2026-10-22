"use client";
import {useState} from 'react';
import Link from 'next/link';
import {usePao} from '@/lib/PaoRuntimeContext';
import '@/components/workspace/lifecycle.css';
import '@/components/auth-entry.css';

export default function Join(){
 const runtime=usePao();
 const [email,setEmail]=useState(''),[code,setCode]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
 return <main className="pao-auth-page"><section className="lc-panel pao-auth-card">
  <header><strong>PAO</strong><span>Tham gia doanh nghiệp</span></header>
  <h1>{runtime.me?'Nhận lời mời vào doanh nghiệp':'Tạo tài khoản bằng mã mời'}</h1>
  <p>Chỉ dành cho người được chủ doanh nghiệp mời. Mã dùng một lần, không đặt lại mật khẩu. Không đưa mã vào URL hoặc chat với AI.</p>
  {!runtime.me&&<p>Đã có tài khoản PAO? <Link href="/">Đăng nhập trước để nhận lời mời</Link>.</p>}
  <p>{runtime.me?`Đang đăng nhập: ${runtime.me.email}`:'Chưa đăng nhập: chỉ dùng phần dưới để tạo tài khoản mới từ lời mời hợp lệ.'}</p>
  <form onSubmit={e=>{e.preventDefault();if(busy)return;setBusy(true);setError('');setMessage('');void runtime.api('/v1/auth/invitations/accept','POST',{email:runtime.me?.email||email,code,...(!runtime.me?{password}:{})}).then(()=>{setCode('');setPassword('');setMessage('Đã tham gia doanh nghiệp. Đăng nhập lại để cập nhật danh sách doanh nghiệp.')}).catch(e=>setError((e as Error).message)).finally(()=>setBusy(false))}}>
   <fieldset disabled={busy||runtime.hydrating}><legend>Thông tin nhận lời mời</legend>
   {!runtime.me&&<label>Email được mời<input type="email" required maxLength={254} autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)}/></label>}
   <label>Mã mời<input type="password" required minLength={40} maxLength={100} autoComplete="off" value={code} onChange={e=>setCode(e.target.value)}/></label>
   {!runtime.me&&<label>Mật khẩu cho tài khoản mới — tối thiểu 12 ký tự<input type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>}
   <button disabled={busy}>{busy?'Đang kiểm tra lời mời…':runtime.me?'Nhận lời mời':'Tạo tài khoản và tham gia'}</button>
   </fieldset>
  </form>
  {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
  <p><Link href="/">Về trang đăng nhập</Link>{runtime.me&&<> · <Link href="/settings">Về cài đặt</Link></>}</p>
 </section></main>;
}
