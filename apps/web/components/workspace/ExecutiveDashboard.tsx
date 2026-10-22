"use client";

import {useEffect, useMemo, useState} from "react";
import {
  Activity, AlertTriangle, ArrowRight, Bot, CheckCircle2, CircleDollarSign,
  ClipboardCheck, Database, Radio, RefreshCw, TrendingUp, Users,
} from "lucide-react";
import type {components} from "../../../../packages/contracts/schema";
import {usePao} from "@/lib/PaoRuntimeContext";
import {coverageLabel,connectionLabel,runtimeLabel} from '@/lib/display-status.mjs';
import PaoAppShell from "./PaoAppShell";
import "./dashboard.css";

type S = components["schemas"];
type Flow = {id:string; kind:string; status:string; approval_status:string; payload:Record<string,unknown>; created_at:string};
type Connection = {configured:boolean; status:string};
type DashboardState = {
  report: S["DashboardOut"] | null;
  anomalies: S["AnomalyOut"][];
  recommendations: S["RecommendationOut"][];
  approvals: S["ActionOut"][];
  attribution: S["AttributionDashboardOut"] | null;
  workflows: Flow[];
  tasks: S["TaskOut"][];
  meta: Connection | null;
  google: Connection | null;
  account: string;
};

const EMPTY: DashboardState = {report:null, anomalies:[], recommendations:[], approvals:[], attribution:null, workflows:[], tasks:[], meta:null, google:null, account:""};

