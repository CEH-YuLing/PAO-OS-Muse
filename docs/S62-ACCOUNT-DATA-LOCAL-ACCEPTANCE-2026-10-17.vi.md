# S6.2 — Giai đoạn 1: nền tảng SaaS

Target duy nhất `F:\PAO-ACOS`. **Giai đoạn1 — S6.2 tài khoản/dữ liệu:
local_accepted trọn cả bốn bước**,17/10/2026,12:49:36Asia/Saigon.
Toàn S6 vẫn in_progress; production chưa đạt. Receipt thực tế:
`.runtime/s62-completion.json`, preflight `.runtime/s6-readiness.json`.

## Kết quả nghiệm thu hiện hành

| Cổng | Kết quả |
|---|---|
| Bảo vệ phiên bản | Checkpoint0070,1238source/149tables/3archives; phục hồi clone đúng row hashes và schema definitions |
| Lời mời/thành viên | API/UI invite-only, role/remove theo SME; không ảnh hưởng quyền ở SME khác |
| Phiên đăng nhập | Thu hồi current/từng phiên/tất cả phiên phía server, kiểm lại phiên khi stream/metadata |
| Dữ liệu | Export theo danh mục/ACL, preview→request→confirm; không có executor xóa thật, retention tắt |
| Full backend Windows mới | **2258/2258 đạt,0fail/0error/0skip**,2291.43s;62ARQ deprecation warnings còn tồn tại |
| Frontend |114Node/TypeScript và production build23trang đạt; browser thật desktop/mobile390px/hai SME đạt |
| Runtime primary |0071/399operations/152ORM/153physical; API health/ready/Web200, worker lease khỏe, replay3/3 không gọi tool |
| Dữ liệu/cấu hình | Cột cũ/hashes nghiệp vụ/3archives và `.env` trước/sau giữ nguyên; không tạo user/fixture trong primary |
| Preflight S6 |local_checks_passed=true; hai lifecycle gates local_accepted; S6/production=false |

Backend binding hiện hành:
`8e9a71b996dee609d36868b8a254073c9ea16d4d78f56cf790d86690cf1b591b`.

Bằng chứng private, tương đối từ root dự án:

- Full: `.runtime/s62-full-b51e01d3789e408d8ee5ae1e554af04b/junit.xml`
  và `result.json`; `.runtime/s62-backend.json` là snapshot mới nhất.
- Browser: `.runtime/s62-browser-runs/pao_s62_browser_2b654ce9dfc04140bd60159bf81ce482/receipt.json`,
  `cleanup.json`, screenshots. DB thử riêng đã dọn; không timeout cleanup.
- Clone schema: `.runtime/s62-migration-beb795238d1f4085b633489ed684d21a/result.json`.
- Checkpoint trước rollout: `.runtime/checkpoints/p0-20261017T050556-1dcc85d8/manifest.json`;
  restore exact được kiểm lại ngay trước migration.
- Checkpoint sau nghiệm thu: `.runtime/checkpoints/p0-20261017T055129-35142d1a/manifest.json`,
 1238source/153tables/3archives/0071, verified. Phục hồi clone riêng
  `pao_s03_restore_f94a01dd78e74e60ad2ce036302a7b79` đạt exact row hashes và
  schema definitions; primary không đổi. Chỉ clone do lượt kiểm tra tạo đã dọn,
  bản dump/source vẫn giữ private. Snapshot không chứa các khóa giải mã.
- Primary rollout: `.runtime/s62-schema-rollout.json`; live: `.runtime/s62-live.json`.
- 47tests tập trung, gồm Temporal/ARQ thật và signal trễ, đạt141.98s; JUnit
  `F:\Apex\audit-reports\s62-release-preparation-2026-10-17\candidate-d8aaa26c383748abb5d93c721e9c265e.xml`.
- 13gate tests/31subtests offline đạt; precheck OpenAPI/152ORM đạt. Hosted CI
  chưa chạy. Không gọi full Windows mới này là lượt Linux hoặc production.

