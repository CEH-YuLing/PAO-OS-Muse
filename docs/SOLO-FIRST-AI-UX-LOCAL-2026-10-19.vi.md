# PAO cho một chủ sở hữu và nhóm nhỏ — UX local

Ngày nghiệm thu:19/10/2026. Nguồn/bản cài: `F:\PAO-ACOS`.

## Phạm vi đã hoàn thành

Lát cắt này hoàn thiện **giao diện thiết lập AI đơn giản** trên backend EA1 hiện
có. Không phải hoàn tất kết nối Codex dùng chung, không thay cơ chế xác thực,
không tuyên bố PAO đã vận hành trọn vẹn chỉ bằng một lần bấm Kết nối.

- Nhãn cài đặt: **AI và giọng nói → Kết nối AI / AI mặc định / Giọng nói**.
  Các URL/section ID cũ vẫn hoạt động, không dịch enum hoặc đổi API.
- Màn hình **AI cho bạn và nhóm nhỏ** có ba bước: kết nối, chọn mặc định, làm việc.
  Một người không phải tạo nhân viên; phần quản lý cộng sự chỉ là liên kết tùy chọn.
- Tự tải thiết lập bằng GET, không gọi model/discovery provider hoặc ghi policy.
  Nguồn API duy nhất được đề xuất trên biểu mẫu, ghi rõ chưa lưu/chưa bật.
- Một nút Lưu thiết lập AI, vẫn cần xác nhận sử dụng. Giữ các nguồn bổ sung đã
  bật; không làm mất cấu hình nhiều provider khi chọn AI mặc định đơn giản.
- Đổi không gian/tài khoản/vai trò xóa state cũ, hủy request; response muộn
  không trộn dữ liệu. Kiểm tra response theo workspace và DTO whitelist, không
  giữ secret hoặc các trường ngoài hợp đồng UI.
- Mất ACK không tự gửi lại; chặn Lưu tới khi Tải lại. Response sai scope hoặc
  đọc lỗi cũng chặn thay đổi tới khi đọc lại hợp lệ. Lưu thành công xóa nhắc
  biểu mẫu chưa lưu; không tự thay hội thoại/công việc đã ghim.
- Quyền API cá nhân cũ và quyền Codex đặt trong Nâng cao, chỉ tải khi mở và chỉ
  hiện cho người quản lý. Không xóa hoặc kích hoạt lại các quyền này.
- Viewer không sửa cấu hình; owner/admin vẫn do backend xác minh. Không biến
  cách sắp xếp UI thành quyền xem dữ liệu, công cụ, đăng bài hoặc chi tiền.
- Giữ Client trước/API sau, ba ô Client và trạng thái chưa hỗ trợ đúng thực tế.
  Link thiết lập giữ chính xác SME đang chọn. Không bắt tạo tài khoản dịch vụ
  cho luồng cá nhân; không tự đăng nhập, chuyển cache hoặc fallback trả phí.

## Chưa hoàn tất — cần đọc cùng kết quả trên

API dùng chung đã có nền tảng EA1. **Codex hiện tại vẫn riêng cho người đăng
nhập và còn cần quyền cá nhân cũ trước khi gọi native run**; chỉ đưa bảng đó
vào Nâng cao không xóa yêu cầu backend. Lượt này chưa đạt mục tiêu bỏ thao tác
grant/TTL cho Codex. EA2.1 là công việc tiếp theo để đơn giản hóa thật sự luồng
chính chủ, giữ các kiểm tra thu hồi/accounting/cancel và xác nhận tiêu quota.

Codex cho nhiều thành viên, Claude Code, Antigravity, nghiệm thu model thật và
bỏ Ollama bắt buộc vẫn còn các gate riêng. Các dòng “kết nối một lần” mô tả
trải nghiệm mục tiêu và nguồn được hỗ trợ, không chứng nhận các adapter chưa có.
Không giới hạn cứng số người bằng UI;2–3 là nhóm mặc định để thiết kế, không là
khẳng định giới hạn gói của nhà cung cấp.

