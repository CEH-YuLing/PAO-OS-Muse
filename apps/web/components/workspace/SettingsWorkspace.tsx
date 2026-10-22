"use client";

import {useEffect,useRef,useState} from "react";
import {readSettingsNavigation,settingsNavigationUrl} from "@/lib/settings-navigation.mjs";
import {BrainCircuit,CheckCircle2,Database,KeyRound,Mic,RefreshCw,Settings,ShieldCheck} from "lucide-react";
import type {components} from "../../../../packages/contracts/schema";
import {usePao} from "@/lib/PaoRuntimeContext";
import PaoAppShell from "./PaoAppShell";
import IntegrationTabs,{LEAVE_CONNECTION_DRAFT} from "./IntegrationTabs";
import {SectionTabs} from "./SectionNavigation";
import {settingsGroups,settingsSections,settingsSection} from "@/lib/settings-structure.mjs";
import LifecyclePanel from "./LifecyclePanel";
import SettingsAccountTeam from "./SettingsAccountTeam";
import ModelAccessPanel from "./ModelAccessPanel";
import ResourceQuotaPanel from "./ResourceQuotaPanel";
import ModelProviderSettings from "./ModelProviderSettings";
import {readModelConnection,type ModelConnection} from '@/lib/model-provider-tabs.mjs';
import {useSettingsStatus} from "@/lib/useSettingsStatus";
import SettingsGuide from "./SettingsGuide";
import OrganizationPanel from './OrganizationPanel';
import {AppearanceSettings} from '@/lib/ThemeProvider';
import PlatformCatalog, {type Platform} from "../features/platform/PlatformCatalog";
import "../features/platform/readiness.css";
import "./settings.css";
import "./settings-account.css";
import "./settings-platform.css";
import "./settings-observations.css";
import "./model-access.css";

type S=components["schemas"];type Connection={configured:boolean;status:string;scopes:string[];expires_at?:string|null};type Telegram={enabled:boolean;configured:boolean;mode:string;allowed_peers:number;delivery_issues:{id:string;status:string;error_code:string|null}[]};type Voice={enabled:boolean;stt_ready:boolean;tts_ready:boolean;stt_device:string;stt_compute_type:string;tts_provider:string;max_seconds:number};type Automation={enabled:boolean;address:string|null;namespace:string;task_queue:string};type Autopilot={global_enabled:boolean;meta_enabled:boolean;default_mode:string;phase:number};

