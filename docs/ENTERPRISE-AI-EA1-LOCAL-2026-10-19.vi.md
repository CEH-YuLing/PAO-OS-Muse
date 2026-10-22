# EA1 — AI cấp doanh nghiệp: nghiệm thu local và hướng dẫn

Ngày: 19/10/2026. Nguồn triển khai: `F:\PAO-ACOS`.

## Kết quả và phạm vi

Đã cài EA1: chính sách AI cấp doanh nghiệp, kế thừa kết nối API cho thành viên,
model mặc định, kiểm tra lại quyền khi chạy và giao diện tiếng Việt. Đây là
lát cắt local, **không phải hoàn tất kết nối Codex/Claude Code/Antigravity dùng
chung cho doanh nghiệp**. Policy thực vẫn tắt ở lần kiểm tra cuối; chưa gọi
provider, thử quota hay tự chuyển mặc định thực tế.

Mô hình sản phẩm là một SME / một VPS riêng, thường 1–3 người. Tiếp tục local
trước; chưa triển khai VPS/public. Không gộp các doanh nghiệp hiện có. Workspace,
nhãn hàng, private Brain, hội thoại, dữ liệu và ngân sách vẫn được khoanh vùng.
Không sửa nguồn bảo vệ hoặc `F:\PAO-BOS Backup 001`.

## Những phần đã triển khai

- Migration `0073` thêm hai bảng policy và lịch sử bất biến; không chuyển grant,
  hội thoại hoặc credentials cũ. Downgrade không được xóa lịch sử đã có dữ liệu.
- Owner/admin cấu hình nguồn API được dùng và model mặc định. Thành viên hoạt
  động kế thừa quyền suy luận, không cần grant riêng hoặc thời hạn cấp quyền ngắn.
- Chat mới và chọn model/routing native nhận nguồn cấp doanh nghiệp. Không đổi
  ngầm model hoặc quyền của các hội thoại/công việc đã tồn tại.
- Pin workspace/brand/actor/role/source/policy revision/auth version/membership
  epoch. Gỡ nhân sự, đổi vai trò, xoay khóa hoặc đổi/tắt policy vô hiệu pin cũ;
  kiểm tra lại trước gọi và công bố. Không tự repin/retry để vượt thu hồi.
- Dùng lại Run/ARQ/ledger/lease/ngân sách/approval; không thêm runner thứ hai.
- Người xem được mở chat văn bản riêng khi policy cho phép; không planner,
  công cụ, ghi bộ nhớ hoặc gắn Brain/Knowledge. Đây chưa phải trợ lý người xem
  có truy cập kho tri thức. Thành viên khác vẫn theo quyền ứng dụng hiện hành.
- UI có chính sách doanh nghiệp, nguồn/mặc định, xác nhận, Lưu và Đọc lại rõ ràng;
  quyền cá nhân cũ đặt trong phần nâng cao. Không hiện secret trong chính sách.
- Quyền dùng AI không cấp quyền cấu hình, xem bí mật, sửa dữ liệu, chạy Ads/MCP,
  SSH hoặc chia sẻ private Brain. Không tự fallback sang API trả phí.

## Cách cấu hình trên PAO

1. Chọn đúng doanh nghiệp và đăng nhập bằng owner/admin có quyền cấu hình.
2. Vào **Cài đặt và kết nối → AI và giọng nói → Quyền sử dụng AI**.
3. Bấm **Đọc lại**, xem trạng thái và phiên bản hiện tại.
4. Chọn các kết nối API đã được cấu hình cho doanh nghiệp và nguồn mặc định.
   Chưa có nguồn thì cấu hình tại Nhà cung cấp mô hình → Kết nối qua API trước.
5. Đọc cảnh báo phạm vi, xác nhận rồi Lưu chính sách. Lưu không phải bài thử
   kết nối thật, không xác nhận quota còn lại và không tự gửi yêu cầu đến model.
6. Mở hội thoại mới để nhận mặc định mới; hội thoại cũ không tự chuyển đổi.

Nếu mất phản hồi sau Lưu, Đọc lại để đối chiếu phiên bản; không gửi lặp mù.
Khi thay đổi kết nối/khóa, cần đọc lại policy và chọn nguồn hợp lệ. Xoay/xóa
khóa tại ô provider tương ứng; tắt policy để dừng quyền kế thừa. Các quyền cá
nhân cũ là cơ chế riêng, cần kiểm tra/thu hồi riêng nếu mục đích là dừng toàn bộ
quyền AI. Người xem không được thay đổi chính sách.

**Codex cá nhân hiện tại chưa dùng ở đây:** hệ thống từ chối dùng hồ sơ
`local_personal_self_only` làm nguồn chung, kể cả request có đánh dấu đồng ý.
Không sao chép cache đăng nhập hoặc chia sẻ tài khoản ngầm. EA2 sẽ bổ sung
identity/profile backend cấp doanh nghiệp sau kiểm tra cơ chế provider phù hợp.
Một VPS không tự chứng minh quyền dùng chung gói thuê bao.

## Kiểm thử của chính nguồn này

| Phạm vi | Kết quả | Giới hạn |
|---|---|---|
| Backend tập trung | 343 pass,0fail/error/skip | Không phải full regression toàn hệ thống |
| Migration/schema ứng viên | 0073 và schema check đạt | DB thử riêng `pao_test`, Redis15, chạy tuần tự |
| Frontend | 167Node, typecheck và production build23 trang đạt | Không đổi dependency live để chạy test |
| Browser fixture | Owner/save/ACK/SME/viewer/dark/light/1440/390/320 đạt | Chặn toàn bộ API thật/provider |
| Backup/clone restore trước cài | 155bảng,3archive,revision0072 đạt | Restore trên clone, không đè primary |
| Bản cài ngay sau migration | 0073,157bảng,419API; hàng cũ nguyên vẹn;3replay đạt | Kiểm tra tại thời điểm trước hoạt động đồng thời |
| UI bản cài | GET-only,1440/390,policy revision0/tắt đạt | Kiểm tra chức năng; không giả đồng ý/Lưu thật |
| Worker sau cài | Health check thành công lúc21:01:02 giờ Việt Nam | Không phải job provider thật |
| Kiểm tra cuối | API8100 `/health` và `/ready`, Web3200 đều HTTP200;28file khớp source-plan | Không đóng gate provider/production |