Rà source hiện hành1238file đối chiếu5giá trị cấu hình riêng:0match. Giữ
35signals review ban đầu và giới hạn kiểm tra; **chưa audit toàn Git history**,
không commit/push hoặc tuyên bố toàn source sạch mọi loại secret.

## Phạm vi trọn giai đoạn

1. Bảo vệ phiên bản: snapshot source không chứa cấu hình riêng/dependencies,
   dump DB và restore clone; không commit/push tự động. Khóa giải mã được giữ
   riêng, không nằm trong source ZIP. Source ZIP không thay backup khóa/offsite.
2. Tài khoản/thành viên: owner tạo mã mời một lần, có hạn và thu hồi; tài khoản
   mới chỉ được tạo bằng lời mời hợp lệ. Người có tài khoản phải đăng nhập đúng
   email, không dùng mã mời để đặt lại mật khẩu. Quản lý vai trò không-owner,
   gỡ quyền SME A mà không xóa tài khoản hoặc quyền ở SME B.
3. Phiên: lưu hash token, không lưu token rõ; thu hồi hiện tại/từng phiên/tất
   cả phiên phía server. JWT cũ version0 còn hiệu lực được hỗ trợ có kiểm soát;
   logout-all tăng phiên bản tài khoản. SSE kiểm lại phiên. Logout không tự hủy
   mọi job đã giao; gỡ membership mới thu hồi quyền thực thi theo SME.
4. Dữ liệu: xuất theo danh mục hỗ trợ và ACL, mã hóa payload, tải trong15phút;
   preview → yêu cầu xóa → xác nhận riêng. Chưa có executor xóa thật. Retention
   nội dung kênh mặc định tắt, cấu hình số ngày không tự bật purge.

## Thiết kế và giới hạn chủ đích

- Modular monolith hiện có được giữ nguyên, không thêm authority/runner mới.
- Schema0071 thêm4bảng,2cột;152ORM/153physical,47routers/399operations.
- Lifecycle audit không được UPDATE/DELETE; downgrade có dữ liệu bị từ chối.
  Khôi phục source và khôi phục schema/dữ liệu là hai thủ tục khác nhau.
- Invite không gửi email/Telegram tự động, không nằm trong URL hoặc lịch sử
  plaintext; hash một chiều, giới hạn tốc độ, một lần và kiểm owner lúc nhận.
- Vai trò/Brain/connection/channel grants được kiểm lại; owner SME không tự
  có quyền Brain riêng của nhân viên. Không hỗ trợ chuyển owner trong lát cắt này.
- Export là **gói dữ liệu nghiệp vụ được hỗ trợ**, không phải bản sao đầy đủ
  toàn database: brands/projects/goals/tasks, hồ sơ/kế hoạch/job/ngân sách/
  hành động/báo cáo kinh doanh và Brain được chọn mà người yêu cầu có ACL.
  Không export thông tin kết nối, secret/ciphertext, private chat, raw execution,
  audit hoặc backup. Tối đa2000bản ghi/2MiB, chặn trước khi nạp file quá lớn.
- Lọc các khóa/chuỗi credential thường gặp trong trường JSON; không hứa phát
  hiện mọi bí mật người dùng tự viết trong tài liệu. Kiểm tra file trước chia sẻ.
- Export hết hạn không còn tải được nhưng chưa tự purge record/ciphertext.
  Preview/yêu cầu/xác nhận chỉ ghi metadata/audit, không xóa dữ liệu nghiệp vụ.
- Chưa có reset mật khẩu, public signup, chuyển chủ, billing, xóa tự động,
  DSR pháp lý toàn diện hoặc production security review.

## Bằng chứng và lịch sử lỗi

- Snapshot trước triển khai0070 đã verify source/149tables/3archives và restore.
  Thông tin checkpoint cuối cùng sẽ được chốt sau bộ kiểm thử cuối.
- Clone migration roundtrip0070→0071→0070→0071 đạt; giữ nguyên dữ liệu cột cũ,
  populated restore đạt, audit trigger sau restore còn hiệu lực, downgrade
  có dữ liệu bị chặn. Primary/env không đổi trong kiểm thử clone.