const number = (value: string | number | null | undefined) => {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const compact = (value: number | null, suffix = "") => value == null ? "—" : `${new Intl.NumberFormat("vi-VN", {maximumFractionDigits: value < 10 ? 2 : 0, notation: value >= 1_000_000 ? "compact" : "standard"}).format(value)}${suffix}`;
const money = (value: number | null, currency = "VND") => value == null ? "—" : new Intl.NumberFormat("vi-VN", {style:"currency", currency, maximumFractionDigits:0, notation:value >= 1_000_000 ? "compact" : "standard"}).format(value);

export default function ExecutiveDashboard() {
  const runtime = usePao();
  const membership = runtime.activeWorkspace;
  const workspace = membership?.id || "";
  const role = membership?.role || "viewer";
  const [data, setData] = useState<DashboardState>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!workspace) return;
    let live = true;
    async function load() {
      setLoading(true); setError("");
      const canApprove = role === "owner" || role === "admin";
      const [meta, google, accounts, approvals, workflows, tasks] = await Promise.allSettled([
        runtime.api<Connection>(`/v1/integrations/meta/connection?workspace_id=${workspace}`),
        runtime.api<Connection>(`/v1/integrations/google-ads/connection?workspace_id=${workspace}`),
        runtime.api<S["SnapshotOut"]>(`/v1/integrations/meta/snapshots?workspace_id=${workspace}&kind=accounts`),
        canApprove ? runtime.api<S["ActionOut"][]>(`/v1/approvals?workspace_id=${workspace}&status=pending`) : Promise.resolve([]),
        runtime.api<Flow[]>(`/v1/automation/workflows?workspace_id=${workspace}`),
        runtime.api<S["TaskOut"][]>(`/v1/tasks?workspace_id=${workspace}&limit=100`),
      ]);
      if (!live) return;
      const accountRows = accounts.status === "fulfilled" ? accounts.value.rows : [];
      const account = String(accountRows[0]?.id || "");
      const next: DashboardState = {
        ...EMPTY, account,
        meta: meta.status === "fulfilled" ? meta.value : null,
        google: google.status === "fulfilled" ? google.value : null,
        approvals: approvals.status === "fulfilled" ? approvals.value : [],
        workflows: workflows.status === "fulfilled" ? workflows.value : [],
        tasks: tasks.status === "fulfilled" ? tasks.value : [],
      };
      const failures = [meta, google, accounts, approvals, workflows, tasks].filter(result => result.status === "rejected") as PromiseRejectedResult[];
      if (account) {
        const query = `workspace_id=${workspace}&account_id=${encodeURIComponent(account)}`;
        const [report, anomalies, recommendations, attribution] = await Promise.allSettled([
          runtime.api<S["DashboardOut"]>(`/v1/reports/dashboard?${query}`),
          runtime.api<S["AnomalyOut"][]>(`/v1/ads/anomalies?${query}`),
          runtime.api<S["RecommendationOut"][]>(`/v1/ads/recommendations?${query}`),
          runtime.api<S["AttributionDashboardOut"]>(`/v1/attribution/dashboard?${query}`),
        ]);
        if (!live) return;
        next.report = report.status === "fulfilled" ? report.value : null;
        next.anomalies = anomalies.status === "fulfilled" ? anomalies.value : [];
        next.recommendations = recommendations.status === "fulfilled" ? recommendations.value : [];
        next.attribution = attribution.status === "fulfilled" ? attribution.value : null;
        failures.push(...[report, anomalies, recommendations, attribution].filter(result => result.status === "rejected") as PromiseRejectedResult[]);
      }
      setData(next);
      if (failures.length) setError("Một số nguồn chưa thể đồng bộ. Tổng quan vẫn hiển thị các nguồn còn hoạt động.");
      setLoading(false);
    }
    void load().catch(reason => {if (live) {setError(reason instanceof Error ? reason.message : "Không thể tải tổng quan"); setLoading(false);}});
    return () => {live = false;};
  }, [workspace, role, runtime.api, refreshKey]);

  const report = data.report?.latest_daily || data.report?.latest_weekly || null;
  const actual = useMemo(() => {
    const rows = data.attribution?.metrics || [];
    return rows.reduce((sum, row) => ({
      revenue: sum.revenue + (number(row.actual_revenue) || 0),
      orders: sum.orders + row.actual_orders,
      leads: sum.leads + row.leads,
      sales: sum.sales + row.sales,
    }), {revenue:0, orders:0, leads:0, sales:0});
  }, [data.attribution]);
  const hasActual = Boolean(data.attribution?.metrics.length);
  const revenue = hasActual ? actual.revenue : number(report?.revenue);
  const orders = hasActual ? actual.orders : number(report?.purchases);
  const leads = hasActual ? actual.leads : number(report?.leads);
  const spend = number(report?.spend);
  const clicks = number(report?.clicks);
  const conversion = clicks && orders != null ? orders / clicks * 100 : null;
  const currency = report?.currency || data.attribution?.metrics[0]?.currency || "VND";
  const pendingWorkflows = data.workflows.filter(row => !["completed","failed","cancelled","rejected"].includes(row.status));
  const openTasks = data.tasks.filter(row => !["completed", "cancelled"].includes(row.status));
  const insights = [
    ...data.anomalies.filter(row => !row.resolved).slice(0, 3).map(row => ({id:row.id, level:row.severity, title:`${row.kind} · ${row.resource_id}`, body:`Hiện tại ${row.current_value ?? "—"}, baseline ${row.baseline_value ?? "—"}.`})),
    ...data.recommendations.filter(row => row.status === "active").slice(0, 3).map(row => ({id:row.id, level:"opportunity", title:row.type, body:row.explanation})),
  ].slice(0, 4);

  const kpis = [
    {label:"Doanh thu", value:money(revenue,currency), note:hasActual ? "Doanh thu thực từ CRM/đơn hàng" : "Doanh thu được nền tảng ghi nhận", icon:CircleDollarSign},
    {label:"Lợi nhuận", value:"—", note:"Chưa có dữ liệu giá vốn", icon:TrendingUp},
    {label:"Chi phí quảng cáo", value:money(spend,currency), note:report ? `Dữ liệu đến ${report.data_through || report.period_end}` : "Chưa có báo cáo", icon:Activity},
    {label:"ROAS", value:compact(number(report?.roas),"×"), note:"Doanh thu / Chi phí quảng cáo", icon:TrendingUp},
    {label:"CPA", value:money(number(report?.cpa),currency), note:"Theo chuyển đổi quảng cáo", icon:TargetIcon},
    {label:"Khách tiềm năng", value:compact(leads), note:hasActual ? "Khách tiềm năng từ CRM" : "Khách tiềm năng từ nền tảng", icon:Users},
    {label:"Đơn hàng", value:compact(orders), note:hasActual ? "Đơn hàng thực tế" : "Đơn hàng nền tảng ghi nhận", icon:ClipboardCheck},
    {label:"Tỷ lệ chuyển đổi", value:compact(conversion,"%"), note:"Đơn hàng / Lượt nhấp", icon:CheckCircle2},
  ];

  return <PaoAppShell pageTitle="Tổng quan" pageSubtitle="Trung tâm điều hành — trạng thái doanh nghiệp, công việc và quyết định cần xử lý.">
    <section className="pao-dashboard-intro">
      <div><p>{new Intl.DateTimeFormat("vi-VN",{weekday:"long",day:"2-digit",month:"long",year:"numeric"}).format(new Date())}</p><h2>Chào buổi {new Date().getHours() < 12 ? "sáng" : new Date().getHours() < 18 ? "chiều" : "tối"}.</h2><span>Đây là những gì cần bạn chú ý hôm nay.</span></div>
      <div className="pao-dashboard-health"><i className={data.account ? "online" : ""}/><span>{data.account ? `Tài khoản ${data.account}` : "Chưa có tài khoản quảng cáo được đồng bộ"}</span><button type="button" onClick={() => setRefreshKey(key => key + 1)} disabled={loading}><RefreshCw size={14} className={loading ? "spin" : ""}/> Làm mới</button></div>
    </section>
    {error && <div className="pao-dashboard-warning" role="alert"><AlertTriangle size={16}/>{error}</div>}

    <section className="pao-kpi-grid" aria-label="Các chỉ số chính">
      {kpis.map(item => <article key={item.label} className={loading ? "is-loading" : ""}><header><span>{item.label}</span><item.icon size={16}/></header><strong>{loading ? "···" : item.value}</strong><p>{item.note}</p></article>)}
    </section>

    <div className="pao-dashboard-grid">
      <section className="pao-dashboard-card pao-performance-chart">
        <header><div><p>HIỆU QUẢ</p><h3>Doanh thu / Chi phí</h3></div><span>{report ? `${report.period_start} → ${report.period_end}` : "Chưa có kỳ báo cáo"}</span></header>
        {data.report?.daily_trend.length ? <div className="pao-bars" aria-label="Biểu đồ doanh thu và chi tiêu">
          {data.report.daily_trend.slice(-14).map(row => {
            const max = Math.max(...data.report!.daily_trend.slice(-14).flatMap(item => [number(item.revenue)||0,number(item.spend)||0]),1);
            return <div key={row.id} title={`${row.period_end}: revenue ${row.revenue ?? "—"}, spend ${row.spend ?? "—"}`}><i style={{height:`${Math.max(3,(number(row.revenue)||0)/max*100)}%`}}/><b style={{height:`${Math.max(3,(number(row.spend)||0)/max*100)}%`}}/><small>{row.period_end.slice(8)}</small></div>;
          })}
        </div> : <EmptyState text="Chưa có báo cáo để vẽ biểu đồ. Kết nối Meta Ads và đồng bộ warehouse trước."/>}
        <footer><span><i className="revenue"/>Doanh thu</span><span><i className="spend"/>Chi phí</span><strong>ROAS {compact(number(report?.roas),"×")}</strong></footer>
      </section>

      <section className="pao-dashboard-card pao-insights">
        <CardHeader eyebrow="PHÂN TÍCH PAO" title="Nhận định" action="/analytics"/>
        {insights.length ? insights.map(item => <article key={item.id}><i className={item.level}/><div><strong>{item.title}</strong><p>{item.body}</p></div><ArrowRight size={15}/></article>) : <EmptyState text="Chưa có cảnh báo bất thường hoặc đề xuất đang hoạt động."/>}
      </section>

      <section className="pao-dashboard-card pao-approvals">
        <CardHeader eyebrow="PHÊ DUYỆT" title="Cần bạn phê duyệt" action="/automation"/>
        {data.approvals.length ? data.approvals.slice(0,4).map(row => <article key={row.id}><div><strong>{row.action_type.replaceAll("_"," ")} · {row.resource_type}</strong><p>{row.reason}</p></div><span>{row.dry_run ? "MÔ PHỎNG" : "THỰC TẾ"}</span></article>) : <EmptyState text="Không có đề xuất nào đang chờ phê duyệt."/>}
      </section>

      <section className="pao-dashboard-card pao-channels">
        <CardHeader eyebrow="CÁC KÊNH" title="Tình trạng các kênh" action="/analytics"/>
        <Channel name="Meta Ads" status={data.meta?.status || (data.meta?.configured ? "configured" : "not configured")} active={data.meta?.status === "connected"}/>
        <Channel name="Google Ads" status={data.google?.status || (data.google?.configured ? "configured" : "not configured")} active={data.google?.status === "connected"}/>
        <Channel name="TikTok Ads" status="Chưa hỗ trợ kết nối" active={false}/>
      </section>

      <section className="pao-dashboard-card pao-pipeline">
        <CardHeader eyebrow="KHÁCH HÀNG VÀ DOANH THU" title="Phễu khách hàng" action="/crm"/>
        {hasActual ? <div className="pao-funnel">
          {[["Tiềm năng",actual.leads],["Đủ điều kiện",data.attribution!.metrics.reduce((s,r)=>s+r.qualified_leads,0)],["Bán hàng",actual.sales],["Đơn hàng",actual.orders]].map(([label,value],index)=><div key={String(label)}><span>{label}</span><strong>{value}</strong>{index<3&&<ArrowRight size={14}/>}</div>)}
        </div> : <EmptyState text="Chưa có nguồn CRM/orders. PAO chưa thể tính ROAS thực."/>}
      </section>

      <section className="pao-dashboard-card pao-tasks">
        <CardHeader eyebrow="VẬN HÀNH" title="Công việc và hoạt động PAO" action="/tasks"/>
        <div className="pao-task-row"><ClipboardCheck size={16}/><div><strong>{openTasks.length} công việc đang mở</strong><p>{data.tasks.filter(row => row.status === "running").length} đang thực hiện · {data.tasks.filter(row => row.kind !== "human").length} thuộc trợ lý AI</p></div><span>{data.tasks.length} tổng cộng</span></div>
        <div className="pao-task-row"><Bot size={16}/><div><strong>{runtime.active ? "PAO đang xử lý" : "PAO đang chờ"}</strong><p>{runtime.active ? runtime.activeAgents.join(", ") || "Trợ lý điều hành" : `${runtime.sessions.length} hội thoại trong doanh nghiệp`}</p></div><span className={runtime.active ? "running" : ""}>{runtimeLabel(runtime.state)}</span></div>
        <div className="pao-task-row"><Radio size={16}/><div><strong>Tự động hóa</strong><p>{pendingWorkflows.length ? `${pendingWorkflows.length} quy trình đang hoạt động` : "Không có quy trình đang chờ"}</p></div><span>{data.workflows.length} lượt chạy</span></div>
        <div className="pao-task-row"><Database size={16}/><div><strong>Mức đầy đủ dữ liệu</strong><p>{report ? `${report.coverage_days}/${report.expected_days} ngày trong báo cáo hiện tại` : "Chưa có báo cáo hiện tại"}</p></div><span>{coverageLabel(report)}</span></div>
      </section>
    </div>
  </PaoAppShell>;
}

function TargetIcon({size=16}:{size?:number}) {return <Activity size={size}/>}
function EmptyState({text}:{text:string}) {return <div className="pao-empty"><Database size={20}/><p>{text}</p></div>}
function CardHeader({eyebrow,title,action}:{eyebrow:string;title:string;action:string}) {return <header><div><p>{eyebrow}</p><h3>{title}</h3></div><a href={action}>Mở <ArrowRight size={13}/></a></header>}
function Channel({name,status,active}:{name:string;status:string;active:boolean}) {return <div className="pao-channel"><i className={active?"active":""}/><strong>{name}</strong><span>{connectionLabel(status)}</span></div>}
