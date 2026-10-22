# S6 — Hướng dẫn chuẩn bị local và mẫu nghiệm thu

S6 đưa MVP local sang dùng trong doanh nghiệp thật rồi mới production. Không
phải bật tất cả cờ tính năng. Tài liệu không cấp quyền đọc tài khoản ngoài,
gửi tin, chi tiền, đăng bài hoặc deploy công khai.

## 1. Kiểm tra local hiện tại

Tại `F:\PAO-ACOS`, dùng môi trường Python của dự án:

```powershell
.\.venv\Scripts\python.exe scripts/test_s6_readiness.py
.\.venv\Scripts\python.exe scripts/run_p0_checks.py --preflight-only
.\.venv\Scripts\python.exe scripts/check_s6_readiness.py
```

Hai lệnh đầu không chạy backend regression hoặc thay DB. Lệnh cuối đọc HTTP,
worker lease, source contract, replay và business row hashes, ghi diagnostic
`.runtime/s6-readiness.json`. Không gọi Meta/Google/Telegram/LLM hoặc tạo job.
`local_checks_passed=true` chỉ nói bản local vẫn khỏe. Chạy lại để lấy thời
điểm mới; JSON cũ không phải giấy phê duyệt hay bằng chứng health hiện tại.

Giữ database0070, pin launcher0070 và các cờ provider tắt. Không dùng
`test_backend.py --roundtrip` để sửa database chính. Backup private gồm dữ
liệu doanh nghiệp; không đưa `.runtime`, dumps, `.env` hay keys lên GitHub.

## 2. Hồ sơ pilot — điền sau khi có dữ liệu thật

Hai chính sách đã chốt: chỉ owner mời, chưa public signup; chưa tự xóa,
export/yêu cầu xóa có preview và xác nhận. Xem ADR-S6-ACCOUNT-AND-DATA-LIFECYCLE.vi.md.
Đây không phải claim các luồng lifecycle đã triển khai.

| Trường cần xác nhận | Vì sao cần |
|---|---|
| SME ID, brand ID, owner và người tham gia | Một người thuộc hai SME không được trộn dữ liệu/quyền |
| Provider, account, campaign filter nếu theo brand | Số liệu cả account không mặc nhiên là số liệu một brand |
| Từ ngày/đến ngày, timezone account, currency | Chốt kỳ đã kết thúc, không cộng tiền khác loại hoặc nhầm ngày UTC |
| Metric definitions và attribution | Purchases/conversions/doanh thu là các khái niệm khác nhau |
| Connection/ref/grant revision, scopes đọc | Lưu cấu hình không chứng minh token hợp lệ hoặc có quyền đọc account |
| Nguồn PAO, export nguyên gốc, hash, exported_at | Hash chứng minh file không đổi, không tự chứng minh file chính thức |
| Coverage, missing fields, freshness, quota | NULL không thành0; quota chưa được provider xác nhận phải để chưa rõ |
| Quyền đọc được owner cấp, tiêu chí nghiệm thu | Chỉ thao tác trong account/kỳ/đích được cấp riêng |

Ưu tiên một kỳ7ngày đã hoàn tất trước khi mở rộng30ngày. Chuẩn hóa bằng adapter
hiện có, không tự đoán CSV separator/decimal/locale hay cộng hàng total với hàng
campaign. Giữ export gốc trong kho private theo SME; không commit report khách.
Đối chiếu scope/coverage trước khi so số. Endpoint reconciliation hiện có chỉ
so totals người dùng cung cấp: `values_match` chưa xác thực nguồn hoặc đóng S6.

Khi chênh lệch: dừng nghiệm thu dữ liệu, nêu đúng metric/nguồn/kỳ và missing
data, không sửa tay DB hoặc thêm số giả để khớp. Báo cáo Chief không được suy
ra KPI đạt hay lợi nhuận từ fixture hoặc purchases do nền tảng tự báo cáo.

## 3. Một hành động thật — chưa được phép trong preparation