- Frontend: TypeScript và114Node đạt; production build23trang đạt.
  Browser thực qua API/DB riêng, Edge desktop/mobile390px; không mock `/v1`.
- Gate offline13tests/31subtests đạt; không suy hosted CI đã chạy từ precheck.
- Các lượt full regression lỗi được giữ nguyên:325pass/1fail do fixture đọc
  private business flag;1033pass/1fail do mã lỗi authority sau khi thêm session
  recheck. Sửa fixture, giữ auth deny và mã lỗi domain; bổ sung test logout
  giữa metadata I/O. Không bỏ test hoặc mở quyền để đổi trạng thái thành xanh.
- Một lượt browser chạy đồng thời với source sửa đã bị từ chối receipt vì
  binding đổi; giữ log lỗi, chạy lại sau đóng băng source.
- Lượt full2256ca:2255đạt/1lỗi/0skip,2490.94s,61ARQ warnings. Lỗi ở
  `test_real_temporal_cancel_drains_or_holds_unknown`: native abort đã xác minh
  nhưng activity báo lỗi trước khi signal hủy tới workflow, nên thành
  `manual_review`. Không xóa log hoặc nới assertion. Sửa activity strict ACK
  để tiếp tục heartbeat chờ signal trong deadline25giây hiện có; không đổi
  deterministic workflow code, không thêm runner, không bỏ xác minh ACK.
  Bổ sung test cố tình giao signal trễ và test signal mất vẫn hết hạn an toàn.
  Bằng chứng backend/browser cũ không dùng để nghiệm thu backend đã sửa.

## Nghiệm thu và việc tiếp theo

Các cổng full backend/browser/checkpoint/restore/guarded schema rollout/live
health/worker/replay và dữ liệu/cấu hình không đổi đều đã đạt. Master/register
được cập nhật theo receipt hiện hành, không dùng kết quả lỗi để đóng gate.

### Vận hành và phục hồi

- Khởi động bằng `scripts/start_acos_local.ps1` sau release; pin0071, không
  dùng launcher0070 cũ để cố đưa schema lùi lại. API8100/Web3200 chỉ loopback.
- Giữ checkpoint0070 trước migration và checkpoint0071 sau nghiệm thu; kiểm
  hash/restore trên clone trước khi dùng làm phương án phục hồi. Giữ khóa JWT/
  Fernet riêng và không gửi lên chat, source ZIP hoặc Git.
- Nếu rollout/health thất bại, giữ log và dừng mở tính năng; không tự xóa4bảng
  mới để vượt guard downgrade, không `TRUNCATE` audit, không restore đè primary.
  Restore primary hoặc bỏ lịch sử cần xem trước phạm vi và xác nhận riêng.
- Khi cần đổi vai trò/gỡ nhân viên, kiểm cả Brain/connection/channel/job ở SME
  liên quan; không khóa toàn tài khoản để thay thao tác gỡ một SME.
- Hết hạn tải không đồng nghĩa record đã xóa. Chưa có SLA xử lý xóa pháp lý;
  quản trị phải xem xét dữ liệu ngoài phạm vi, audit/backups và tác vụ đang chạy.

Toàn S6 và production vẫn chưa đạt: dữ liệu/quảng cáo thật đã hoãn theo quyết
định người dùng; hosted CI, môi trường riêng/HTTPS/reboot/cold restore và owner
pilot còn gate riêng. Sau giai đoạn này là lát cắt **M6 UX phục vụ S6**, không
làm lại P6 hoặc các milestone đã nghiệm thu local.

Xem [hướng dẫn sử dụng](S62-ACCOUNT-DATA-USER-GUIDE.vi.md). Các nguyên tắc token
một lần/hết hạn, không tự đổi mật khẩu và quản lý session tham khảo
[OWASP token recovery](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
và [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
Đây không phải chứng nhận OWASP hoặc tuân thủ pháp lý.
