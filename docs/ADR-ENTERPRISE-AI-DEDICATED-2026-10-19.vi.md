# ADR — PAO riêng cho SME, AI tập trung ở backend

Ngày quyết định: 19/10/2026. Người dùng xác nhận rồi yêu cầu triển khai.

### Quyết định tiếp nối20/10

Người dùng chọn tạm hoãn Codex dùng chung (EA2.2), tiếp tục EA3. Không hỏi lại
hoặc yêu cầu chuyển gói tổ chức cho luồng cá nhân. Codex chính chủ đã nghiệm
thu model thật; dùng chung vẫn chưa triển khai. Cập nhật tiếp20/10: người dùng
chưa có Claude Pro/Max nên tạm dừng Claude, ưu tiên Antigravity. Ứng viên EA3
đạt95unit offline và Claude native pre-auth isolation, không live inference.
Antigravity CLI1.2.12 đã đo version/help; chưa auth/catalog/model. Gate quyền
tích hợp OAuth cá nhân vẫn riêng, không tự chuyển API/Enterprise/billing. Xem
[EA3 preparation](EA3-LOCAL-PREPARATION-2026-10-20.vi.md).

## Làm rõ: doanh nghiệp một người

Mặc định thiết kế cho một chủ sở hữu hoặc nhóm2–3 người, phần lớn là owner/admin.
Không bắt tạo nhân sự, mời thành viên hoặc tài khoản dịch vụ để dùng luồng cá
nhân. Workspace được diễn đạt thân thiện là không gian làm việc; ranh giới dữ
liệu và vai trò vẫn giữ nguyên. Tài khoản/AI không phải vị trí nhân sự phải tạo
để giao việc cho agent. Một người sở hữu nhiều không gian vẫn không được truy
xuất chéo ngầm. Xem [lát cắt UX đã cài và giới hạn](SOLO-FIRST-AI-UX-LOCAL-2026-10-19.vi.md).

EA2.1 ưu tiên làm gọn Codex cho chính chủ trước: đăng nhập/chọn model/đồng ý
thay vì thao tác bảng grant/TTL. Việc này chưa được triển khai bởi lát cắt UX.
EA2.2 mới là kết nối chung cho nhóm nhỏ, sau khi có cơ chế provider phù hợp.
Không suy từ một máy/VPS thành quyền dùng chung thuê bao cá nhân; cũng không
ép người dùng một mình chuyển sang identity tổ chức hoặc gói tính tiền khác.

## Quyết định sản phẩm mới

Hướng thương mại mặc định là một SME / một VPS PAO riêng, thường 1–3 người.
VPS chạy PAO, database, worker và các Client/API đã được hỗ trợ. Khách hàng chỉ
đăng nhập PAO. Không phân phối token/secret, quyền SSH hoặc hồ sơ CLI xuống máy
nhân viên. Đây là thay đổi so với ưu tiên SaaS dùng chung ngày 11/10, không phải
lệnh triển khai VPS/public ngay. Tiếp tục hoàn thiện và nghiệm thu local trước.

Giữ code workspace/multi-brand/membership để bảo vệ dữ liệu và hỗ trợ một người
tham gia nhiều doanh nghiệp. Không tự gộp, chuyển hoặc xóa dữ liệu của hai SME
đang có. Tạo doanh nghiệp mới không kế thừa kết nối, bộ nhớ hoặc nhân sự.

## Quyền AI và quyền làm việc là hai lớp khác nhau

Chủ sở hữu/quản trị viên bật một danh sách kết nối và chọn mặc định cấp doanh
nghiệp. Thành viên hoạt động kế thừa quyền suy luận, không cần tạo grant từng
người hay TTL 30–60 phút. Chính sách có phiên bản, có thể tắt và có lịch sử.

- Chủ sở hữu/quản trị viên: quản lý cấu hình theo quyền ứng dụng.
- Người thực thi/người phân tích: dùng AI, hành động vẫn qua kiểm tra công việc.
- Người xem: hội thoại văn bản riêng, không planner, công cụ, ghi bộ nhớ hoặc
  nâng quyền sửa ứng dụng. Lát cắt đầu chưa gắn nguồn tri thức vào chat người xem.
- Mọi người chỉ xem dữ liệu đã được cấp. Dùng chung kết nối không dùng chung
  phiên hội thoại, private Brain, ngữ cảnh hay quyền Ads/MCP.

Không tắt các kiểm tra membership, source, budget, approval hoặc worker để giảm
thao tác UI. Tái sử dụng Run/ARQ/ledger/lease hiện có; không thêm runner thứ hai.
Giữ lựa chọn model theo SME → brand → agent → step → job và execution pin.

## EA1 — Chính sách kế thừa, API và UX local

1. Migration 0073 bổ sung policy và lịch sử đồng ý bất biến; không chuyển đổi
   grant, credentials, hồ sơ CLI hoặc hội thoại cũ.