Chỉ sau read-only đạt và owner cấp riêng: chốt đúng action/đích/account/brand,
payload hash, thời hạn, trần tiền/currency/headroom, adapter hỗ trợ và cách dừng.
Review kế hoạch, content và action là ba việc riêng. Recheck quyền ngay trước
thực hiện; giữ receipt/idempotency. Unknown phải giữ khoản giữ và đối soát,
không chạy lại bằng request ID mới. Mock ledger không phải provider balance.
Không suy quyền đăng bài/tạo campaign từ adapter điều chỉnh Ads hiện có.

## 4. Checklist môi trường Linux/production riêng

Chạy thử Linux local bằng `scripts/run_s6_linux.py` trên máy đã cấu hình Docker;
script dùng source-only ZIP và dịch vụ test riêng, không publish cổng hay mang
database chính vào runner. Không cần và không được mang cache `.exe` Windows
sang Linux. `scripts/bootstrap_temporal_test.py` là bước cấp binary Temporal
test tường minh; các fixture sau đó chỉ dùng cache native đã có. Đọc log tại
S6-LINUX-LOCAL-2026-10-16.vi.md; runner build/chạy chưa có kết quả cuối không
phải đã đạt. GitHub CI vẫn là bằng chứng riêng, không tự push để tạo run.

- CI: source commit/binding, Python/Node/dependency lock, service images và
  migration0070 khớp; full tests gồm restore/kill-restart/no-resend, Node/build.
  Lưu run URL/log/artifact, không gọi cài workflow là đã chạy. Không skip test
  Windows-path để gọi Linux xanh; dùng profile restore cô lập đã chuẩn bị tại
  `scripts/ci_restore_profile.py`. Profile chỉ chạy populated trên Linux CI,
  không cho apply-manifest hoặc địa chỉ/database primary. Unit trên Windows
  với platform giả lập không phải một full Linux run đã đạt.
- HTTPS/reverse proxy: host riêng, DNS/TLS, forwarded headers/cookie/CORS/origin
  đã kiểm; DB/Redis không public. Không dùng Next dev làm production server.
- Danh tính: signup/invite/deprovision, session/revocation và vai trò theo SME;
  thu hồi khỏi SME A không cấp hoặc phá quyền SME B. Chưa có test là chưa đạt.
- Tài nguyên: tải đồng thời hai SME, giới hạn token/job/queue và fairness; đo
  latency/queue lag/RAM/cost trên cùng workload, không tự đặt SLA chưa có số.
- Vận hành: process supervisor, lỗi/thời gian/queue alerts, log redaction và
  owner nhận cảnh báo; không gọi lease khỏe là provider inference khỏe.
- Dữ liệu: export/retention/delete theo SME cần chính sách do chủ sản phẩm chọn;
  không tự xóa dữ liệu thật. Backup private/off-host và keys qua kênh riêng;
  cold restore đúng SME gồm keys, ACL, lịch sử, unknown không resend.
- Reboot/failover: chỉ môi trường riêng dùng một lần, drain/backup trước;
  worker restart trên Windows hiện tại không phải reboot drill. Không reboot PC.

## 5. S6.3 — owner nghiệm thu pilot

Chạy chuỗi nghiệp vụ với dữ liệu thật: nguồn→kế hoạch→AI jobs→owner review→
action được cấp riêng→report. Đo đúng dữ kiện, sai sót, phần cần sửa, token
reported, API billing nếu có, thời gian/CPU/RAM/queue theo tenant. Không quy
đổi token thành tiền bị trừ hoặc quota còn lại khi provider không xác nhận.
Owner ghi chấp nhận/từ chối cùng lý do; chưa có owner và dữ liệu thì pending.
Billing/subscriptions là backlog riêng, không tự kết nối thanh toán.

## Nguồn thiết kế CI — kiểm tra16/10/2026

[GitHub: PostgreSQL service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)
và [GitHub: workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
Services trên runner host cần mapped port; test dùng path/container local phải
được tách profile, không nới an toàn production để thích nghi runner.