type Selection={tab:string;platform:string;section:string;modelConnection:ModelConnection};
function readSelection():Selection{const selected=readSettingsNavigation(location.search),tab=selected.tab==='capabilities'?'system':selected.tab;return {...selected,tab,modelConnection:readModelConnection(location.search),section:selected.tab==='capabilities'?'capabilities':settingsSection(tab,new URLSearchParams(location.search).get('section'))}}
export default function SettingsWorkspace(){
 const runtime=usePao(),member=runtime.activeWorkspace,workspace=member?.id||"";
 const {data,failed,loading,observed,load}=useSettingsStatus(workspace);
 const meta=(data.meta as Connection|undefined)??null,google=(data.google as Connection|undefined)??null,telegram=(data.telegram as Telegram|undefined)??null,
 voice=(data.voice as Voice|undefined)??null,automation=(data.automation as Automation|undefined)??null,write=(data.write as S["WriteStatus"]|undefined)??null,
 autopilot=(data.autopilot as Autopilot|undefined)??null,platform=(data.platform as Platform|undefined)??null;
 const [selection,setSelection]=useState<Selection>({tab:'general',platform:'meta',section:'',modelConnection:'client'});
 const [connectionDraft,setConnectionDraft]=useState(false),[formChanged,setFormChanged]=useState(false);
 const state=useRef({selection,connectionDraft,formChanged});state.current={selection,connectionDraft,formChanged};
 const {tab,section}=selection;
 function leave(){const s=state.current;if(s.selection.tab==='integrations'&&s.connectionDraft&&!window.confirm(LEAVE_CONNECTION_DRAFT))return false;if(s.formChanged&&!window.confirm('Rời biểu mẫu đã thay đổi? Hãy kiểm tra thao tác đã được xác nhận; phần chưa lưu sẽ bị bỏ.'))return false;setConnectionDraft(false);setFormChanged(false);return true}
 useEffect(()=>{setSelection(readSelection());const back=()=>{if(leave())setSelection(readSelection());else history.replaceState(history.state,'',settingsNavigationUrl(location.href,state.current.selection))};const unload=(e:BeforeUnloadEvent)=>{if(state.current.connectionDraft||state.current.formChanged){e.preventDefault();e.returnValue=''}};window.addEventListener('popstate',back);window.addEventListener('beforeunload',unload);return()=>{window.removeEventListener('popstate',back);window.removeEventListener('beforeunload',unload)}},[]);
 function navigate(next:Selection){if(!leave())return false;setSelection(next);history.pushState(history.state,'',settingsNavigationUrl(location.href,next));return true}
 function setTab(next:string){navigate({...selection,tab:next,section:settingsSection(next,null),modelConnection:'client'})}
 const services=[Boolean(meta),Boolean(google),Boolean(telegram),Boolean(voice),Boolean(automation),Boolean(write),Boolean(autopilot),Boolean(platform),data.providers!==undefined];
 return <PaoAppShell pageTitle="Cài đặt và kết nối" pageSubtitle="Chọn một khu vực để thiết lập, không cần xử lý tất cả trên cùng một trang.">
 <div className="st-workspace"><section className="st-command"><div><Settings size={19}/><span><small>DOANH NGHIỆP ĐANG CẤU HÌNH</small><strong>{member?.name} · {roleLabel(member?.role||'')}</strong></span></div><button onClick={()=>{if(leave())void load()}} disabled={loading}><RefreshCw size={14}/>Làm mới trạng thái</button></section>
 {failed.length>0&&<Message tone="error" text="Chưa đọc được một số nhóm trạng thái; chưa xác minh hoạt động. Kiểm tra quyền/API, không nhập lại khóa chỉ vì lỗi đọc."/>}
 {observed&&<details className="pao-observation-details"><summary>Thông tin trạng thái vừa đọc</summary><p>Đọc lúc {observed}. Đây không phải lần kiểm tra dịch vụ ngoài hoặc bằng chứng kết nối đang hoạt động.</p></details>}
 <div className="ux-settings-layout"><SectionTabs id="settings" label="Khu vực cài đặt và kết nối" items={settingsGroups} value={tab} onChange={setTab} rail/>
 <section className="ux-settings-content" role="tabpanel" id={'settings-panel-'+tab} aria-labelledby={'settings-tab-'+tab}>
 <SettingsGuide section={tab}/>
 {!!settingsSections[tab]?.length&&<SectionTabs id="settings-section" label="Mục cài đặt" items={settingsSections[tab]} value={section} onChange={next=>navigate({...selection,section:next})}/>}
 {formChanged&&<p role="note" className="ux-context-note">Biểu mẫu đã thay đổi. Trước khi rời, kiểm tra thông báo xác nhận lưu; PAO không tự lưu cấu hình.</p>}
 {loading?<Loading/>:<div role={settingsSections[tab]?.length?'tabpanel':undefined} id={settingsSections[tab]?.length?'settings-section-panel-'+section:undefined} aria-labelledby={settingsSections[tab]?.length?'settings-section-tab-'+section:undefined} key={workspace+':'+member?.role+':'+tab+':'+section} onChangeCapture={e=>{if(tab!=='integrations'&&!(tab==='ai'&&section==='providers')&&(e.target as HTMLElement).closest('form,fieldset'))setFormChanged(true)}}>
 {tab==='general'&&<><h2>Thiết lập PAO cho doanh nghiệp</h2><p>Mỗi khu vực bên trái chỉ phụ trách một nhóm công việc. Khóa, quyền và dữ liệu không tự chia sẻ giữa các doanh nghiệp.</p><div className="ux-shortcuts">{settingsGroups.filter(g=>g.id!=='general').map(g=><button className="ux-action" key={g.id} onClick={()=>setTab(g.id)}>{g.label}</button>)}</div><AppearanceSettings/><section className="st-summary"><PanelHead icon={Database} title="Thông tin trong phiên hiện tại" sub="Không phải thống kê tổng doanh nghiệp"/><Summary label="Hội thoại đang tải" value={String(runtime.sessions.length)}/><Summary label="Trợ lý trong danh mục" value={String(runtime.availableAgents.length)}/></section></>}
 {tab==='organization'&&<OrganizationPanel view={section==='brands'?'brands':'enterprise'}/>}
 {tab==='team'&&<>{section==='account'&&<><SettingsAccountTeam view="account" onConnections={()=>setTab('integrations')}/><LifecyclePanel view="account"/></>}{section==='permissions'&&<SettingsAccountTeam view="permissions" onConnections={()=>setTab('integrations')}/>} {(section==='members'||section==='invitations')&&<LifecyclePanel view={section}/>}</>}
 {tab==='integrations'&&<IntegrationTabs key={workspace+':'+member?.role} legacy={telegram} onDraftChange={setConnectionDraft} active={selection.platform} onSelect={platform=>navigate({...selection,platform})}/>}
 {tab==='ai'&&<>{section==='providers'&&<><ModelProviderSettings value={selection.modelConnection} onChange={modelConnection=>navigate({...selection,modelConnection})} onDraftChange={setFormChanged}/><p><a href="/business-planning?view=routing">Mở phân công AI theo công việc</a> · <a href="/knowledge?tab=skills">Mở thư viện Skills và agent</a></p></>}{section==='access'&&<ModelAccessPanel onDraftChange={setFormChanged}/>}{section==='voice'&&<VoicePanel voice={voice}/>}</>}
 {tab==='safety'&&<>{section==='policy'&&<Safety write={write} autopilot={autopilot} role={member?.role||''}/>} {section==='quota'&&<ResourceQuotaPanel/>}{(section==='exports'||section==='deletions')&&<LifecyclePanel view={section}/>}</>}
 {tab==='system'&&<>{section==='capabilities'?<PlatformCatalog platform={platform}/>:<SystemStatus services={services} meta={meta} google={google} telegram={telegram} voice={voice} automation={automation}/>}</>}
 </div>}</section></div></div></PaoAppShell>
}
function VoicePanel({voice}:{voice:Voice|null}){return <section className="st-voice"><PanelHead icon={Mic} title="Xử lý giọng nói" sub="Thư viện sẵn sàng chưa thay cho nghiệm thu micro/giọng nói thật"/><Info label="Xử lý giọng nói" value={yes(voice?.enabled)}/><Info label="Giọng nói thành văn bản" value={!voice?'CHƯA XÁC MINH':voice.stt_ready?'THƯ VIỆN SẴN SÀNG':'THƯ VIỆN CHƯA SẴN SÀNG'}/><Info label="Văn bản thành giọng nói" value={!voice?'CHƯA XÁC MINH':voice.tts_ready?'THƯ VIỆN SẴN SÀNG':'THƯ VIỆN CHƯA SẴN SÀNG'}/><Info label="Thời lượng ghi âm tối đa" value={voice?voice.max_seconds+' giây':'—'}/><details><summary>Thông tin kỹ thuật giọng nói</summary><Info label="Thiết bị" value={voice?voice.stt_device+'/'+voice.stt_compute_type:'Chưa đọc được'}/><Info label="Nhà cung cấp" value={voice?.tts_provider||'Chưa đọc được'}/></details></section>}
function Safety({write,autopilot,role}:{write:S["WriteStatus"]|null;autopilot:Autopilot|null;role:string}){
if(!write||!autopilot)return <Message tone="error" text="Chưa đọc được đầy đủ chốt an toàn. Chưa xác minh chế độ an toàn hoặc quyền ghi; bấm Làm mới trạng thái và kiểm tra kết nối máy chủ."/>;
const safe=!write.enabled&&!autopilot.global_enabled&&!autopilot.meta_enabled;
return <section className="st-safety"><header><ShieldCheck size={22}/><div><strong>Chốt an toàn do máy chủ quyết định</strong><p>Đây là cấu hình vừa đọc, không phải quyền thực thi hoặc nghiệm thu vận hành thật.</p></div><span>{safe?"CÁC CHỐT GHI ĐANG TẮT":"CẦN KIỂM TRA CHỐT GHI"}</span></header><div><SafetyCard title="Ghi dữ liệu Meta" value={yes(write.enabled)} safe={!write.enabled} text={`Mặc định ${write.dry_run_default?"mô phỏng":"thực thi thật"} · thay đổi ngân sách tối đa ${write.max_budget_change_pct}%`}/><SafetyCard title="Tự động hóa toàn hệ thống" value={yes(autopilot.global_enabled)} safe={!autopilot.global_enabled} text={`Giai đoạn ${autopilot.phase} · chế độ ${autopilot.default_mode}`}/><SafetyCard title="Tự động hóa Meta" value={yes(autopilot.meta_enabled)} safe={!autopilot.meta_enabled} text="Chỉ hiệu lực khi chốt toàn hệ thống và chính sách cùng cho phép"/><SafetyCard title="Quyền phê duyệt" value={roleLabel(role)} safe={role==="owner"||role==="admin"} text="Chủ doanh nghiệp/quản trị viên quyết định quy trình và hành động quảng cáo trong phạm vi được cấp"/></div><footer><KeyRound size={15}/>Các biến môi trường nhạy cảm được quản lý ngoài giao diện và không được trả về trình duyệt.</footer></section>}
function SystemStatus({services,meta,google,telegram,voice,automation}:{services:boolean[];meta:Connection|null;google:Connection|null;telegram:Telegram|null;voice:Voice|null;automation:Automation|null}){const responding=services.filter(Boolean).length;return <div className="st-system" aria-label="Thông tin trạng thái cài đặt"><section className="st-health"><ActivityIcon/><div><strong>{responding}/{services.length} nhóm trạng thái phản hồi hợp lệ</strong><p>HTTP thành công hoặc cờ đang bật không chứng minh kết nối hoạt động. Không tự gọi dịch vụ ngoài để báo trạng thái tốt.</p></div><em>{responding===services.length?"ĐÃ ĐỌC ĐỦ":"CHƯA ĐỌC ĐỦ"}</em></section><div>
<Service name="Kết nối Meta" value={meta?`OAuth đã lưu: ${connectionState(meta.status)}`:"Chưa đọc được"}/>
<Service name="Kết nối Google Ads" value={google?`OAuth đã lưu: ${connectionState(google.status)}`:"Chưa đọc được"}/>
<Service name="Bot Telegram cũ" value={telegram?`Vận hành dùng chung ${telegram.enabled?"đang bật":"đang tắt"} · cấu hình ${telegram.configured?"có":"chưa"}`:"Chưa đọc được"}/>
<Service name="Nhận dạng giọng nói" value={voice?`Thư viện trên máy ${voice.stt_ready?"sẵn sàng":"chưa sẵn sàng"} · ${voice.stt_device}/${voice.stt_compute_type}`:"Chưa đọc được"}/>
<Service name="Đọc văn bản" value={voice?`Thư viện trên máy ${voice.tts_ready?"sẵn sàng":"chưa sẵn sàng"} · ${voice.tts_provider}`:"Chưa đọc được"}/>
<Service name="Temporal" value={automation?`Cờ máy chủ ${automation.enabled?"đang bật":"đang tắt"} · ${automation.namespace}`:"Chưa đọc được"}/>
</div></div>}
function PanelHead({icon:Icon,title,sub}:{icon:typeof Settings;title:string;sub:string}){return <header className="st-panel-head"><Icon size={17}/><span><strong>{title}</strong><small>{sub}</small></span></header>}
function Info({label,value}:{label:string;value:string}){return <div className="st-info"><span>{label}</span><i/><strong>{value}</strong></div>}
function Summary({label,value}:{label:string;value:string}){return <div className="st-summary-row"><span>{label}</span><strong>{value}</strong></div>}
function SafetyCard({title,value,safe,text}:{title:string;value:string;safe:boolean;text:string}){return <article><ShieldCheck size={18}/><small>{title}</small><strong className={safe?"safe":"warn"}>{value}</strong><p>{text}</p></article>}
function Service({name,value}:{name:string;value:string}){return <article aria-label={`Trạng thái ${name}`}><i/><span><strong>{name}</strong><small>{value}</small><small>Hoạt động ổn định: Chưa xác minh · Nghiệm thu thật: Chưa xác minh</small></span><em>{value==="Chưa đọc được"?"CHƯA XÁC MINH":"ĐÃ ĐỌC"}</em></article>}
function ActivityIcon(){return <CheckCircle2 size={22}/>}
function Message({text,tone=""}:{text:string;tone?:string}){return <div className={`st-message ${tone}`} role={tone==="error"?"alert":"status"}>{text}</div>}
function Loading(){return <section className="st-loading" aria-label="Đang đọc cài đặt">{[1,2,3,4].map(x=><span key={x}/>)}</section>}
function yes(value:boolean|undefined){return value===undefined?"CHƯA XÁC MINH":value?"ĐANG BẬT":"ĐANG TẮT"}
function roleLabel(role:string){return ({owner:'Chủ doanh nghiệp',admin:'Quản trị viên',operator:'Người thực thi',analyst:'Người phân tích',viewer:'Người xem'} as Record<string,string>)[role]||'Chưa xác minh'}
function connectionState(state:string){return ({connected:'Đã lưu kết nối',disconnected:'Đã ngắt',expired:'Đã hết hạn'} as Record<string,string>)[state]||'Chưa xác minh'}

