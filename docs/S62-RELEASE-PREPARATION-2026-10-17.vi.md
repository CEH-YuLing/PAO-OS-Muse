# S6.2 — Bảo vệ phiên bản trước vòng đời tài khoản/dữ liệu

Ngày17/10/2026. Target ứng dụng `F:\PAO-ACOS`.
Trạng thái: **checkpoint backup/restore local đã đạt; review source trước publish
còn mở; chưa triển khai lời mời/phiên/export/xóa, toàn S6.2 chưa hoàn tất.**

## Phạm vi và thao tác

- Đọc AGENTS/master, mã backup/restore và identity/team để chuẩn bị checkpoint.
- Git HEAD e1eb473 ngày05/10;93tracked thay đổi,819untracked tại lúc kiểm tra.
  `.env`, `.runtime`, `.venv`, node_modules đều được ignore; không có private
  env/runtime/dependency paths trong tracked list của lượt rà. Không commit/push.
- Docker29.4.3 hoạt động; lần đầu trong sandbox bị permission denied, không phải
  daemon hỏng. Hai container pao-acos-local postgres/redis đang Exited255 được
  khởi động lại bằng compose hiện có; không xóa/recreate volume, không reboot,
  không thao tác container search của dự án khác.
- Chạy script checkpoint hiện có, không đổi backup/restore hoặc migration.
  Script tạo clone restore riêng rồi chỉ xóa đúng clone nó tạo; primary giữ0070.
  Không khởi động API/Web/worker/Telegram/Ollama, không provider calls.

## Bằng chứng checkpoint

- Manifest: `.runtime/checkpoints/p0-20261017T024623-0631c516/manifest.json`.
- Source ZIP cùng thư mục: **1219files**, archive/manifest hashes verified.
- DB dump: `.runtime/m2-20261017T024617-414625fb.dump`,744287bytes.
- **149tables,3skill artifacts,revision0070**; restore clone so revision,
  row counts và artifact hashes/responses khớp. Không gọi đây là full row-content
  hash equality của toàn DB vì script không kiểm điều đó.
- Source không chứa `.env`/runtime/dependencies/Git history. DB dump vẫn là dữ
  liệu riêng tư có thể chứa dữ liệu người dùng/ciphertext; giữ trong runtime,
  không đưa Git/CI/chia sẻ. Khóa recovery cần quy trình riêng tư riêng; không
  đưa khóa thật vào source ZIP/report và chưa chứng minh disaster recovery offsite.

## Rà source không lộ giá trị

Artifacts tại `F:\Apex\audit-reports\s62-release-preparation-2026-10-17`:
release_review.py, test_release_review.py, source-review.json,
verify_literal_passwords.py và literal-password-review.json.

- Quét1212file nguồn tracked + untracked không bị ignore, giới hạn suffix/path;
  không đọc env thật/runtime/dependencies hoặc Git history. Đây không phải
  inventory mọi file archive hoặc secret scanner chuyên dụng.
-35review signals:7URL có credential-like segment,27secret-like assignments,
  1private-key marker. Không output matched value; giữ path/line/category.
- Vị trí nằm trong test/browser fixture, template env/compose và script kiểm
  local. Có template interpolation và fixture markers; **không whitelist tự động
  toàn thư mục test, không gọi mọi finding là false positive hoặc secret sạch**.
- Không có provider-token hoặc Telegram-token pattern hit theo heuristic này.
- Read-only hash verification:1active local account;3Python dictionary password
  literals ở source flagged đều không khớp mật khẩu active. Không đăng nhập/
  tạo token/rotate password/user mutation. Không suy từ đó mọi dạng secret đều an toàn.
-4helper tests đạt. Lượt đầu có1fail do Windows rooted path, đã sửa chặn anchor,
  rerun4/4đạt; không phải test của application hoặc full backend regression mới.

## Kế hoạch commit khi được phép

Không git add-all. Rà dependency/diff và gom logic: nền tảng boundaries/
operations→Brain/knowledge→engine/Studio/connectors→durable Goal/channels→
tenant/connections/S3/S4→S5/business planning→S6scripts/docs. Các nhóm chỉ là
đề xuất review; trạng thái working tree không chứng minh từng commit build độc lập.

Trước public/remote push phải triage35findings theo exact file/hash/line, audit
history bằng công cụ phù hợp, xác định remote/private access và review source
snapshot đầy đủ. Không thay `.gitignore` hoặc xóa fixture để giấu findings.

## Các gate còn mở và bước tiếp theo

| Gate | Trạng thái |
|---|---|
| Snapshot source + database restore local trước code change | đạt theo phạm vi nêu trên |
| Rà secret toàn history / commit / remote publish | chưa thực hiện; không được coi clean |
| Key recovery riêng / offsite / production disaster drill | chưa nghiệm thu |
| Lời mời/member A, session B, export/deletion/retention C | implementation_pending |
| S6.1real data/action, hosted CI/production, S6.3pilot | giữ pending theo register |

**Checkpoint triển khai kế tiếp: S6.2A — lời mời và thành viên theo SME.**
Backup local đủ làm điểm phục hồi trước implementation test; findings review
không cấp quyền publish source. Trước migration/rollout phải backup lại nếu
source/data inputs đã đổi, kiểm clone và ghi bằng chứng đúng candidate.
Không full baseline rerun, thay code/UI/schema/env hoặc bật external flags ở
lượt bảo vệ này. Không tuyên bố đã hoàn thành Giai đoạn1/S6.2.