Backend kiểm tra policy/revision/SME/role/rotation/membership, chat người xem,
native execution/ledger, cơ chế grants/CLI cũ, Brain và business routing liên
quan. Network guard không cho gọi provider. Sáu cảnh báo ARQ deprecation trong
lượt backend được giữ; các cảnh báo hook frontend không bị tắt để làm xanh.

## Cài đặt và bảo toàn dữ liệu

Cài đúng28file theo source-plan; giữ bản trước trong `source-before/`. Có source
checkpoint và DB dump/clone restore được xác minh trước migration. Chỉ restart
API/worker/Web có executable và thời điểm khởi động đã xác nhận. `.env`, Python
runtime pin và CLI registry không đổi. Không pip update live, push, deploy,
chuyển hồ sơ CLI, tạo grant, bật policy hoặc gọi provider.

**Giới hạn đối chiếu sau UI:** kiểm tra nghiêm ngay sau cài đạt, nhưng lượt
đối chiếu tiếp theo thấy bốn bảng thay đổi: login sessions, connection audits,
connection grants và metadata leases. Log có đăng nhập20:57:39, thu hồi grant
20:58:43, thử đổi model/gửi chat20:59 giờ Việt Nam. Người dùng xác nhận có mình
hoặc công cụ khác đang thao tác. Browser chẩn đoán của lượt này chỉ cho GET;
không dùng điều đó để chứng minh database đứng yên. Giữ dữ liệu mới, receipt
thất bại và trạng thái cạnh tranh; **không restore primary hoặc sửa hash để pass**.
Snapshot trước UI riêng không được giữ; không suy ra nguồn của mọi thay đổi
chỉ từ các mốc log. Đây không phải bằng chứng giữ nguyên dữ liệu toàn phiên.

Giữ các lỗi thử trước: fixture/selector/browser executable, strict validation,
native snapshot ordering và helper đọc UTF-8 đã được xử lý trước kết quả cuối.
Lỗi đọc OpenAPI bằng encoding Windows mặc định làm checker báo khác giả; sửa
helper sang UTF-8, không nới assertion. Helper checkpoint trả zero trước lỗi
PowerShell lấy ký tự cuối thay vì dòng; manifest/ZIP/dump được xác minh lại,
không chạy restore primary. Không cộng các lượt test riêng thành full xanh.

Probe cuối ban đầu dùng nhầm cổng3100 và nhận connection refused; đối chiếu
helper cài đặt xác nhận API thực ở8100, sau đó cả health/readiness đều200.
Không đổi cổng/cấu hình hoặc restart dịch vụ để xử lý lỗi probe này.

Web ứng viên cổng13209 đã dừng theo đúng executable/start-time; giữ PAO chính
chạy. Không xóa thư mục bằng chứng, backup hoặc dữ liệu doanh nghiệp.

## Bằng chứng

- Backend: `.runtime/enterprise-ai-check-33fb7e6e0d7b47f0baa1c9dadb76c805/receipt.json`.
- Frontend: `.runtime/enterprise-ai-check-b87b2796cf0b4c78a2e45c291678132c/receipt.json`.
- Browser: `.runtime/enterprise-ai-20261019/browser-proof-1792417990756/receipt.json`.
- Checkpoint: `.runtime/checkpoints/p0-20261019T135344-eb595429/manifest.json`.
- Xác minh checkpoint: `.runtime/enterprise-ai-20261019/verified-checkpoint.json`.
- Kế hoạch file: `.runtime/enterprise-ai-20261019/source-plan.json`.
- Bản cài: `.runtime/enterprise-ai-20261019/installed-check.json`.
- UI thật: `.runtime/enterprise-ai-20261019/installed-ui.json`, `installed-ui.png`.
- Receipt drift giữ thất bại: `.runtime/enterprise-ai-20261019/installed-ui-primary-drift.json`.
- Lỗi checker ban đầu: `.runtime/enterprise-ai-20261019/installed-check-first-failure.json`.
- Tổng hợp có giới hạn: `.runtime/enterprise-ai-completion.json`.

## Thứ tự tiếp theo

1. **EA2:** identity/profile Codex cấp doanh nghiệp, tách khỏi người yêu cầu;
   queue/attribution/revoke/cancel/recovery và native fixture trước nghiệm thu thật.
2. **EA3:** Claude Code và Antigravity, adapter/auth/điều kiện sử dụng riêng;
   routing/usage theo cùng chính sách. Không chỉ dựng nút rồi tuyên bố kết nối.
3. **P8.4-D:** bỏ Ollama bắt buộc nhưng giữ cổng model local tùy chọn, bảo toàn
   memory/embedding và pin cũ; EA1 không đóng gate này.
4. **EA4:** owner + nhân viên pilot local, quota/đồng thời/lỗi/khôi phục; sau đó
   mới xét VPS/public. Provider thật, Ads thật và production vẫn chưa nghiệm thu.

Thiết kế và nguồn provider: [ADR AI doanh nghiệp](ADR-ENTERPRISE-AI-DEDICATED-2026-10-19.vi.md).
Trạng thái toàn hệ thống: [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md).
