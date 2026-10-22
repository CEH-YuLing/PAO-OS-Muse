"use client";
import {createContext,useCallback,useContext,useEffect,useRef,useState} from 'react';
import {usePathname} from 'next/navigation';
import {Moon,Sun,SunMoon} from 'lucide-react';
import {THEME_KEY,readTheme,resolveTheme,saveTheme,validTheme,watchAutoTheme,type Theme,type ThemePreference} from './theme.mjs';
const Context=createContext<{theme:Theme;preference:ThemePreference;setTheme:(theme:ThemePreference)=>void}>({theme:'dark',preference:'dark',setTheme:()=>{}});
export const useTheme=()=>useContext(Context);
export function ThemeToggle({compact=false}:{compact?:boolean}){
 const {theme,preference,setTheme}=useTheme();const next=theme==='dark'?'light':'dark';
 const title=preference==='auto'?`Tự động theo giờ thiết bị · Đang dùng giao diện ${theme==='light'?'sáng':'tối'}. Bấm để dùng giao diện ${next==='light'?'sáng':'tối'} cố định.`:`Đang dùng giao diện ${theme==='light'?'sáng':'tối'}`;
 return <button type="button" className={`pao-theme-toggle${compact?' is-compact':''}`} aria-label={`Chuyển sang giao diện ${next==='light'?'sáng':'tối'}`} title={title} onClick={()=>setTheme(next)}>
  {preference==='auto'?<SunMoon size={18}/>:theme==='dark'?<Sun size={18}/>:<Moon size={18}/>}<span>{theme==='dark'?'Giao diện sáng':'Giao diện tối'}</span>
 </button>;
}
export function AppearanceSettings(){
 const {theme,preference,setTheme}=useTheme();
 const options=[
  {value:'light',label:'Sáng',help:'Nền sáng, chữ rõ ràng',Icon:Sun},
  {value:'dark',label:'Tối',help:'Nền tối, dễ chịu khi ít ánh sáng',Icon:Moon},
  {value:'auto',label:'Tự động',help:'Sáng 06:00–18:00, còn lại tối',Icon:SunMoon},
 ] as const;
 return <section className="pao-appearance" aria-labelledby="pao-appearance-title">
  <div><h2 id="pao-appearance-title">Giao diện hiển thị</h2><p>Chọn Sáng, Tối hoặc Tự động theo giờ trên thiết bị: từ 06:00 đến trước 18:00 dùng nền sáng, từ 18:00 đến trước 06:00 dùng nền tối. Lựa chọn được nhớ trên trình duyệt này, không thay đổi dữ liệu hay quyền của doanh nghiệp.</p><p className="pao-appearance-current" role="status">{preference==='auto'?`Đang tự động: giao diện ${theme==='light'?'sáng':'tối'} theo giờ thiết bị.`:`Đang dùng giao diện ${theme==='light'?'sáng':'tối'} cố định.`}</p></div>
  <div className="pao-appearance-options" role="group" aria-label="Chọn giao diện PAO">
   {options.map(({value,label,help,Icon})=><button key={value} type="button" aria-pressed={preference===value} onClick={()=>setTheme(value)}>
    <Icon size={20}/><span><strong>{label}</strong><small>{help}</small></span>
   </button>)}
  </div>
 </section>;
}
export default function ThemeProvider({children}:{children:React.ReactNode}){
 const [theme,update]=useState<Theme>('dark');const [preference,updatePreference]=useState<ThemePreference>('dark');
 const activePreference=useRef<ThemePreference>('dark');const pathname=usePathname();
 const applyResolved=useCallback((value:Theme)=>{document.documentElement.dataset.theme=value;document.documentElement.style.colorScheme=value;update(value)},[]);
 const apply=useCallback((value:ThemePreference)=>{activePreference.current=value;document.documentElement.dataset.themePreference=value;updatePreference(value);applyResolved(resolveTheme(value))},[applyResolved]);
 useEffect(()=>{
  try{apply(readTheme(window.localStorage))}catch{apply('dark')}
  const sync=(event:StorageEvent)=>{if(event.storageArea){try{if(event.storageArea!==window.localStorage)return}catch{return}}if(event.key===THEME_KEY||event.key===null)apply(validTheme(event.newValue)?event.newValue:'dark')};
  window.addEventListener('storage',sync);return()=>window.removeEventListener('storage',sync);
 },[apply]);
 useEffect(()=>{
  if(preference!=='auto')return;
  const watcher=watchAutoTheme(value=>{if(activePreference.current==='auto')applyResolved(value)});
  const visible=()=>{if(document.visibilityState==='visible')watcher.refresh()};
  window.addEventListener('focus',watcher.refresh);window.addEventListener('pageshow',watcher.refresh);document.addEventListener('visibilitychange',visible);
  return()=>{watcher.stop();window.removeEventListener('focus',watcher.refresh);window.removeEventListener('pageshow',watcher.refresh);document.removeEventListener('visibilitychange',visible)};
 },[preference,applyResolved]);
 const setTheme=useCallback((value:ThemePreference)=>{if(!validTheme(value))return;apply(value);try{saveTheme(window.localStorage,value)}catch{/* Browser storage may be denied; current tab still works. */}},[apply]);
 return <Context.Provider value={{theme,preference,setTheme}}>{children}{(pathname==='/'||pathname==='/join')&&<div className="pao-public-theme"><ThemeToggle/></div>}</Context.Provider>;
}
