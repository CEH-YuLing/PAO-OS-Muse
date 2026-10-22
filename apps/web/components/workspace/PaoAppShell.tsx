"use client";

import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {FormEvent, useEffect, useMemo, useRef, useState} from "react";
import {
  BarChart3, Bell, Bot, BrainCircuit, ChevronLeft, ChevronRight, CircleDollarSign,
  FileImage, Gauge, LayoutDashboard, Menu, Network, Search, Settings, Sparkles,
  Target, Workflow, X,
} from "lucide-react";
import {usePao} from "@/lib/PaoRuntimeContext";
import EnterpriseSelector from "./EnterpriseSelector";
import {ThemeToggle} from '@/lib/ThemeProvider';
import {WORKSPACE_GROUPS, WORKSPACE_MODULES, WORKSPACE_SUBVIEWS} from "@/lib/workspace-modules";
import "./workspace.css";

const ICONS: Record<string, React.ComponentType<{size?: number; strokeWidth?: number}>> = {
  dashboard: LayoutDashboard, "pao-ai": Sparkles, tasks: Target, "meta-ads": CircleDollarSign,
  "tiktok-ads": FileImage, "google-ads": Search, crm: Network, "content-creative": FileImage,
  analytics: BarChart3, automation: Workflow, knowledge: BrainCircuit, settings: Settings,
};

