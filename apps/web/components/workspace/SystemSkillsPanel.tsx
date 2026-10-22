"use client";
import {useEffect, useRef, useState} from "react";
import {Bot} from "lucide-react";
import type {components} from "../../../../packages/contracts/schema";
import {usePao} from "@/lib/PaoRuntimeContext";
import "@/components/workspace/settings-platform.css";

type Skill = components["schemas"]["SkillView"];
type Brief = components["schemas"]["BriefPreviewOut"];
type Replay = components["schemas"]["SkillReplay"];
const names: Record<string, string> = {
  "daily-business-brief": "Báo cáo doanh nghiệp",
  "investigate-ads-drop": "Điều tra hiệu quả quảng cáo giảm",
  "creative-fatigue-review": "Đánh giá creative fatigue",
};
const previewNames = {...names, attribution: "Đối chiếu attribution đã lưu"};
function known(value: unknown) {
  return typeof value === "string" || typeof value === "number" ? String(value) : "chưa biết";
}

export default function SystemSkillsPanel() {
  const runtime = usePao();
  const workspace = runtime.activeWorkspace?.id;
  const [data, setData] = useState<{workspace: string; skills: Skill[]}>({workspace: "", skills: []});
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [previewSkill, setPreviewSkill] = useState("daily-business-brief");
  const [accountId, setAccountId] = useState("");
  const [platform, setPlatform] = useState("meta");
  const [preview, setPreview] = useState<{workspace: string; value?: Brief; error?: string; busy?: boolean}>({workspace: ""});
  const requestGeneration = useRef(0);
  const replayGeneration = useRef(0);
  const [replayId, setReplayId] = useState("");
  const [replay, setReplay] = useState<{workspace: string; value?: Replay; error?: string; busy?: boolean}>({workspace: ""});
  function clearReplay() {
    replayGeneration.current += 1;
    setReplay({workspace: ""});
  }
  async function readReplay() {
    if (!workspace) return;
    const requestedWorkspace = workspace;
    const generation = ++replayGeneration.current;
    setReplay({workspace: requestedWorkspace, busy: true});
    try {
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(replayId.trim())) throw new Error("Run ID phải là UUID hợp lệ.");
      const value = await runtime.api<Replay>(`/v1/runs/${replayId.trim()}/skill-replay`);
      if (generation === replayGeneration.current) setReplay({workspace: requestedWorkspace, value});
    } catch (reason) {
      if (generation === replayGeneration.current) setReplay({workspace: requestedWorkspace, error: (reason as Error).message});
    }
  }
  function clearPreview() {
    requestGeneration.current += 1;
    setPreview({workspace: ""});
  }
  async function readBrief() {
    if (!workspace) return;
    const requestedWorkspace = workspace;
    const generation = ++requestGeneration.current;
    setPreview({workspace: requestedWorkspace, busy: true});
    try {
      const path = previewSkill === "attribution" ? "/v1/skills/investigate-ads-drop/attribution-preview"
        : previewSkill === "daily-business-brief" ? "/v1/skills/daily-business-brief/preview" : `/v1/skills/${previewSkill}/analysis-preview`;
      const value = await runtime.api<Brief>(path, "POST", {
        workspace_id: requestedWorkspace, input: {start_date: startDate, end_date: endDate,
          ...(previewSkill === "daily-business-brief" ? {} : {account_id: accountId, platform})},
      });
      if (generation === requestGeneration.current) setPreview({workspace: requestedWorkspace, value});
    } catch (reason) {
      if (generation === requestGeneration.current) setPreview({workspace: requestedWorkspace, error: (reason as Error).message});
    }
  }
  useEffect(() => {
    requestGeneration.current += 1;
    replayGeneration.current += 1;
    setReplay({workspace: ""});
    setPreview({workspace: ""});
    if (!workspace) return;
    let live = true;
    setError("");
    setData({workspace: "", skills: []});
    runtime.api<Skill[]>(`/v1/skills?workspace_id=${workspace}`)
      .then(skills => {if (live) setData({workspace, skills});})
      .catch(reason => {if (live) setError((reason as Error).message);});
    return () => {live = false; requestGeneration.current += 1; replayGeneration.current += 1;};
  }, [runtime.api, workspace, reload]);
  return <>

    <p>Ba kỹ năng có bản xem trước và Chief command routing chỉ đọc. Ads/creative cần nền tảng, account và hai ngày rõ ràng; chưa hỗ trợ mọi cách diễn đạt tự do.</p>
    <p>Ví dụ trong PAO AI: “Điều tra hiệu quả quảng cáo giảm meta act_123 từ 2026-10-01 đến 2026-10-05” hoặc “Đánh giá creative fatigue meta act_123 từ 2026-10-01 đến 2026-10-05”.</p>
    <section className="skills-preview" aria-label="Bản xem trước báo cáo doanh nghiệp">
      <h2>Xem trước kỹ năng</h2>
      <p>Chỉ đọc dữ liệu đã lưu thuộc kết nối của bạn, đúng kỳ. Không đồng bộ, không phân tích mới, không sửa hoặc gửi dữ liệu. Tín hiệu Ads/creative không chứng minh nguyên nhân.</p>
      <form onSubmit={event => {event.preventDefault(); void readBrief();}}>
        <label>Kỹ năng xem trước <select value={previewSkill} onChange={event => {setPreviewSkill(event.target.value); clearPreview();}}>
          {Object.entries(previewNames).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select></label>{" "}
        {previewSkill !== "daily-business-brief" && <>
          <label>Nền tảng <select value={platform} onChange={event => {setPlatform(event.target.value); clearPreview();}}>
            <option value="meta">Meta</option><option value="google_ads">Google Ads (chưa hỗ trợ)</option>
          </select></label>{" "}
          <label>Tài khoản Ads <input required maxLength={100} pattern="[a-zA-Z0-9_-]+" value={accountId} onChange={event => {setAccountId(event.target.value); clearPreview();}}/></label>{" "}
        </>}
        <label>Từ ngày <input type="date" required value={startDate} onChange={event => {setStartDate(event.target.value); clearPreview();}}/></label>{" "}
        <label>Đến ngày <input type="date" required value={endDate} onChange={event => {setEndDate(event.target.value); clearPreview();}}/></label>{" "}
        <button type="submit" disabled={preview.workspace === workspace && preview.busy}>Đọc bản xem trước</button>
      </form>
      {previewSkill === "attribution" && <p>Chọn Meta, nhập tài khoản dạng act_123 và kỳ cần đọc. Chỉ xem phân bổ đã lưu; không tạo phân tích mới. Doanh thu Ads và orders được phân bổ không phải tổng doanh thu doanh nghiệp đã xác minh.</p>}
      {preview.workspace === workspace && <>
        {preview.busy && <p role="status">Đang đọc dữ liệu…</p>}
        {preview.error && <p role="alert">{preview.error}</p>}
        {preview.value && <div>
          <p>Kỹ năng: {names[preview.value.skill.id]} · Kỳ đã đọc: {String(preview.value.input.start_date)} → {String(preview.value.input.end_date)}</p>
          <p>{preview.value.result.summary}</p>
          {preview.value.tools.some(tool => tool.tool === "business.attribution.read") && <section aria-label="Kết quả attribution">
            <p role="status">Chưa xác minh doanh thu doanh nghiệp. Không cộng lẫn tiền tệ; giá trị chưa biết không được thay bằng 0.</p>
            <p>Tài khoản đã đọc: {String(preview.value.input.account_id)} · {String(preview.value.input.platform)}</p>
            <p>Bảng có thể cuộn ngang trên điện thoại để đọc đủ cột doanh thu và nguồn.</p>
            {preview.value.tools.filter(tool => tool.tool === "business.attribution.read").map(tool => {
              const rows = Array.isArray(tool.data.metrics) ? tool.data.metrics.filter((row): row is Record<string, unknown> => !!row && typeof row === "object").slice(0, 49) : [];
              return rows.length ? <div key={tool.tool} style={{overflowX: "auto", maxWidth: "100%"}}><table>
                <caption>Snapshot phân bổ đã lưu — không phải tổng doanh thu đã đối soát</caption>
                <thead><tr><th scope="col">Chiến dịch</th><th scope="col">Tiền tệ</th><th scope="col">Doanh thu Ads báo cáo</th><th scope="col">Doanh thu orders được phân bổ</th><th scope="col">Số orders được phân bổ</th><th scope="col">Nguồn</th></tr></thead>
                <tbody>{rows.map((row, index) => <tr key={known(row.id) + index}>
                  <td>{known(row.campaign_id)}</td><td>{known(row.currency)}</td><td>{known(row.platform_reported_revenue)}</td>
                  <td>{known(row.attributed_paid_order_revenue)}</td><td>{known(row.attributed_paid_order_count)}</td>
                  <td style={{overflowWrap: "anywhere"}}>attribution-metric:{known(row.id)}</td>
                </tr>)}</tbody>
              </table></div> : <p key={tool.tool}>Chưa có metric attribution để hiển thị. Xem lý do thiếu dữ liệu bên dưới.</p>;
            })}
          </section>}
          <ul>{(preview.value.result.missing_data || []).map(item => <li key={item}>{item}</li>)}</ul>
          <details><summary>Dữ liệu và nguồn đã đọc</summary>
            <pre style={{whiteSpace: "pre-wrap", overflowWrap: "anywhere"}}>{JSON.stringify(preview.value.tools, null, 2)}</pre>
          </details>
        </div>}
      </>}
    </section>
    {error ? <div role="alert">{error} <button onClick={() => setReload(value => value + 1)}>Thử lại</button></div>
      : data.workspace !== workspace ? <p role="status">Đang tải danh mục…</p>
      : <div className="st-platform"><section><div className="st-cap-grid">
        {data.skills.map(skill => <article key={skill.id}>
          <Bot size={16}/><div><strong>{names[skill.id] || skill.id}</strong>
            <p>Phiên bản {skill.version} · Chỉ đọc dữ liệu · Chưa tự thực thi</p>
            <p>Agent: {skill.allowed_agents.join(", ")}</p>
            <details><summary>Contract và quyền công cụ</summary>
              <p>{skill.allowed_tools.join(", ")}</p>
              <p>Giới hạn: {skill.timeout_seconds}s · trần {skill.token_budget} token. Ba skill hiện tại không gọi LLM: 0 token sinh.</p>
              <code style={{overflowWrap: "anywhere"}}>{skill.hash}</code>
            </details>
          </div><span>REGISTERED</span>
        </article>)}
      </div></section></div>}
    <section aria-label="Replay skill đã lưu">
      <h2>Xem lại kết quả skill</h2>
      <p>Chỉ đọc artifact của run đã hoàn tất, giữ phiên bản và dữ liệu tại thời điểm chạy. Không gọi lại tool, không chạy code cũ; không xác minh dữ liệu hiện tại.</p>
      <label>Run ID để xem lại <input style={{maxWidth: "100%", boxSizing: "border-box"}} value={replayId} onChange={event => {setReplayId(event.target.value); clearReplay();}} placeholder="UUID của run trong Chief"/></label>
      <button onClick={readReplay} disabled={!workspace || replay.busy}>Xem kết quả đã lưu</button>
      {replay.workspace === workspace && <>
        {replay.busy && <p role="status">Đang đọc artifact…</p>}
        {replay.error && <p role="alert">{replay.error}</p>}
        {replay.value && <div>
          <p>Skill {String(replay.value.skill_snapshot.id)} · Phiên bản đã lưu {String(replay.value.skill_snapshot.version)} · {replay.value.result.status}</p>
          <p>{replay.value.result.summary}</p>
          <p>Không thực thi lại · Chưa xác minh kết quả kinh doanh</p>
          <details><summary>Artifact, contract và nguồn đã lưu</summary>
            <pre style={{whiteSpace: "pre-wrap", overflowWrap: "anywhere"}}>{JSON.stringify(replay.value, null, 2)}</pre>
          </details>
        </div>}
      </>}
    </section>
  </>;
}
