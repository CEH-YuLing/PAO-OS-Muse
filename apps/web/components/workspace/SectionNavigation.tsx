'use client';
import {useEffect,useRef,useState} from 'react';
import {sectionKey,sectionUrl,sectionValue} from '@/lib/section-navigation.mjs';
import './section-navigation.css';
export type SectionItem={id:string;label:string;description?:string};
export function useSection(items:readonly SectionItem[],key:string,fallback=items[0].id,aliases:Record<string,string>={}){
 const [value,setValue]=useState(fallback),ids=items.map(x=>x.id).join('|'),aliasRef=useRef(aliases);aliasRef.current=aliases;
 useEffect(()=>{const read=()=>{const hash=location.hash.slice(1),alias=Object.hasOwn(aliasRef.current,hash)?aliasRef.current[hash]:undefined;setValue(alias&&ids.split('|').includes(alias)?alias:sectionValue(location.search,key,ids.split('|'),fallback))};read();window.addEventListener('popstate',read);window.addEventListener('hashchange',read);return()=>{window.removeEventListener('popstate',read);window.removeEventListener('hashchange',read)}},[ids,key,fallback]);
 function select(next:string){if(next===value||!ids.split('|').includes(next))return;setValue(next);const url=new URL(sectionUrl(location.href,key,next),location.origin);url.hash='';history.pushState(history.state,'',url.pathname+url.search)}
 return [value,select] as const;
}
export function SectionTabs({id,label,items,value,onChange,rail=false}:{id:string;label:string;items:readonly SectionItem[];value:string;onChange:(id:string)=>void;rail?:boolean}){
 const root=useRef<HTMLElement>(null),[vertical,setVertical]=useState(false);
 useEffect(()=>{const media=matchMedia('(min-width:761px)'),read=()=>setVertical(rail&&media.matches);read();media.addEventListener('change',read);return()=>media.removeEventListener('change',read)},[rail]);
 return <nav ref={root} className={`ux-section-tabs${rail?' ux-section-rail':''}`} role="tablist" aria-label={label} aria-orientation={vertical?'vertical':'horizontal'}>{items.map((item,index)=><button type="button" role="tab" data-testid={`${id}-tab-${item.id}`} key={item.id} id={`${id}-tab-${item.id}`} aria-controls={`${id}-panel-${item.id}`} aria-selected={value===item.id} tabIndex={value===item.id?0:-1} onClick={()=>{if(value!==item.id)onChange(item.id)}} onKeyDown={e=>{if(vertical&&['ArrowLeft','ArrowRight'].includes(e.key)||!vertical&&['ArrowUp','ArrowDown'].includes(e.key))return;const next=sectionKey(e.key,index,items.length);if(next===null)return;e.preventDefault();if(value!==items[next].id)onChange(items[next].id);requestAnimationFrame(()=>(root.current?.querySelector<HTMLButtonElement>(`#${id}-tab-${items[next].id}[aria-selected=true]`)||root.current?.querySelector<HTMLButtonElement>('[aria-selected=true]'))?.focus())}}><strong>{item.label}</strong>{item.description&&<small>{item.description}</small>}</button>)}</nav>
}
export function SectionPanel({id,name,active,children}:{id:string;name:string;active:boolean;children:React.ReactNode}){return <section className="ux-section-panel" id={`${id}-panel-${name}`} role="tabpanel" aria-labelledby={`${id}-tab-${name}`} hidden={!active}>{children}</section>}