export default function PaoAppShell({children, pageTitle, pageSubtitle, pageActions}: {
  children: React.ReactNode;
  pageTitle: string;
  pageSubtitle: string;
  pageActions?: React.ReactNode;
}) {
  const runtime = usePao();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const copilotClose=useRef<HTMLButtonElement>(null);
  const copilotTrigger=useRef<HTMLElement|null>(null);
  function openCopilot(){copilotTrigger.current=document.activeElement as HTMLElement;setCopilotOpen(true)}
  function closeCopilot(){setCopilotOpen(false);copilotTrigger.current?.focus()}
  useEffect(()=>{if(copilotOpen)copilotClose.current?.focus()},[copilotOpen]);
  useEffect(()=>{if(!mobileOpen)return;const close=(event:KeyboardEvent)=>{if(event.key==='Escape')setMobileOpen(false)};document.addEventListener('keydown',close);return()=>document.removeEventListener('keydown',close)},[mobileOpen]);
  const [query, setQuery] = useState("");
  const [businessPlanning,setBusinessPlanning]=useState(false);
  const businessApi=runtime.api,businessWorkspace=runtime.activeWorkspace?.id;
  useEffect(()=>{
    let live=true;setBusinessPlanning(false);
    if(businessWorkspace)void businessApi<{available:boolean;can_manage:boolean}>(`/v1/workspaces/${businessWorkspace}/business-planning/status`)
      .then(value=>{if(live)setBusinessPlanning(value.available===true&&value.can_manage===true)}).catch(()=>{});
    return()=>{live=false};
  },[businessApi,businessWorkspace]);
  const [system, setSystem] = useState<{automation:boolean|null;voice:boolean|null;telegram:boolean|null}>({automation: null, voice: null, telegram: null});

  useEffect(() => {
    if (!runtime.hydrating && !runtime.me) router.replace("/");
  }, [runtime.hydrating, runtime.me, router]);
  useEffect(() => setMobileOpen(false), [pathname]);
  useEffect(() => {
    if (!runtime.me) return;
    let live = true;
    Promise.allSettled([
      runtime.api<{enabled: boolean}>("/v1/automation/status"),
      runtime.api<{enabled: boolean}>("/v1/voice/status"),
      runtime.api<{enabled: boolean}>("/v1/telegram/status"),
    ]).then(([automation, voice, telegram]) => {
      if (!live) return;
      setSystem({
        automation: automation.status === "fulfilled" && typeof automation.value.enabled==='boolean' ? automation.value.enabled : null,
        voice: voice.status === "fulfilled" && typeof voice.value.enabled==='boolean' ? voice.value.enabled : null,
        telegram: telegram.status === "fulfilled" && typeof telegram.value.enabled==='boolean' ? telegram.value.enabled : null,
      });
    });
    return () => {live = false;};
  }, [runtime.api, runtime.me]);

  const current = useMemo(
    () => WORKSPACE_MODULES.find(module => module.href === pathname || WORKSPACE_SUBVIEWS.some(view => view.parent === module.id && view.href === pathname)),
    [pathname],
  );
  const membership = runtime.activeWorkspace;

  if (runtime.hydrating || !runtime.me) {
    return <main className="pao-route-loading" aria-live="polite"><span /><p>Đang khôi phục phiên PAO…</p></main>;
  }
  if (!membership) return <main className="pao-route-loading">
    <h1>Chọn doanh nghiệp làm việc</h1><EnterpriseSelector/>
    {!runtime.me.workspaces.length && <p>Tài khoản chưa thuộc doanh nghiệp nào. Liên hệ quản trị viên để được cấp quyền.</p>}
    {runtime.error && <p role="alert">{runtime.error}</p>}
    <button type="button" onClick={runtime.logout}>Đăng xuất</button>
  </main>;

  function askPao(event: FormEvent) {
    event.preventDefault();
    const prompt = query.trim();
    if (!prompt) return;
    sessionStorage.setItem(runtime.storageKey("prompt"), prompt);
    if (pathname === "/pao-ai") {
      window.dispatchEvent(new CustomEvent("pao:prompt", {detail: {text: prompt, actor: runtime.me?.id, workspace: runtime.workspaceId, revision: runtime.scopeRevision}}));
      sessionStorage.removeItem(runtime.storageKey("prompt"));
    } else {
      router.push("/pao-ai");
    }
    setQuery("");
  }

  return <div className={`pao-app${collapsed ? " is-collapsed" : ""}`}>
    <a className="pao-skip-link" href="#pao-main">Bỏ qua điều hướng, đến nội dung</a>
    <button className="pao-mobile-menu" type="button" aria-label="Mở điều hướng" onClick={() => setMobileOpen(true)}><Menu size={20}/></button>
    <aside className={`pao-sidebar${mobileOpen ? " is-mobile-open" : ""}`}>
      <div className="pao-sidebar-brand">
        <Link href="/" aria-label="Trở về PAO Orb"><span className="pao-brand-mark">P</span><span className="pao-brand-word">PAO</span></Link>
        <button type="button" aria-label={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"} onClick={() => setCollapsed(value => !value)}>
          {collapsed ? <ChevronRight size={16}/> : <ChevronLeft size={16}/>}
        </button>
        <button className="pao-mobile-close" type="button" aria-label="Đóng điều hướng" onClick={() => setMobileOpen(false)}><X size={18}/></button>
      </div>
      <nav aria-label="Các module PAO">
        {WORKSPACE_GROUPS.map(group => <section key={group}>
          <h2>{{OVERVIEW:'TỔNG QUAN',GROWTH:'TĂNG TRƯỞNG',INTELLIGENCE:'TRÍ TUỆ',SYSTEM:'HỆ THỐNG'}[group]}</h2>
          {WORKSPACE_MODULES.filter(module => module.group === group).map(module => {
            const Icon = ICONS[module.id] || Gauge;
            const selected = pathname === module.href;
            return <div key={module.id} className="pao-nav-module"><Link href={module.href} data-active={current?.id===module.id} aria-current={selected ? "page" : undefined} title={collapsed ? module.label : undefined}>
              <Icon size={18} strokeWidth={1.7}/><span>{module.label}</span><small>{module.number}</small>
            </Link><div className="pao-subviews">{WORKSPACE_SUBVIEWS.filter(view=>view.parent===module.id&&(!view.requiresPlanning||businessPlanning)).map(view=><Link key={view.href} href={view.href} aria-current={pathname===view.href?'page':undefined} title={view.label}><span>{view.label}</span></Link>)}</div></div>;
          })}
        </section>)}
      </nav>
      <div className="pao-sidebar-enterprise"><EnterpriseSelector/></div>
      <footer>
        <span className="pao-user-avatar">{runtime.me.email.slice(0, 1).toUpperCase()}</span>
        <div><strong>{membership.name}</strong><small>{runtime.me.email}</small></div>
        <button type="button" onClick={() => void runtime.logout()}>Đăng xuất</button>
      </footer>
    </aside>
    {mobileOpen && <button className="pao-sidebar-scrim" aria-label="Đóng điều hướng" onClick={() => setMobileOpen(false)}/>}

    <div className="pao-app-stage">
      <header className="pao-topbar">
        <div className="pao-topbar-context">
          <EnterpriseSelector/>
        </div>
        <form className="pao-ask-bar" onSubmit={askPao}>
          <Sparkles size={17}/><input aria-label="Hỏi PAO" placeholder={`Hỏi PAO về ${current?.label || pageTitle}…`} value={query} onChange={event => setQuery(event.target.value)}/>
          <kbd>↵</kbd>
        </form>
        <div className="pao-topbar-actions">
          <ThemeToggle compact/>
          <Link href="/knowledge" aria-label="Tìm kiếm trong kho tri thức"><Search size={17}/></Link>
          <Link href="/automation/review" aria-label="Mở kết quả và phê duyệt"><Bell size={17}/></Link>
          <Link href="/settings" aria-label="Cài đặt"><Settings size={17}/></Link>
          <span className="pao-top-avatar">{runtime.me.email.slice(0, 1).toUpperCase()}</span>
        </div>
      </header>
      <details className="pao-system-details"><summary>Thông tin kết nối <small>Trạng thái kỹ thuật · bấm để xem</small></summary>
      <div className="pao-system-strip" aria-label="Thông tin vận hành PAO">
        <span className="pao-system-title">THÔNG TIN VẬN HÀNH</span>
        <span>API <b>XEM CÀI ĐẶT</b></span>
        <span><i className={runtime.connected ? "online" : ""}/> HỘI THOẠI <b>{runtime.connected ? "ĐÃ KẾT NỐI" : "CHƯA KẾT NỐI"}</b></span>
        <span>CỜ TEMPORAL <b>{system.automation===null?'CHƯA XÁC MINH':system.automation?'BẬT':'TẮT'}</b></span>
        <span>CỜ GIỌNG NÓI <b>{system.voice===null?'CHƯA XÁC MINH':system.voice?'BẬT':'TẮT'}</b></span>
        <span>CỜ TELEGRAM CŨ <b>{system.telegram===null?'CHƯA XÁC MINH':system.telegram?'BẬT':'TẮT'}</b></span>
      </div></details>

      <main id="pao-main" tabIndex={-1} className="pao-page">
        <header className="pao-page-heading">
          <div><span>HỆ ĐIỀU HÀNH PAO · {current?.number || "00"}</span><h1>{pageTitle}</h1><p>{pageSubtitle}</p></div>
          {pageActions?<div className="pao-page-actions">{pageActions}<button className="pao-page-ai" type="button" onClick={openCopilot}><Sparkles size={16}/> Hỏi PAO</button></div>:<button className="pao-page-ai" type="button" onClick={openCopilot}><Sparkles size={16}/> Hỏi PAO</button>}
        </header>
        {pathname==='/dashboard'&&<section className="pao-get-started" aria-labelledby="pao-start-title">
          <h2 id="pao-start-title">Bắt đầu một chu kỳ làm việc</h2><p>Chọn đúng doanh nghiệp ở thanh trên cùng, rồi đi từ dữ liệu đến kế hoạch và kết quả.</p>
          <div className="pao-start-links"><Link href="/knowledge"><b>1</b><span><strong>Chuẩn bị tri thức</strong><small>Tập hợp tài liệu và thông tin của doanh nghiệp.</small></span></Link>
          <Link href={businessPlanning?'/business-planning':'/tasks'}><b>2</b><span><strong>{businessPlanning?'Lập kế hoạch và giao việc':'Quản lý công việc'}</strong><small>Chia đầu việc, chọn trợ lý và theo dõi tiến độ.</small></span></Link>
          <Link href="/automation/review"><b>3</b><span><strong>Xem kết quả và phê duyệt</strong><small>Đối chiếu nguồn trước khi cho phép bước tiếp theo.</small></span></Link></div>
        </section>}
        {children}
      </main>
    </div>

    <button className="pao-copilot-launcher" type="button" aria-label="Mở PAO Copilot" onClick={openCopilot}><Bot size={21}/><span>PAO</span></button>
    {copilotOpen&&<aside className="pao-copilot is-open" role="dialog" aria-label="PAO Copilot" onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();closeCopilot()}}}>
      <header><div><Sparkles size={17}/><strong>PAO Copilot</strong></div><button ref={copilotClose} type="button" aria-label="Đóng PAO Copilot" onClick={closeCopilot}><X size={18}/></button></header>
      <div className="pao-copilot-body">
        <span className="pao-state-chip">NGỮ CẢNH · {current?.label || pageTitle}</span>
        <h2>Trao đổi với PAO về khu vực này.</h2>
        <p>Mở hội thoại và nêu yêu cầu cụ thể. Khu vực đang xem không tự cấp quyền đọc dữ liệu hoặc thực hiện hành động.</p>
        <div className="pao-copilot-signal"><i className={runtime.active ? "active" : ""}/><span>{runtime.active ? `${runtime.activeAgents.length} agent đang xử lý` : "Không có tác vụ AI đang chạy"}</span></div>
        <button type="button" onClick={() => {setCopilotOpen(false); router.push("/pao-ai");}}>Mở PAO AI</button>
      </div>
    </aside>}
  </div>;
}
