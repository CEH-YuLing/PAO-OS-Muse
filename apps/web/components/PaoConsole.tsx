"use client";

import {useState} from "react";
import Link from "next/link";
import PaoWorld from "./PaoWorld";
import {usePao} from "../lib/PaoRuntimeContext";
import {WORKSPACE_MODULES} from "../lib/workspace-modules";
import EnterpriseSelector from "./workspace/EnterpriseSelector";
import "./console.css";

export default function PaoConsole({overviewOpen}: {overviewOpen: boolean}) {
  const runtime = usePao();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  if (!runtime.me) return <div className="pao-console pao-console-login">
    <section className="pao-visual" aria-label="Trạng thái PAO" data-runtime-state={runtime.state}>
      <PaoWorld runtimeState={runtime.state} activeAgents={runtime.activeAgents} availableAgents={runtime.availableAgents} />
    </section>
    <div className="pao-login-layer">
      <section className="pao-login-dialog" role="dialog" aria-modal="true" aria-labelledby="pao-login-title">
        <header><span className="pao-eyebrow">PAO · KHÔNG GIAN LÀM VIỆC</span><h1 id="pao-login-title">Đăng nhập</h1>
          <p>Truy cập không gian làm việc của doanh nghiệp.</p></header>
        <form onSubmit={async e => {e.preventDefault(); await runtime.login(email, password); setPassword("");}}>
          <label>Email<input autoFocus type="email" autoComplete="username" disabled={runtime.hydrating||runtime.busy} required value={email} onChange={e => setEmail(e.target.value)} /></label>
          <label>Mật khẩu<input type="password" autoComplete="current-password" disabled={runtime.hydrating||runtime.busy} required value={password} onChange={e => setPassword(e.target.value)} /></label>
          <button disabled={runtime.hydrating||runtime.busy}>{runtime.hydrating ? "Đang kiểm tra phiên…" : runtime.busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
        </form>
        {runtime.error && <div className="pao-error" role="alert">{runtime.error}</div>}
        <div className="pao-login-invite"><span>Nhân sự được mời</span><Link className="pao-invite-button" href="/join">Tạo tài khoản bằng mã mời</Link><small>Chỉ dành cho nhân sự được chủ doanh nghiệp mời.</small></div>
      </section>
    </div>
  </div>;

  const renderRail = (side: "left" | "right") => <div className={`pao-tab-rail pao-tab-rail-${side}`}>
    {WORKSPACE_MODULES.filter((_, index) => side === "left" ? index < 6 : index >= 6).map(tab => {
      const selected = tab.id === "dashboard";
      return <Link
        key={tab.id}
        id={`pao-tab-${tab.id}`}
        className="pao-workspace-tab"
        href={tab.href}
        aria-current={selected ? "page" : undefined}
      >
        <span className="pao-tab-copy"><small>{tab.number}</small>{tab.label}</span>
      </Link>;
    })}
  </div>;

  return <div className="pao-console pao-console-workspace">
    <section className="pao-visual" aria-label="PAO workspace" data-runtime-state={runtime.state}>
      <PaoWorld
        runtimeState={runtime.state}
        activeAgents={runtime.activeAgents}
        availableAgents={runtime.availableAgents}
        showAgents
        statusHint="PAO OPERATING SYSTEM · DASHBOARD"
      />
    </section>

    <div className="pao-session-strip">
      <span>{runtime.activeWorkspace?.name || "Chưa chọn doanh nghiệp"}</span>
      <button type="button" onClick={runtime.logout}>Đăng xuất</button>
    </div>
    <div className="pao-orb-enterprise"><EnterpriseSelector/></div>
    {!runtime.activeWorkspace && <div className="pao-workspace-error" role="status">{runtime.me.workspaces.length ? "Chọn doanh nghiệp trước khi làm việc." : "Tài khoản chưa được cấp quyền doanh nghiệp."}</div>}

    <nav id="pao-workspace-tabs" className={`pao-workspace-nav${overviewOpen ? " is-open" : ""}`} aria-label="Điều hướng PAO" aria-hidden={!overviewOpen}>
      {renderRail("left")}
      {renderRail("right")}
    </nav>

    {runtime.error && <div className="pao-workspace-error" role="alert">{runtime.error}</div>}
  </div>;
}