Tài liệu chính thức đã đối chiếu bằng OpenAI Docs19/10:
[Authentication](https://learn.chatgpt.com/docs/auth) có luồng người dùng đăng
nhập ChatGPT cho Codex. Điều đó không tự xác nhận dùng chung thuê bao cho nhóm;
không mua gói/tài khoản dịch vụ hoặc mở API trả phí trong lượt này.

## Kiểm thử và bản cài

| Kiểm tra | Kết quả |
|---|---|
| Node |179pass,0fail/cancel/skip, gồm12test helper mới |
| Typegen/TypeScript |Đạt |
| Production build |23trang, đạt trên ứng viên riêng |
| Browser fixture |Owner/admin/viewer, trống, một/nhiều nguồn, lost ACK, response sai và muộn, Client3ô; dark/light1440/390/320 đạt |
| Browser bản cài |GET-only,1440/390; không ghi API, không gọi provider |
| Health bản cài |API8100 health/ready và Web3200 settings đều200 |
| Bảo toàn nguồn |Đúng10file UI, backend/contracts/env/Python pin/CLI registry không đổi |

Đây không phải full backend regression mới. Không chạy lại343test EA1 để đổi
nhãn UI; backend và API contract giữ nguyên byte. Không migration, sửa database,
grant, secret, model mặc định thật hoặc thông số an toàn. Policy thực được đọc
ở bản cài vẫn revision0/tắt. Người dùng có thể thao tác đồng thời; **không tuyên
bố database đứng yên toàn lượt**, không restore primary hoặc sửa receipt cũ.

Checkpoint nguồn trước sửa có1483file đã xác minh, loại secrets/runtime/deps/
Git. Phát triển/build trên ứng viên `.runtime/solo-ai-20261019/source`; giữ
preimage10file trong `source-before/`. Chỉ restart Web3200 sau xác minh exe/
start-time; cache sinh ra được giữ trong quarantine. API/worker không restart.
Không sửa nguồn bảo vệ/backup, commit/push, VPS/public hoặc bật provider.

Lịch sử lỗi được giữ:

- Build đầu thất bại Windows EPERM khi tạo thư mục output ứng viên; chạy lại
  đúng ứng viên với quyền phù hợp đạt. Không đổi app/dependency để vượt lỗi.
- Guard chuẩn bị lần đầu so danh mục thiếu13file hạ tầng bổ sung: không có hash
  nguồn nào thay đổi. Sửa helper dùng cùng `source_supplements` với checkpoint;
  vẫn đối chiếu đầy đủ trước khi cài, không bỏ assertion.
- Cảnh báo hook có sẵn và Next workspace-root inference được giữ trong build
  log; không tắt lint hoặc xóa lockfile dự án để làm xanh.

## Hướng dẫn ngắn

1. Chọn đúng không gian đang làm việc.
2. Vào **Cài đặt và kết nối → AI và giọng nói → Kết nối AI** để cấu hình provider.
3. Với API được hỗ trợ, qua **AI mặc định**, chọn kết nối, bật, xác nhận và Lưu.
   Nhân sự không cần nhập lại key hoặc có grant model riêng khi EA1 đã bật.
4. Mở hội thoại mới. Không dùng trạng thái đã lưu thay cho kiểm thử model thật.
5. Codex cá nhân tạm theo hướng dẫn Nâng cao; Claude/Antigravity chưa kết nối.
   Không dán secret trong chat. Khi gặp mất phản hồi, Tải lại trước khi tiếp tục.

## Bằng chứng

- `.runtime/solo-ai-20261019/before-source.zip` và `before.json`.
- `.runtime/solo-ai-20261019/frontend-f82cdd5cc49e48479104a2704cce6507/receipt.json`: build EPERM, giữ thất bại.
- `.runtime/solo-ai-20261019/frontend-18688e530b214e32ba8a1be868d311cf/receipt.json`: Node/typecheck/build đạt.
- `.runtime/solo-ai-20261019/browser-proof-1792419884425/receipt.json`: fixture,0backend forwarded/0provider.
- `.runtime/solo-ai-20261019/source-plan.json`:10file.
- `.runtime/solo-ai-20261019/installed-check.json` và `installed-ui.json`.
- `.runtime/solo-ai-20261019/installed-ui.png`, `installed-ui-mobile.png`.

Trạng thái chung thuộc [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md).