2. API quản lý chính sách, quyền kế thừa cho thành viên, mặc định ở chat mới,
   lựa chọn model và routing công việc dùng lại cơ chế native.
3. Pin policy/revision/source/actor/role/brand/auth-version/membership-epoch;
   kiểm tra lại trước gọi và công bố kết quả. Đổi role, gỡ/mời lại, xoay khóa,
   đổi/tắt policy làm pin cũ hết hiệu lực; không tự repin hoặc retry.
4. UI tiếng Việt ở AI và giọng nói → Quyền sử dụng AI: một chính sách doanh
   nghiệp, mặc định, đồng ý và Lưu rõ ràng; quyền cá nhân cũ nằm trong nâng cao.
5. Regression, migration/schema, browser fixture dark/light/mobile, source/DB
   checkpoint và kiểm tra bản cài trước khi xác nhận local accepted.

EA1 đã nghiệm thu lát cắt API/chính sách local và cài bản 0073 ngày 19/10.
Xem [báo cáo và hướng dẫn](ENTERPRISE-AI-EA1-LOCAL-2026-10-19.vi.md).
Policy thực vẫn tắt ở lần đọc cuối; không gọi provider. Hồ sơ CLI doanh nghiệp
và nghiệm thu thuê bao không thuộc kết quả EA1. Lượt so dữ liệu sau UI có thay
đổi do có thao tác đồng thời được người dùng xác nhận; giữ nguyên dữ liệu và
receipt thất bại, không suy ra database đứng yên trong toàn lượt triển khai.

## EA2 — Client cấp doanh nghiệp: Codex trước

Làm rõ20/10: EA2.1 cho chính chủ đã cài0074. Dùng `personal_cli` authority có
revision và source pin, không grant/TTL; chỉ owner/admin sở hữu hồ sơ, không
ủy quyền thuê bao. Kiểm tra actor/role/auth/membership/source tại dispatch và
trước công bố; không ghim lại job cũ. Xem [nghiệm thu EA2.1](EA21-PERSONAL-CODEX-LOCAL-2026-10-20.vi.md).
Không suy kết quả này thành EA2.2 dùng chung đã xong. Phần sau mô tả yêu cầu
identity dùng chung còn lại, không phải điều kiện bắt buộc của luồng cá nhân.

Chưa triển khai trong EA1. Hồ sơ Codex hiện có vẫn `local_personal_self_only`.
Không tự chuyển hoặc chia sẻ cache cá nhân. Policy EA1 từ chối bật một UUID hồ
sơ CLI cá nhân, kể cả người gửi request đánh dấu đã đồng ý.

Cần hoàn thiện: identity/profile backend dành cho doanh nghiệp, cơ chế xác
thực phù hợp, quản lý bởi owner/admin, tách profile principal khỏi người yêu
cầu, giữ attribution/ledger và khóa cạnh tranh một profile, recheck/revoke/
cancel/recovery. Kiểm tra fixture trước; sau đó mới có consent/login/inference
thật. Không lấy tài khoản của người vận hành PAO phục vụ nhiều khách hàng.

## EA3 — Claude Code, Antigravity và lựa chọn công việc

Adapter riêng, hướng dẫn và điều kiện sử dụng riêng theo tài liệu chính thức
tại thời điểm làm; không chỉ dựng nút rồi tuyên bố kết nối. Giữ capability,
privacy, queue, usage và no-paid-fallback. API và Ollama là tùy chọn độc lập;
bỏ phụ thuộc Ollama bắt buộc là P8.4-D, chưa được coi là xong bởi EA1.

## EA4 — Nghiệm thu thực tế, bộ cài và vận hành riêng

Thử 1 owner + 1–2 nhân viên, hạn mức/đồng thời, role viewer, gỡ nhân sự, lỗi
provider, khôi phục/restart và backup bằng dữ liệu được chọn. Sau owner pilot
local mới lập rollout VPS/HTTPS/keys/offsite/monitoring. CI/production, dữ liệu
Ads thật, phát hành nội dung và chi tiền vẫn là gate riêng, chưa đạt.

## Tài liệu provider đã đối chiếu ngày 19/10/2026

- https://learn.chatgpt.com/docs/auth : ChatGPT sign-in và API là các cơ chế khác
  nhau; workspace/seat/role tiếp tục có hiệu lực.
- https://learn.chatgpt.com/docs/enterprise/service-accounts : identity tổ chức
  cho headless/shared automation; tài liệu hiện ghi pay-as-you-go.

Một VPS không tự chứng minh quyền dùng chung một thuê bao cá nhân. Các nguồn
trên hướng dẫn thiết kế, không phải nghiệm thu commercial Codex/Claude/Google,
không cam kết miễn phí/không giới hạn hoặc chuyển sang gói tính tiền.
