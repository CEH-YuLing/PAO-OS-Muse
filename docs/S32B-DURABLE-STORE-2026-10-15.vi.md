# S3.2B — Lưu cấu hình và cách ly tin chưa được phép xử lý

15/10/2026, `F:\PAO-ACOS`. **S3.2B vẫn in_progress**. Phần lưu cấu hình,
thế hệ khóa, nhật ký và con trỏ/quarantine đã source_verified; chưa đóng B,
chưa rollout primary hoặc nối adapter/worker. [Phân kỳ A/B/C](ADR-S32-TELEGRAM-SCOPED-RUNTIME.vi.md).

## Phần mới đã triển khai

- Migration candidate `0061_telegram_durable_profiles.py`: ba bảng mới
  `telegram_runtime_profiles`, `telegram_runtime_audits`, `telegram_runtime_receipts`.
  Không backfill hoặc sửa namespace/history cũ. Không thêm router/contract.
- `telegram_store.py` là dịch vụ nội bộ, không có route hoặc worker import.
  Lưu/đổi/thu hồi cần consent, pin connection/owner/SME/version hiện hành và
  PG bot lease thật từ kernel A; quyền owner/admin không cấp quyền cho nhân viên.
- Token mã hóa với purpose/pin/generation được xác thực; audit dùng MAC có khóa,
  không có token rõ hoặc ciphertext trong view/audit. Lưu xong vẫn `disabled`,
  chưa xác minh token tại Telegram, chưa bật nhận/gửi và không cấp công cụ.
- Generation tăng, CAS/request key chống ghi đè và xử lý trùng. Retry cùng khóa
  nhưng khác nội dung/bot/hành động bị chặn; yêu cầu đã bị thay thế không tái áp
  dụng. Thu hồi xóa ciphertext, không thể khôi phục profile hoặc nhả bot identity.
- Loader metadata pin generation, dùng lại `getMe/getWebhookInfo` của kernel A.
  Đổi generation làm loader cũ mất hiệu lực; không fallback token host.
- Quarantine nội bộ nhận batch giới hạn, chỉ lưu hash/ID/lý do của tin chưa liên
  kết, không hỗ trợ hoặc sai định dạng; không lưu body, tạo peer/run hay gửi tin.
  Receipt + cursor cùng transaction; lỗi/cancel rollback cả hai. Cursor không
  lùi, không reset khi đổi khóa; dedup xuyên generation theo connection/update ID.
- Trigger DB giữ audit/receipt append-only; profile có audit nguyên tử và cursor
  chỉ được tiến khi có receipt tương ứng. Downgrade có dữ liệu mới bị từ chối.
- Registry hiện tái sử dụng unique bot ID và identity bất biến ở
  `telegram_connections`. Legacy chưa xác minh identity vẫn bị chặn; chưa đóng
  gate registry/resolver legacy chỉ vì đã có unique constraint cho native.

## Bằng chứng kiểm thử trong lượt này

| Gate | Kết quả |
|---|---|
| Checkpoint trước thay đổi | `.runtime/checkpoints/p0-20261015T071811-82399845/manifest.json`;1082source/0060/129tables/3archives, backup/restore đạt |
| Candidate migration clone |0060→0061→0060→0061; alembic check đạt hai lần, old rows exact, rollback schema equivalent, populated downgrade refused, primary unchanged |
| Migration evidence | `.runtime/s32b-migration.json`; backup cuối `s32b-pre-3c875a7108914101ac3b7191117a63d9.dump`; chỉ xóa clone do script tạo, giữ backup |
| Focused cuối |199passed/0failed/0error/0skip,77.88s;56store+143kernel/Telegram/namespace/mapping/helpers/Channels/factory, `.runtime/s32b-focused.xml` |
| Dedicated test DB | `pao_test`0061; alembic check không còn upgrade operations; không chạy pytest trên primary |
| Bản chạy | API/ready/Web200,workerhealthy,Telegram bridge disabled; live OpenAPI338 khớp file contract |
| Primary |0060/129physical, không có bảng `telegram_runtime_*`; không apply0061 hoặc restart API/worker |
| Cấu hình | `.env` SHA256 `5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`, không sửa |

Không chạy full backend/build/browser ở primitive chưa nối runtime và không
đổi UI. Full1737 của S31B là lịch sử, không phải kết quả full backend mới.
Không gọi Telegram thật; HTTP fixture dùng token synthetic và cấm default live
transport. Trang chính thức đã đối chiếu trước code:
[getUpdates](https://core.telegram.org/bots/api#getupdates),
[getMe](https://core.telegram.org/bots/api#getme); offset không được ACK trước
receipt durable. Trong lượt này chưa gọi getUpdates hoặc ACK provider.

## Các lỗi kiểm thử đã xử lý, không che kết quả trung gian

- Lần đầu41pass/1fail: fixture forged bot dùng token prefix bot cũ nên bị chặn
  ở kiểm tra token trước scope. Sửa fixture để token khớp forged ID và thực sự
  kiểm tra nhánh từ chối scope; không nới kiểm tra token.
- Lần tích hợp tiếp191pass/3fail: test downgrade lịch sử hard-code revision0060.
  Giữ nguyên kiểm tra append-only/refusal và so sánh revision trước/sau; không
  cho phép downgrade hoặc bỏ test. Bộ199 cuối đều đạt.

## Còn lại trong cùng S3.2B — không triển khai lại phần trên

Snapshot store này giữ bằng chứng cũ. Toàn B sau đó đã
[source_verified368affected/25Node](S32B-SCOPED-EXECUTION-2026-10-15.vi.md),
candidate0063/primary0060; next-step hiện hành là S3.2C theo master.

Cập nhật sau snapshot store: mục1 đã source_verified theo
[identity evidence](S32B-VERIFIED-IDENTITY-2026-10-15.vi.md),238focused/39identity,
candidate0062 chỉ clone/pao_test. Mục2–3 bên dưới vẫn mở; không triển khai lại
store hoặc registry. Primary vẫn0060, không coi metadata resolver là admission.

1. Registry/resolver cho identity legacy được xác minh rõ, không repin history,
   không suy từ host token; native staged/unverified không là activation.
2. Scoped ingress/admission dùng Channels/admit_run/S2 accounting; actor, session,
   Brain và grant đúng phạm vi. Receipt/quarantine hiện chỉ ghi tin không được
   xử lý, chưa phải nhận và chạy công việc hợp lệ.
3. Scoped outbox pins, generation/actor/destination recheck và trạng thái gửi
   unknown/retryable/no-resend. Chưa có adapter gửi hoặc cancellation mới.

Sau B mới C: worker epoch, polling/webhook/report integration, release đủ test,
checkpoint/migration primary/khớp installed binding/exact restore. Restore checker
hiện hỗ trợ primary đến0060; cập nhật gate0061 khi tích hợp rollout C, không coi
candidate0061 đã được nghiệm thu production.

S3.3 mới có liên kết tài khoản Telegram/đội ngũ, phân quyền/thu hồi trên giao diện,
token/setup và hướng dẫn/Việt hóa Cài đặt theo
[yêu cầu đã chốt](PRODUCT-SETTINGS-AND-TELEGRAM-ACCESS.vi.md). Không gán quyền từ
/start, username hoặc quản trị nhóm. Không nhập token thật trong lượt này.
