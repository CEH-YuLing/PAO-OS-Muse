'use client';

import {useEffect,useState,type ReactNode} from 'react';
import {Bot,Cloud,KeyRound,Plug,Puzzle,Search} from 'lucide-react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {connectionGroups,connectionItem,itemsInGroup,appsInCategory,tabTarget,type ConnectionGroupId} from '@/lib/connection-catalog.mjs';
import AdsAppSettings from './AdsAppSettings';
import AdsConnectionSettings from './AdsConnectionSettings';
import AdsGrantedReads from './AdsGrantedReads';
import ConnectionGrantPanel from './ConnectionGrantPanel';
import ConnectorPanel from './ConnectorPanel';
import McpGrantedCalls from './McpGrantedCalls';
import TelegramSettings from './TelegramSettings';
import TelegramLegacyMappingPanel from './TelegramLegacyMappingPanel';
import './integration-tabs.css';

export const LEAVE_CONNECTION_DRAFT='Bạn đã thay đổi thông tin trong biểu mẫu. Rời tab sẽ xóa dữ liệu chưa lưu, bao gồm khóa bí mật. Thao tác đã gửi đến máy chủ không bị hủy hoặc hoàn tác khi đổi tab. Bạn muốn tiếp tục?';
const icons={ads:Cloud,bots:Bot,plugins:Puzzle,mcp:Plug};

