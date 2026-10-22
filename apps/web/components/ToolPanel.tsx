"use client";
import {useEffect, useRef, useState} from "react";
import type {components} from "../../../packages/contracts/schema";
type Snapshot = components["schemas"]["ToolSnapshot"];
type Info = components["schemas"]["ToolInfo"];
export default function ToolPanel({api, runId, role}: {api: <T>(path: string, method?: string, body?: unknown) => Promise<T>; runId: string; role?: string}) {
  const [snapshot, setSnapshot] = useState<Snapshot>({calls: [], audit: []});
  const [registry, setRegistry] = useState<Info[]>([]);
  const [name, setName] = useState("web.search");
  const [fields, setFields] = useState<Record<string,string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const live = useRef(true);
  const pending = useRef<{payload: string; key: string} | null>(null);
  useEffect(() => {live.current = true; return () => {live.current = false;};}, []);
  useEffect(() => {
    let current = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const [data, tools] = await Promise.all([api<Snapshot>(`/v1/runs/${runId}/tools`), api<Info[]>("/v1/tools")]);
        if (current) {setSnapshot(data); setRegistry(tools);}
      } catch (e) {if (current) setError((e as Error).message);}
      if (current) timer = setTimeout(() => void load(), 3000);
    }
    void load();
    return () => {current = false; clearTimeout(timer);};
  }, [api, runId, refresh]);
  const labels: Record<string,string> = {pending:"Chờ bạn duyệt",queued:"Đã xếp hàng",running:"Đang thực thi",completed:"Hoàn tất",failed:"Thất bại",rejected:"Đã từ chối",cancelled:"Đã hủy",unknown:"Chưa xác định kết quả — không tự chạy lại",expired:"Hết hạn duyệt"};
  async function mutate(path: string, body: unknown) {
    setBusy(true); setError("");
    try {await api(path,"POST",body); if (live.current) setRefresh(n => n + 1); return true;}
    catch (e) {if (live.current) setError((e as Error).message); return false;}
    finally {if (live.current) setBusy(false);}
  }
  const allowed = registry.filter(t => t.enabled && role !== "viewer" && (!t.requires_approval || ["owner","admin","operator"].includes(role || "")));
  const fieldNames = name === "web.search" ? ["query"] : name === "email.mock_send" ? ["to","subject","body"] : ["title","starts_at","ends_at"];
  const fieldLabels: Record<string,string> = {query:"Từ khóa tìm kiếm",to:"Email người nhận mô phỏng",subject:"Tiêu đề email",body:"Nội dung email",title:"Tên sự kiện",starts_at:"Bắt đầu",ends_at:"Kết thúc"};
  return <details className="pao-tools"><summary>Công cụ và phê duyệt ({snapshot.calls.filter(c => c.status === "pending").length})</summary>
    <p>Tìm kiếm gửi từ khóa đến các máy tìm kiếm qua SearXNG. Email và lịch chỉ mô phỏng, không gửi thư hoặc tạo lịch bên ngoài.</p>
    <p role="status">Công cụ đang thực thi: {snapshot.calls.filter(c => c.status === "running").map(c => c.name).join(", ") || "Không có"}</p>
    {!!allowed.length && <form onSubmit={async e => {
      e.preventDefault();
      const args: Record<string,string> = Object.fromEntries(fieldNames.map(key => [key, fields[key] || ""]));
      if (name === "calendar.mock_create") {args.starts_at = new Date(args.starts_at).toISOString(); args.ends_at = new Date(args.ends_at).toISOString();}
      const payload = JSON.stringify({name,agent:"chief_of_staff",arguments:args});
      if (pending.current?.payload !== payload) pending.current = {payload,key:crypto.randomUUID()};
      if (await mutate(`/v1/runs/${runId}/tools`,{...JSON.parse(payload),request_key:pending.current.key})) {pending.current = null; if (live.current) setFields({});}
    }}>
      <label htmlFor="tool-name">Công cụ</label><select id="tool-name" value={name} onChange={e => {setName(e.target.value);setFields({});}}>{allowed.map(t => <option key={t.name}>{t.name}</option>)}</select>
      {fieldNames.map(key => <label key={key}>{fieldLabels[key]}<input required maxLength={key === "body" ? 2000 : key === "query" ? 300 : key === "to" ? 254 : 160} type={key.endsWith("_at") ? "datetime-local" : key === "to" ? "email" : "text"} value={fields[key] || ""} onChange={e => setFields({...fields,[key]:e.target.value})}/></label>)}
      <button disabled={busy || !allowed.some(t => t.name === name)}>{name === "web.search" ? "Tìm kiếm web" : "Tạo đề xuất mô phỏng"}</button>
    </form>}
    {snapshot.calls.map(call => <article className="pao-message" key={call.id}>
      <strong>{call.name} · {labels[call.status] || call.status}</strong>
      <dl>{Object.entries(call.arguments).map(([key,value]) => <div key={key}><dt>{fieldLabels[key] || key}</dt><dd style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{String(value)}</dd></div>)}</dl>
      {call.status === "pending" && <div className="pao-toolbar"><button disabled={busy || !["owner","admin","operator"].includes(role || "")} onClick={() => void mutate(`/v1/tools/calls/${call.id}/decision`,{decision:"approve",version:call.version})}>Duyệt mô phỏng</button><button disabled={busy} onClick={() => void mutate(`/v1/tools/calls/${call.id}/decision`,{decision:"reject",version:call.version})}>Từ chối</button></div>}
      {call.status === "completed" && call.name !== "web.search" && <p>Đã hoàn tất mô phỏng. Không gửi email hay tạo sự kiện bên ngoài.</p>}
      {call.name === "web.search" && call.status === "completed" && <>
        {Array.isArray(call.result.results) && (call.result.results as {title:string;url:string;snippet:string}[]).filter(r => /^https?:\/\//i.test(r.url)).map((result,index) => <div key={index}><a href={result.url} target="_blank" rel="noopener noreferrer">{result.title || result.url}</a><p>{result.snippet}</p></div>)}
        {Array.isArray(call.result.results) && !call.result.results.length && <p>Không tìm thấy kết quả. Thử từ khóa khác.</p>}
        {Number(call.result.unresponsive_engines) > 0 && <p>Một số máy tìm kiếm không phản hồi; kết quả có thể chưa đầy đủ.</p>}
      </>}
      {call.error_code && <p>{call.error_code}</p>}
    </article>)}
    <details><summary>Nhật ký công cụ</summary><ol>{snapshot.audit.map(item => <li key={item.id}>{item.created_at} · {item.event}</li>)}</ol></details>
    {error && <p className="pao-error" role="alert">{error} <button onClick={() => {setError("");setRefresh(n => n + 1);}}>Tải lại công cụ</button></p>}
  </details>;
}
