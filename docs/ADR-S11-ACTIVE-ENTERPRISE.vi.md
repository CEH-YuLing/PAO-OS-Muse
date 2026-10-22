# ADR-S1.1 — Doanh nghiệp đang hoạt động

Ngày11/10/2026. Target `F:\PAO-ACOS`; thứ tự do master roadmap sở hữu.

## Hợp đồng

- Reuse Workspace/Member; không tenant engine, bảng, migration hoặc tenant claim
  mới trong JWT. GET `/v1/workspaces/{workspace_id}/context` kiểm membership hiện
  hành, trả id/name/role và no-store; anonymous401, outsider/unknown404.
- `/v1/me` trả membership theo name/id ổn định. Browser lưu preference trong
  sessionStorage theo user ID; chỉ resolve ID có trong response membership.
  Nhiều SME chưa có preference phải chọn; một SME có thể initialize trực tiếp.
  Preference bị sửa/mất quyền không silent fallback sang doanh nghiệp khác.
- Runtime sở hữu `workspaceId` và `activeWorkspace`; tất cả consumers trước đây
  lấy membership đầu tiên chuyển sang active membership, role cũng theo SME đó.
- Selector ở Orb, topbar và sidebar mobile. Khi không có selection, shell hiển
  thị yêu cầu chọn; zero-membership có thông báo, không spinner vô hạn.
- Chuyển SME kiểm lại context backend trước commit preference. Tenant generation
  thay đổi trước lookup; reset session/messages/run/projection/pending prompt và
  remount component subtree để bỏ local form drafts/IDs/credential inputs.
- API JSON dùng generation guard trước/sau đọc body; closure của scope cũ bị
  từ chối trước fetch. SSE dùng epoch hiện có, cleanup abort khi selection reset.
  Session detail phải khớp active SME. Không cancel/repin run phía server khi switch.

## Giới hạn và checkpoint tiếp theo

- Không cấp thêm quyền Brain/private memory hoặc đổi historical pins. Backend
  authorization từng API vẫn là authority, preference không là authorization.
- S1.2 còn test SSE đang chạy, raw response/body/blob sau switch, download/export,
  per-tab/cache/local storage và refresh membership; S1.3 còn worker/outbox/files
  corpus và mất quyền giữa enqueue/execute. S1.1 không chứng minh toàn SaaS đã cách ly.
- Status Telegram/Voice/Temporal cấp process vẫn là capability chung hiện hành;
  S2–S4 sẽ làm connection resolver riêng SME. Không gọi saved config là live.
- Không thay feature flags/.env/DB schema, bật connector hoặc gọi model để test.
- Backend source đổi exact execution binding: restart owned API/ARQ khi idle;
  không sửa snapshot/hash lịch sử để ép job cũ chạy trên source mới. M2 archive
  vẫn đọc/replay được, compatibility cho thực thi mới là gate riêng.

## Rollout và rollback

Trước rollout: idle gate + retained DB/source checkpoint và clone restore. Chỉ
restart API/ARQ khớp executable/command/start-time; Web dev hot reload source.
Không downgrade0048 hoặc khôi phục primary chỉ vì đây là thay đổi UI/API.
Rollback dùng source checkpoint phù hợp, owned idle restart và contract/health
checks; không reset Git dirty tree. Source checkpoint trước S1.1 giữ tại S03
acceptance; checkpoint chứa code S1.1 dùng cho recovery trạng thái mới.