export default function IntegrationTabs({onDraftChange,legacy,active:requested,onSelect}:{active:string;onSelect:(platform:string)=>boolean;onDraftChange:(dirty:boolean)=>void;legacy:{enabled:boolean;configured:boolean;mode:string;allowed_peers:number}|null}){
 const {activeWorkspace:member}=usePao(),selected=connectionItem(requested),active=selected.id;
 const group=connectionGroups.find(item=>item.id===selected.group)!,items=itemsInGroup(group.id);
 const [dirty,setDirty]=useState(false),[compact,setCompact]=useState(false);
 useEffect(()=>{const media=window.matchMedia('(max-width:760px)');const sync=()=>setCompact(media.matches);sync();media.addEventListener('change',sync);return()=>media.removeEventListener('change',sync)},[]);
 useEffect(()=>{onDraftChange(dirty);if(!dirty)return;const leave=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};window.addEventListener('beforeunload',leave);return()=>window.removeEventListener('beforeunload',leave)},[dirty,onDraftChange]);
 useEffect(()=>()=>onDraftChange(false),[onDraftChange]);
 function choose(next:string){if(next===active)return true;if(!onSelect(next))return false;setDirty(false);return true}
 function chooseGroup(id:string){const next=connectionGroups.find(item=>item.id===id)!;return next.id===group.id||choose(next.defaultPlatform)}
 const Icon=icons[group.id],hasSubtabs=group.id!=='mcp';
 return <section className="cn-workspace" aria-label="Kết nối theo nền tảng">
  <header className="cn-intro"><div><h2>Kết nối của doanh nghiệp</h2><p>Chọn nhóm, sau đó chọn nền tảng cần thiết lập. Chỉ áp dụng cho <strong>{member?.name||'doanh nghiệp đang chọn'}</strong>. Danh mục chờ không phải kết nối đang hoạt động.</p></div><span><KeyRound size={14}/>Khóa và quyền riêng theo doanh nghiệp</span></header>
  <Tabs label="Nhóm kết nối" prefix="connection-group" panelPrefix="connection-group-panel" items={connectionGroups.map(item=>({...item,hint:item.description}))} active={group.id} choose={chooseGroup} groups/>
  <section id={'connection-group-panel-'+group.id} role="tabpanel" aria-labelledby={'connection-group-'+group.id} className="cn-group-panel" tabIndex={0}>
   <header className="cn-group-heading"><Icon size={20}/><div><h3>{group.name}</h3><p>{group.id==='ads'?'Quản lý ứng dụng, tài khoản quảng cáo và quyền sử dụng. Lưu cấu hình không tự bật quảng cáo.':group.id==='bots'?'Quản lý bot và đội ngũ đúng doanh nghiệp. Bot không tự cấp quyền điều khiển cho người nhắn tin.':group.id==='plugins'?'Các ứng dụng được sắp xếp theo lĩnh vực để mở rộng sau. Chưa có thao tác cài hoặc kết nối.':'Kết nối máy chủ MCP riêng bằng cơ chế hiện có; quyền công cụ được cấp riêng, không mặc định cho toàn bộ nhân viên.'}</p></div></header>
   <div className={group.id==='plugins'?'cn-plugin-layout':''}>
    {hasSubtabs&&<Tabs label={group.id==='plugins'?'Danh mục plugin':'Nền tảng kết nối'} prefix="connection-tab" panelPrefix="connection-panel" items={items} active={active} choose={choose} vertical={group.id==='plugins'&&!compact}/>}
    <div key={active} id={'connection-panel-'+active} role={hasSubtabs?'tabpanel':undefined} aria-labelledby={hasSubtabs?'connection-tab-'+active:undefined} tabIndex={0} className="cn-panel" onInputCapture={()=>{if(selected.implemented)setDirty(true)}} onChangeCapture={()=>{if(selected.implemented)setDirty(true)}}>
     {dirty&&<p className="cn-draft" role="note">Biểu mẫu đã thay đổi. Kiểm tra kết quả lưu trước khi rời tab; khóa và dữ liệu chưa lưu sẽ không được giữ lại.</p>}
     {(active==='meta'||active==='google')&&<>
      <p className="cn-steps">1. Thiết lập ứng dụng <span>→</span> 2. Kết nối OAuth <span>→</span> 3. Cấp quyền <span>→</span> 4. Đồng bộ chỉ đọc</p>
      <div className="cn-ads-layout"><AdsAppSettings provider={active}/><AdsConnectionSettings provider={active}/></div>
      <Fold title={'Tài khoản, nhãn hàng và quyền sử dụng '+selected.name}><ConnectionGrantPanel kind={active==='meta'?'meta_ads':'google_ads'}/></Fold>
      <Fold title={'Đồng bộ và báo cáo '+selected.name+' bằng quyền đã cấp'}><AdsGrantedReads kind={active==='meta'?'meta_ads':'google_ads'}/></Fold>
     </>}
     {active==='telegram'&&<><TelegramSettings/><Fold title="Nâng cao · Telegram cũ và chuyển đổi kết nối"><p>Cơ chế cũ dùng chung máy chủ, không thay thế bot riêng của doanh nghiệp. Không tự chuyển token, bật bot hoặc phát lại tin.</p><p>{legacy?`Cờ máy chủ: ${legacy.enabled?'đang bật':'đang tắt'} · Cấu hình: ${legacy.configured?'có':'chưa có'} · ${legacy.allowed_peers} danh tính cũ. Chưa nghiệm thu gửi/nhận thật.`:'Chưa đọc được trạng thái cơ chế cũ.'}</p><TelegramLegacyMappingPanel/></Fold></>}
     {active==='mcp'&&<><ConnectorPanel/><Fold title="Phân quyền MCP theo nhân viên và nhãn hàng"><ConnectionGrantPanel kind="mcp"/></Fold><Fold title="Gọi công cụ chỉ đọc bằng quyền đã cấp"><McpGrantedCalls/></Fold></>}
     {group.id==='plugins'&&<PluginCatalog category={active}/>}
     {!selected.implemented&&group.id!=='plugins'&&<section className="cn-unavailable"><Icon size={30}/><h3>{selected.name}</h3><span>Chưa hỗ trợ kết nối</span><p>Đây là vị trí chờ theo cấu trúc PAO. Chưa có connector hoặc biểu mẫu nhập khóa; chọn tab không tạo, thử hoặc kích hoạt kết nối.</p><p>{active==='gpt_ads'?'GPT Ads là nhãn quy hoạch theo yêu cầu, không phải cấu hình mô hình ChatGPT và không xác nhận có API quảng cáo sẵn dùng.':'Khi triển khai, hướng dẫn chính thức, tài khoản, xác thực và phân quyền của nền tảng sẽ được bổ sung tại đây.'}</p></section>}
    </div>
   </div>
  </section>
 </section>;
}
type TabItem={id:string;name:string;hint?:string};
function Tabs({label,prefix,panelPrefix,items,active,choose,groups=false,vertical=false}:{label:string;prefix:string;panelPrefix:string;items:TabItem[];active:string;choose:(id:string)=>boolean;groups?:boolean;vertical?:boolean}){
 return <div className={groups?'cn-groups':vertical?'cn-tabs cn-plugin-tabs':'cn-tabs'} role="tablist" aria-label={label} aria-orientation={vertical?'vertical':'horizontal'}>{items.map((item,index)=>{
  const Icon=groups?icons[item.id as ConnectionGroupId]:null;
  return <button key={item.id} type="button" role="tab" id={prefix+'-'+item.id} aria-controls={panelPrefix+'-'+item.id} aria-selected={active===item.id} tabIndex={active===item.id?0:-1} data-testid={prefix+'-'+item.id} onClick={()=>choose(item.id)} onKeyDown={event=>{
   if(vertical&&(event.key==='ArrowRight'||event.key==='ArrowLeft'))return;
   const key=vertical?(event.key==='ArrowDown'?'ArrowRight':event.key==='ArrowUp'?'ArrowLeft':event.key):event.key;
   const target=tabTarget(key,index,items.length);if(target===null)return;event.preventDefault();const next=items[target].id;if(choose(next))document.getElementById(prefix+'-'+next)?.focus();
  }}>{Icon&&<Icon size={19}/>}<span><strong>{item.name}</strong>{item.hint&&<small>{item.hint}</small>}</span></button>;
 })}</div>;
}
function PluginCatalog({category}:{category:string}){
 const [query,setQuery]=useState(''),all=appsInCategory(category),apps=all.filter(app=>app.name.toLocaleLowerCase('vi').includes(query.trim().toLocaleLowerCase('vi')));
 return <section className="cn-plugin-catalog" aria-label="Ứng dụng quy hoạch"><header><div><h4>{connectionItem(category).name}</h4><p>{all.length} mục trong danh mục · chưa phải số lượng kết nối.</p></div><label><Search size={16}/><span className="cn-sr-only">Tìm ứng dụng trong danh mục</span><input aria-label="Tìm ứng dụng trong danh mục" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Tìm tên ứng dụng…"/></label></header>
  <p className="cn-planned-note">Danh mục chờ phát triển. Chưa hỗ trợ cài plugin, nhập khóa hay kết nối các ứng dụng dưới đây. Không nhập thông tin bí mật vào ô tìm kiếm.</p>
  <div className="cn-plugin-cards">{apps.map(app=><article key={app.id}><div className="cn-app-mark" aria-hidden="true">{app.name.slice(0,1)}</div><div><h5>{app.name}</h5><p>{connectionItem(app.category).name}</p></div><span>Vị trí chờ</span></article>)}</div>
  {!apps.length&&<p className="cn-plugin-empty" role="status">{all.length?'Không tìm thấy tên ứng dụng phù hợp.':'Nhóm này đang để trống, sẵn sàng bổ sung ứng dụng khi triển khai.'}</p>}
 </section>;
}
function Fold({title,children}:{title:string;children:ReactNode}){
 const [open,setOpen]=useState(false);
 return <details className="cn-fold" onToggle={event=>setOpen(event.currentTarget.open)}><summary>{title}</summary>{open&&<div className="cn-fold-body">{children}</div>}</details>;
}
