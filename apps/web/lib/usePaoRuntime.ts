"use client";
import {useCallback, useEffect, useRef, useState} from "react";
import type {components} from "../../../packages/contracts/schema";
import {readEvents} from "./sse.mjs";
import {initialRuntime, applyRuntimeEvent, type RuntimeEvent} from "./runtime-state.mjs";
import {resolveMembership} from "./tenant-context.mjs";
import {createTenantTransport} from "./tenant-transport.mjs";
import {clearActorStorage, scopedStorageKey} from "./tenant-storage.mjs";
import {clearBusinessDrafts} from "./business-drafts.mjs";
import {runFailureMessage} from "./run-failure-message.mjs";

type Schema = components["schemas"];
type Run = Schema["RunOut"];
type Connection = "idle" | "connecting" | "connected" | "reconnecting" | "disconnected";
const terminal = (status: string) => ["completed", "failed", "cancelled"].includes(status);

export function usePaoRuntime() {
  const [token, setToken] = useState("");
  const tokenRef = useRef("");
  const epoch = useRef(0);
  const [transport] = useState(createTenantTransport);
  const requestTicket = transport.ticket();
  const [scopeRevision, setScopeRevision] = useState(0);
  const profileRef = useRef<Schema["Me"] | null>(null);
  const refreshing = useRef(false);
  const workspaceRef = useRef("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [switchingWorkspace, setSwitchingWorkspace] = useState(false);
  const [me, setMe] = useState<Schema["Me"] | null>(null);
  const [sessions, setSessions] = useState<Schema["SessionOut"][]>([]);
  const [agents, setAgents] = useState<Schema["AgentOut"][]>([]);
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<Schema["MessageOut"][]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [projection, setProjection] = useState(initialRuntime);
  const [connection, setConnection] = useState<Connection>("idle");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const [hydrating, setHydrating] = useState(true);
  const restored = useRef(false);
  const pending = useRef<{session: string; message: string; key: string} | null>(null);
  const activeWorkspace = me?.workspaces.find(member => member.id === workspaceId) || null;

  const installProfile = useCallback((profile: Schema["Me"]) => {
    const saved = sessionStorage.getItem(`pao.workspace.${profile.id}`) || "";
    const member = resolveMembership(profile.workspaces, saved);
    workspaceRef.current = member?.id || "";
    profileRef.current = profile;
    setWorkspaceId(workspaceRef.current); setMe(profile);
  }, []);

  const invalidateTenant = useCallback(() => {
    const previous = workspaceRef.current, actor = profileRef.current?.id;
    epoch.current++; setScopeRevision(transport.invalidate());
    workspaceRef.current = ""; pending.current = null;
    if (actor && previous) sessionStorage.removeItem(scopedStorageKey(actor, previous, "prompt"));
    sessionStorage.removeItem("pao.pending_prompt"); // Discard unscoped legacy data, never import it.
    setWorkspaceId(""); setSessions([]); setMessages([]); setSessionId("");
    setRun(null); setProjection(initialRuntime()); setAgents([]); setConnection("idle");
    setBusy(false); setError("");
  }, [transport]);

  const clearLogin = useCallback(() => {
    clearBusinessDrafts();
    if (typeof window !== "undefined") clearActorStorage(sessionStorage, profileRef.current?.id || "");
    invalidateTenant(); profileRef.current = null;
    tokenRef.current = ""; pending.current = null;
    if (typeof window !== "undefined") sessionStorage.removeItem("pao.access_token");
    setToken(""); setMe(null); setMessages([]); setSessions([]); setSessionId("");
    setWorkspaceId(""); setSwitchingWorkspace(false);
    setAgents([]);
    setRun(null); setProjection(initialRuntime()); setConnection("idle"); setBusy(false); setError("");
  }, [invalidateTenant]);

  const api = useCallback(async <T,>(path: string, method = "GET", body?: unknown, credential = tokenRef.current): Promise<T> => {
    if (workspaceId !== workspaceRef.current) throw new Error("Ngữ cảnh doanh nghiệp đã thay đổi.");
    const result = await transport.request(requestTicket, path, {method, headers: {"Content-Type": "application/json",
      ...(credential ? {Authorization: `Bearer ${credential}`} : {})}, ...(body ? {body: JSON.stringify(body)} : {})});
    if (!result.ok) {
      if (result.status === 401 && credential && credential === tokenRef.current) {
        clearLogin(); setError("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");
        throw new Error("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");
      }
      const payload = await result.json().catch(() => ({}));
      throw new Error(typeof payload.detail === "string" ? payload.detail : `Yêu cầu lỗi (${result.status})`);
    }
    const data = result.status === 204 ? undefined as T : await result.json();
    return data;
  }, [clearLogin, workspaceId, transport, requestTicket]);
  const apiRaw = useCallback(async (path: string, init: RequestInit = {}): Promise<Response> => {
    if (workspaceId !== workspaceRef.current) throw new Error("Ngữ cảnh doanh nghiệp đã thay đổi.");
    const credential=tokenRef.current;
    const headers=new Headers(init.headers);if(credential)headers.set("Authorization",`Bearer ${credential}`);
    const result=await transport.request(requestTicket,path,{...init,headers});
    if(!result.ok){if(result.status===401&&credential===tokenRef.current){clearLogin();setError("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");throw new Error("Phiên đăng nhập hết hạn.");}
      const payload=await result.clone().json().catch(()=>({}));throw new Error(typeof payload.detail==="string"?payload.detail:`Yêu cầu lỗi (${result.status})`);}
    return result;
  },[clearLogin,workspaceId,transport,requestTicket]);

  async function logout() {
    if (!tokenRef.current) {clearLogin(); return;}
    try {await api('/v1/auth/sessions/revoke-current', 'POST'); clearLogin();}
    catch (e) {if(tokenRef.current)setError('Chưa xác minh thu hồi phiên trên máy chủ. '+(e as Error).message);}
  }

  async function logoutAll() {
    try {await api('/v1/auth/sessions/revoke-all', 'POST', {confirm:true});clearLogin();}
    catch (e) {if(tokenRef.current)setError('Chưa xác minh thu hồi tất cả phiên. '+(e as Error).message);}
  }

  const download = useCallback(async (path: string, name: string) => {
    const response = await apiRaw(path), blob = await response.blob();
    const url = transport.objectUrl(requestTicket, blob), link = document.createElement("a");
    link.href = url; link.download = name; link.click();
    setTimeout(() => transport.releaseUrl(url), 1000);
  }, [apiRaw, transport, requestTicket]);

  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    sessionStorage.removeItem("pao.pending_prompt");
    const credential = sessionStorage.getItem("pao.access_token");
    if (!credential) { setHydrating(false); return; }
    const ticket = ++epoch.current;
    tokenRef.current = credential;
    transport.request(requestTicket, "/v1/me", {headers: {Authorization: `Bearer ${credential}`}})
      .then(async response => {
        if (!response.ok) throw new Error("Phiên đăng nhập không còn hiệu lực");
        const profile = await response.json() as Schema["Me"];
        if (ticket !== epoch.current) return;
        setToken(credential); installProfile(profile);
      })
      .catch(() => {
        if (ticket !== epoch.current) return;
        tokenRef.current = ""; sessionStorage.removeItem("pao.access_token");
      })
      .finally(() => { if (ticket === epoch.current) setHydrating(false); });
  }, [installProfile, transport, requestTicket]);

  async function login(email: string, password: string) {
    const ticket = ++epoch.current;
    setBusy(true); setError("");
    try {
      const auth = await api<Schema["Token"]>("/v1/auth/token", "POST", {email, password}, "");
      const profile = await api<Schema["Me"]>("/v1/me", "GET", undefined, auth.access_token);
      if (ticket !== epoch.current) return;
      sessionStorage.setItem("pao.access_token", auth.access_token);
      tokenRef.current = auth.access_token; setToken(auth.access_token); installProfile(profile);
    } catch (e) { if (ticket === epoch.current) setError((e as Error).message); }
    finally { if (ticket === epoch.current) setBusy(false); }
  }

  async function selectWorkspace(id: string) {
    if (!me || switchingWorkspace || !me.workspaces.some(member => member.id === id)) return;
    const credential = tokenRef.current;
    invalidateTenant();
    const ticket = epoch.current, tenantTicket = transport.ticket();
    setSwitchingWorkspace(true);
    sessionStorage.removeItem(`pao.workspace.${me.id}`);
    sessionStorage.removeItem("pao.pending_prompt");
    try {
      const response = await transport.request(tenantTicket, `/v1/workspaces/${encodeURIComponent(id)}/context`, {
        headers: {Authorization: `Bearer ${credential}`}, cache: "no-store",
      });
      if (ticket !== epoch.current || credential !== tokenRef.current) return;
      if (response.status === 401) {clearLogin(); throw new Error("Phiên đăng nhập hết hạn.");}
      if (!response.ok) throw new Error("Không thể chọn doanh nghiệp: kiểm tra lại quyền thành viên.");
      const member = await response.json() as Schema["Membership"];
      if (ticket !== epoch.current || credential !== tokenRef.current) return;
      if (member.id !== id) throw new Error("Doanh nghiệp trả về không khớp lựa chọn.");
      const updated = {...me, workspaces: me.workspaces.map(row => row.id === id ? member : row)};
      profileRef.current = updated; setMe(updated);
      sessionStorage.setItem(`pao.workspace.${me.id}`, id);
      workspaceRef.current = id; setWorkspaceId(id);
    } catch (reason) {if (ticket === epoch.current) setError((reason as Error).message);}
    finally {if (ticket === epoch.current) setSwitchingWorkspace(false);}
  }

  const refreshMemberships = useCallback(async () => {
    if (!tokenRef.current || !profileRef.current || refreshing.current) return;
    const credential = tokenRef.current, ticket = transport.ticket();
    refreshing.current = true;
    try {
      const response = await transport.request(ticket, "/v1/me", {headers: {Authorization: `Bearer ${credential}`}, signal: AbortSignal.timeout(5000)});
      if (response.status === 401) {clearLogin(); setError("Phiên đăng nhập hết hạn."); return;}
      if (!response.ok) throw new Error("Không thể xác minh quyền doanh nghiệp; hãy làm mới hoặc đăng nhập lại.");
      const profile = await response.json() as Schema["Me"];
      const old = profileRef.current;
      if (!old || credential !== tokenRef.current) return;
      if (profile.id !== old.id) throw new Error("Danh tính trả về không khớp phiên đăng nhập.");
      const selected = workspaceRef.current;
      const previous = old.workspaces.find(member => member.id === selected);
      const next = profile.workspaces.find(member => member.id === selected);
      if (selected && (!next || next.role !== previous?.role)) {
        invalidateTenant();
        if (next) {workspaceRef.current = selected; setWorkspaceId(selected);}
        else {sessionStorage.removeItem(`pao.workspace.${old.id}`); setError("Quyền thành viên đã thay đổi. Chọn lại doanh nghiệp được cấp quyền.");}
      }
      profileRef.current = profile; setMe(profile);
    } catch (reason) {
      // Stale probes cannot clear a newer selection or log out a new identity.
      if (ticket === transport.ticket() && credential === tokenRef.current) {
        invalidateTenant(); setError((reason as Error).message);
      }
    } finally {refreshing.current = false;}
  }, [invalidateTenant, clearLogin, transport]);

  useEffect(() => {
    const refresh = () => {if (document.visibilityState === "visible") void refreshMemberships();};
    window.addEventListener("focus", refresh); document.addEventListener("visibilitychange", refresh);
    window.addEventListener("pageshow", refresh);
    const timer = setInterval(refresh, 30000);
    return () => {window.removeEventListener("focus", refresh); window.removeEventListener("pageshow", refresh); document.removeEventListener("visibilitychange", refresh); clearInterval(timer);};
  }, [refreshMemberships]);

  useEffect(() => {
    if (!token || !workspaceId) return;
    let current = true;
    api<Schema["AgentOut"][]>("/v1/agents").then(data => {if (current && tokenRef.current === token) setAgents(data);})
      .catch(e => {if (current && tokenRef.current === token) setError(e.message);});
    api<Schema["SessionOut"][]>(`/v1/sessions?workspace_id=${workspaceId}`)
      .then(data => { if (current && tokenRef.current === token) setSessions(data); })
      .catch(e => { if (current && tokenRef.current === token) setError(e.message); });
    return () => { current = false; };
  }, [api, token, workspaceId]);

  function resetSelection() {
    const ticket = ++epoch.current;
    setRun(null); setProjection(initialRuntime()); setMessages([]); setSessionId("");
    setConnection("idle"); setBusy(true); setError(""); pending.current = null;
    return ticket;
  }
  async function selectSession(id: string) {
    if (!workspaceRef.current || !sessions.some(session => session.id === id && session.workspace_id === workspaceRef.current)) return;
    const ticket = resetSelection();
    try {
      const detail = await api<Schema["SessionDetail"]>(`/v1/sessions/${id}`);
      if (ticket !== epoch.current) return;
      if (detail.workspace_id !== workspaceRef.current) throw new Error("Hội thoại không thuộc doanh nghiệp đang mở.");
      setSessionId(id); setMessages(detail.messages); setRun(detail.active_run);
      setSessions(old => old.map(s => s.id === id ? detail : s));
    } catch (e) { if (ticket === epoch.current) setError((e as Error).message); }
    finally { if (ticket === epoch.current) setBusy(false); }
  }
  async function newSession(brandId: string | null = null) {
    if (!workspaceRef.current || switchingWorkspace) return;
    const ticket = resetSelection();
    try {
      const created = await api<Schema["SessionOut"]>("/v1/sessions", "POST", {workspace_id: workspaceId, brand_id: brandId});
      if (ticket !== epoch.current) return;
      setSessions(old => [created, ...old]); setSessionId(created.id);
    } catch (e) { if (ticket === epoch.current) setError((e as Error).message); }
    finally { if (ticket === epoch.current) setBusy(false); }
  }

  async function deleteSession(id: string) {
    if (busy || (id === sessionId && run && !terminal(run.status))) return false;
    const ticket = epoch.current;
    setBusy(true); setError("");
    try {
      await api<void>(`/v1/sessions/${id}`, "DELETE");
      if (ticket !== epoch.current) return false;
      setSessions(old => old.filter(session => session.id !== id));
      if (id === sessionId) {
        epoch.current++;
        pending.current = null;
        setSessionId(""); setMessages([]); setRun(null); setProjection(initialRuntime());
        setConnection("idle");
      }
      return true;
    } catch (e) { if (ticket === epoch.current) setError((e as Error).message); return false; }
    finally { if (ticket === epoch.current) setBusy(false); }
  }

  async function send(message: string, voiceTurn?: {id:string;version:number}) {
    if (!sessionId || busy || (run && !terminal(run.status))) return false;
    const ticket = epoch.current;
    setBusy(true); setError("");
    if (!pending.current || pending.current.session !== sessionId || pending.current.message !== message) {
      pending.current = {session: sessionId, message, key: crypto.randomUUID()};
    }
    try {
      const created = voiceTurn ? await api<Run>(`/v1/voice/turns/${voiceTurn.id}/submit`, "POST", {
        version:voiceTurn.version,confirm_transcript:true,
      }) : await api<Run>("/v1/runs", "POST", {
        session_id: sessionId, message, request_key: pending.current.key,
      } satisfies Schema["RunCreate"]);
      if (ticket !== epoch.current) return false;
      pending.current = null; setRun(created); setProjection(initialRuntime(created.id));
      const detail = await api<Schema["SessionDetail"]>(`/v1/sessions/${sessionId}`);
      if (ticket !== epoch.current) return false;
      setMessages(old => old.some(m => m.run_id === created.id && m.role === "assistant") &&
        !detail.messages.some(m => m.run_id === created.id && m.role === "assistant") ? old : detail.messages); return true;
    } catch (e) { if (ticket === epoch.current) setError((e as Error).message); return false; }
    finally { if (ticket === epoch.current) setBusy(false); }
  }

  const runId = run?.id;
  useEffect(() => {
    if (!runId || !token) return;
    const abort = new AbortController();
    const ticket = epoch.current;
    const current = () => !abort.signal.aborted && ticket === epoch.current && token === tokenRef.current;
    let snapshot = initialRuntime(runId);
    setProjection(snapshot); setConnection("connecting");
    async function reconcile() {
      const latest = await api<Run>(`/v1/runs/${runId}`);
      if (!current()) return true;
      setRun(latest);
      if (!terminal(latest.status)) return false;
      // Restore authoritative partial/full text even if the stream ended unexpectedly.
      snapshot = {...snapshot, state: "standby", activeAgents: [], response: latest.response,
        terminal: latest.status as "completed" | "failed" | "cancelled"};
      setProjection(snapshot);
      const detail = await api<Schema["SessionDetail"]>(`/v1/sessions/${sessionId}`);
      if (!current()) return true;
      setMessages(detail.messages); setConnection("idle");
      setError(runFailureMessage(latest.error_code));
      return true;
    }
    async function listen() {
      for (let attempt = 0; attempt < 4 && current(); attempt++) {
        try {
          setConnection(attempt ? "reconnecting" : "connecting");
          const res = await transport.request(requestTicket, `/v1/runs/${runId}/events?after=${snapshot.cursor}`, {
            headers: {Authorization: `Bearer ${token}`}, signal: abort.signal,
          });
          if (!current()) return;
          if (res.status === 401) { clearLogin(); setError("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại."); return; }
          if (!res.ok || !res.body) throw new Error(`Kết nối sự kiện lỗi (${res.status})`);
          setConnection("connected");
          for await (const raw of readEvents(res.body)) {
            if (!current()) return;
            snapshot = applyRuntimeEvent(snapshot, raw as RuntimeEvent); setProjection(snapshot);
            if ((raw as RuntimeEvent).run_id === runId && (raw as RuntimeEvent).type === "run.started") {
              setRun(old => old?.id === runId ? {...old, status: "running"} : old);
            }
            if (snapshot.terminal) { if (await reconcile()) return; }
          }
          if (await reconcile()) return;
          throw new Error("Luồng sự kiện gián đoạn");
        } catch (e) {
          if (!current()) return;
          if (attempt === 3) {
            setConnection("disconnected");
            setError(`${(e as Error).message}. Bấm kết nối lại để đồng bộ trạng thái.`); return;
          }
          setConnection("reconnecting");
          await new Promise<void>(resolve => {
            const done = () => {clearTimeout(timer); abort.signal.removeEventListener("abort", done); resolve();};
            const timer = setTimeout(done, 500 * 2 ** attempt);
            abort.signal.addEventListener("abort", done, {once: true});
          });
        }
      }
    }
    void listen();
    return () => { abort.abort(); };
  }, [runId, token, sessionId, api, retry, clearLogin, transport, requestTicket]);

  async function cancel() {
    if (!runId) return;
    const ticket = epoch.current;
    try {
      const cancelled = await api<Run>(`/v1/runs/${runId}/cancel`, "POST");
      if (ticket === epoch.current) setRun(cancelled);
    } catch (e) { if (ticket === epoch.current) setError((e as Error).message); }
  }
  // An authoritative terminal API response wins even if SSE is disconnected.
  const view = run && terminal(run.status)
    ? {...projection, state: "standby" as const, activeAgents: [], response: run.response}
    : projection;
  const storageKey = (kind: string, resource = "") => scopedStorageKey(me?.id || "", workspaceId, kind, resource);
  return {me, activeWorkspace, workspaceId, scopeRevision, switchingWorkspace, selectWorkspace, refreshMemberships, storageKey, download, sessions, sessionId, messages, run, ...view, runId, api, apiRaw,
    availableAgents: agents.filter(a => a.enabled).map(a => a.key),
    connection, connected: connection === "connected", error, busy, hydrating,
    active: !!run && !terminal(run.status),
    login, logout, logoutAll, selectSession, newSession, deleteSession, send, cancel,
    reconnect: () => {setError(""); setRetry(n => n + 1);}};
}
