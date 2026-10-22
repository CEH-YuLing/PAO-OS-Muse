# S2.2B2a — Native read-job admission và dispatch

B2 được kiểm chứng theo hai phạm vi: B2a native MCP/Meta/Google read jobs;
B2b metadata/probes và legacy engine còn lại. Tài liệu không sở hữu thứ tự;
master/register cập nhật kết quả sau các gate. B2a đạt local theo
[nghiệm thu](S22B2A-LOCAL-ACCEPTANCE-2026-10-13.vi.md). Không coi B2a là toàn S2.2B2/S2.

## Cơ chế

- Reuse ToolCall/MetaSyncJob/GoogleAdsSyncJob, không thêm queue/worker/engine.
  TenantReadPolicy độc lập model policy, version/CAS owner/admin và host bounds.
  Defaults500 admitted jobs/dayUTC,20 queued,2 running; ceilings10000/100/8.
  Không nâng số worker/max_jobs, không mở provider/writes/OAuth thật.
- Workspace KEY SHARE → scoped read-resource advisory → subordinate source/job
  locks. API/scheduler recheck authority trước admission; worker check slot trước
  decrypt. Quota không thay grant/actor/brand/account/Skill/Brain/source-version.
- DB guard chống race ở INSERT và queued→running, server admission timestamp
  bất biến; chống thay id/scope/created/request hoặc delete/refund/requeue terminal
  admitted job. Legacy rows vẫn NULL stamp, không sửa lịch sử sau migration.
  JSON null khác SQL NULL: tools nội bộ không bị tính như MCP chỉ vì ORM lưu JSONnull.
- Daily là job admission, không số RPC/HTTP thực. Failed/cancelled/unknown vẫn
  giữ count. Quota provider và billing unknown, không hiển thị như0. Không cam
  kết provider dừng compute/hoàn quota khi client hủy. Terminal native states
  là PAO admission slots, không lời hứa physical concurrency ở provider.
- Worker hết slot giữ queued/wait không decrypt/provider, lượt sau fresh checks.
  Cancel/expiry/source rotation không tự revive grant hoặc repin job.
- Dispatcher chỉ offer một oldest queued item/SME/family, không prefill Redis
  sau SME đang chạy. Due scheduler cũng chia trang theo SME và skip quota-blocked
  SME; fresh admission lại trong transaction. Không là global host QoS guarantee;
  Redis backlog cũ/non-read engines/production host scheduling vẫn có gate riêng.
- Native timeouts giữ MCP32s, Ads300s; stale MCP90s thành unknown như cũ. Lost Ads
  sau360s thành failed/worker_lost_unknown, không blind resend (thay old retry2).
  Late worker publication vẫn bị generation/status/source-authority guards chặn.
- GET/PUT `/v1/workspaces/{id}/resources/reads`: no-store, strict DTO/CAS/redaction,
  phạm vi/pending coverage rõ. Không quota UI trước B3/S2.3.

## Tài liệu provider kiểm tra13/10

- [MCP tools2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools):
  rate limits/timeouts/access control, annotations không tự đáng tin. Giữ native
  transport/version/scope; không mở anonymous tenant grants.
- [Google Ads quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas):
  quota operations/access-level không đồng nghĩa số job PAO. Không hardcode quota
  provider hoặc đổi v25 transport/scopes từ cấu hình native.
- Meta official rate-limiting pages thử hai URL không đọc được (Internal Error).
  Không suy luận số quota, không đổi auth/scopes/v26, không thực hiện network
  acceptance. Native dossier/evidence cũ vẫn là lịch sử, không claim refresh API
  policy thành công. Provider live acceptance/S4 vẫn mở.

B2b metadata/model legacy, B3 quota Settings, S2.3 và full S2 final chưa đạt.
