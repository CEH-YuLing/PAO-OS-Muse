'use client';
import {useEffect,useId,useRef,useState,type ReactNode} from 'react';
import {ChevronDown,X} from 'lucide-react';

/** Native top-layer popover: not clipped by the independently scrolling chat. */
export default function ChatControlPopover({label,title,children,variant='default',closeSignal=0}:{label:string;title:string;children:ReactNode;variant?:'default'|'models';closeSignal?:number}){
 const id=useId(),trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null);
 const [open,setOpen]=useState(false);
 function position(){
  const button=trigger.current,box=panel.current;if(!button||!box)return;
  if(variant==='models'){
   const margin=12,width=Math.min(860,window.innerWidth-margin*2);
   box.style.width=`${width}px`;box.style.maxHeight=`${Math.min(760,window.innerHeight-margin*2)}px`;
   box.style.left=`${(window.innerWidth-width)/2}px`;box.style.top='50%';box.style.transform='translateY(-50%)';return;
  }
  const bounds=button.getBoundingClientRect(),margin=12,width=Math.min(440,window.innerWidth-margin*2);
  const below=window.innerHeight-bounds.bottom-margin-8,above=bounds.top-margin-8;
  const placeAbove=below<220&&above>below,room=Math.max(120,placeAbove?above:below);
  box.style.width=`${width}px`;box.style.maxHeight=`${Math.min(560,room)}px`;
  box.style.left=`${Math.max(margin,Math.min(bounds.right-width,window.innerWidth-width-margin))}px`;
  box.style.top=`${Math.max(margin,placeAbove?bounds.top-8-Math.min(box.scrollHeight,560,room):bounds.bottom+8)}px`;
 }
 useEffect(()=>{
  if(!open)return;
  const move=()=>position();window.addEventListener('resize',move);window.addEventListener('scroll',move,true);
  return()=>{window.removeEventListener('resize',move);window.removeEventListener('scroll',move,true)};
 },[open]);
 useEffect(()=>{if(closeSignal&&panel.current?.matches(':popover-open')){panel.current.hidePopover();trigger.current?.focus()}},[closeSignal]);
 return <>
  <button ref={trigger} type="button" className={`pao-chat-control-trigger${variant==='models'?' pao-model-catalog-trigger':''}`} aria-label={title} aria-haspopup="dialog" aria-expanded={open} aria-controls={id} popoverTarget={id} onClick={position} title={label}>{variant==='models'?<span><small>Mô hình đang chọn</small><strong>{label}</strong></span>:<span>{label}</span>}<ChevronDown size={variant==='models'?17:14}/></button>
  <div id={id} ref={panel} popover="auto" role="dialog" aria-label={title} className={`pao-engine-picker pao-chat-control-popover${variant==='models'?' pao-model-catalog-popover':''}`} onToggle={()=>{const visible=panel.current?.matches(':popover-open')||false;setOpen(visible);if(visible){position();panel.current?.querySelector<HTMLElement>('[data-popover-autofocus]')?.focus()}}}>
   <header><strong>{title}</strong><button type="button" aria-label={`Đóng ${title.toLowerCase()}`} onClick={()=>{panel.current?.hidePopover();trigger.current?.focus()}}><X size={16}/></button></header>
   {children}
  </div>
 </>;
}
