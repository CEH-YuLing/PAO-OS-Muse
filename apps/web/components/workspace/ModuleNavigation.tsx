'use client';
import {SectionTabs,type SectionItem} from './SectionNavigation';
export type ModuleGroup=SectionItem&{views:string[]};
export default function ModuleNavigation({id,label,items,groups,value,onChange}:{id:string;label:string;items:SectionItem[];groups:ModuleGroup[];value:string;onChange:(id:string)=>void}){
 const group=groups.find(g=>g.views.includes(value))||groups[0],children=items.filter(x=>group.views.includes(x.id));
 return <><SectionTabs id={id} label={label} items={groups} value={group.id} onChange={next=>{const found=groups.find(g=>g.id===next);if(found)onChange(found.views[0])}}/><section role="tabpanel" id={`${id}-panel-${group.id}`} aria-labelledby={`${id}-tab-${group.id}`} className="ux-section-panel">{children.length>1&&<label className="ux-view-switch">Xem trong {group.label}<select aria-label={'Chế độ xem '+label} value={value} onChange={e=>onChange(e.target.value)}>{children.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>}</section></>
}
