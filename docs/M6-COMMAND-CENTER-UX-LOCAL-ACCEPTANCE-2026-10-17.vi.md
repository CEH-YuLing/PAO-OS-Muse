# Giai đoạn 2 — M6 UX phục vụ S6

Trạng thái: **local_accepted trọn Giai đoạn2 — lát cắt M6 UX phục vụ S6**.
Không đồng nghĩa toàn M6, toàn S6 hoặc production đã nghiệm thu.
Target duy nhất `F:\PAO-ACOS`; bản thử source-only `F:\Apex\m6-candidate`.

## Phạm vi đã triển khai và chuyển vào dự án chính

1. Điều hướng 12 khu vực; các công cụ phụ nằm dưới khu vực tương ứng, giữ URL
   và chức năng cũ. Loại bỏ nút giả bộ lọc ngày/thông báo chưa có dữ liệu;
   tìm kiếm/phê duyệt có đích thực, không tuyên bố Copilot đã đọc trang.
2. Hành trình tiếng Việt hồ sơ→kế hoạch→AI→duyệt→chạy/duyệt nội dung→báo cáo;
   hướng dẫn người mới, trạng thái đang đọc/chưa lưu/quyền thiếu rõ ràng.
3. Bản nháp kinh doanh có phạm vi, TTL/bộ nhớ giới hạn, clear khi logout,
   revalidate server trước restore; không thay lớp remount/transport cách ly.
   Liên kết kế hoạch có SME, kiểm UUID/phạm vi; không dùng URL làm authority.
4. Danh sách kết nối/quyền cloud thay ô UUID thường dùng; chỉ GET metadata,
   không tự tạo/activate/probe hoặc fallback. Quyền brand khớp chính xác,
   `null` không là wildcard. Dependency dùng checkbox; lịch sử plan đọc riêng,
   nhân bản mới cần duyệt lại thay retry job cũ mù.
5. Cài đặt có deep-link tab/nền tảng, Back/Forward và bảo vệ nháp kết nối;
   giữ tab riêng và nhãn chưa hỗ trợ. Việt hóa trạng thái/ưu tiên/view Công việc;
   báo cáo hiện nguồn, khoảng thời gian và KPI chưa có dữ liệu đo, không thành 0.

## Bằng chứng đã đạt

- **120/120 Node**,0fail/0skip; TypeScript đạt cả candidate và installed.
  Production build23routes đạt trong candidate; giữ React-hook warnings cũ.
- **Browser Edge production candidate + API native/DB0071 riêng đạt**:
  hồ sơ v1/v2, kế hoạch/lịch sử ghim nguồn, hai model/kỹ năng và preflight,
  duyệt/task native, job và duyệt bản nháp, ngân sách/action mô phỏng/unknown
  reconciliation và báo cáo.12routes khách hàng, SME A/C owner giữ nháp riêng,
  SME B operator bị chặn, deep-link kế hoạch/Settings, back/keyboard, cảnh báo
  bỏ nháp kết nối, network-failure recovery và320/390px không tràn ngang đạt.
  Không nhập UUID thủ công trong flow phổ biến này. Gateway model chỉ fixture,
  không phải inference/provider thật; nhánh thiếu specialist bị từ chối thật.
- Receipt browser mới nhất:
  `.runtime/m6-browser-runs/pao_s5_browser_ed1b71dd167840e0b8dc2afd59568a4f/receipt.json`.
  Cleanup xác nhận đã dừng đúng process test, DB UUID đã không còn và hai port
  test18102/13200 trống. Giữ lượt fail `4e2056e8a3c14793b80eb3435ee38de2` và
  lượt pass trước `ce6572f360b04a0fa48e765f34660439`; không sửa log thành pass.
- **Installed read-only browser đạt** tại Web3200:12khu vực, hành trình kinh
  doanh và deep-link tab Zalo hiển thị chưa hỗ trợ; không có request mutation
  hoặc provider. Dùng token chẩn đoán chỉ trong process, không ghi token ra file.
  Evidence `.runtime/m6-installed-runs/20261017T061209/` có Node/typecheck,
  live/health, browser JSON/ảnh; frontend installed khớp byte với candidate.
- Frontend receipt hash:
  `eb4cce6bba55864d3a5c6d4e2f30ed9a18b8e3b8c56b769d4e8547cfa279d6a5`.
- **Primary0071/399operations/153physical**, API/ready/Web200, worker lease
  healthy và3/3archive replays read-only đạt. Hash toàn dữ liệu nghiệp vụ/`.env`
  và binding backend giữ nguyên; không restart API/worker hoặc migrate primary.
- Receipt kết hợp `.runtime/m6-completion.json`: local_accepted=true,
  s6_accepted=false, production_accepted=false; backend2258 baseline được kế thừa.
- Master/unified/architecture/S6 register và AGENTS được đồng bộ. Checkpoint
  hậu nghiệm thu source+DB/restore clone được ghi ở mục phục hồi bên dưới.

Checkpoint trước sửa: `.runtime/checkpoints/p0-20261017T055431-c5e5e77a/manifest.json`,
1238 source files/153 tables/3 archives/0071, dump+restore clone verified.
Backend baseline 2258/2258/0skip và binding
`8e9a71b996dee609d36868b8a254073c9ea16d4d78f56cf790d86690cf1b591b`
được kế thừa khi hash không đổi, không coi đây là một lần full backend mới.

## Giới hạn giữ nguyên

Đây là lát cắt M6 phục vụ S6, không phải toàn M6/S6/production. Dữ liệu browser
là synthetic; model có fixture rõ, không kiểm chất lượng model hoặc provider
thật. Chưa mở Ads/Telegram/MCP thật, chưa public deploy/push/hosted CI, chưa
xóa dữ liệu tự động. Retention tắt; host riêng/HTTPS/reboot/key/offsite recovery,
read-only đối chiếu nghiệp vụ thật, action thật và owner pilot còn gate riêng.
Không thêm backend, schema, runner, scheduler hoặc dependency mới.

Các warning React hooks và ARQ của baseline vẫn là nợ kỹ thuật. Build đầu bị
sandbox chặn mkdir; lỗi giữ trong lịch sử tool, không gọi là lỗi ứng dụng đã
được nghiệm thu. Sau chạy với quyền phù hợp build đạt. Lượt browser đầu dừng
vì kiểm link trước khi tải xong; đồng thời sửa bố cục header bị bó hẹp qua ảnh.
Giữ artifacts các lượt browser chưa đạt, không ghi đè thành pass.

## Phục hồi và bước tiếp theo

Source/DB trước sửa đã checkpoint ở trên. Bản sau nghiệm thu đã verify hash
và restore clone: `.runtime/checkpoints/p0-20261017T061447-61ce95cf/manifest.json`,
1250sourcefiles/153tables/3archives/0071. Phụ lục đường dẫn này được thêm sau
checkpoint, không đổi source ứng dụng. Source ZIP không chứa `.env`, key, Git
history, dependencies hoặc runtime.
Giữ JWT/Fernet riêng; source ZIP không thay thế key/offsite recovery. Không
restore đè primary hoặc xóa lịch sử để rollback frontend. Khi cần, đối chiếu
manifest và khôi phục12file frontend đã tồn tại trước M6 từ source ZIP trước
sửa, trong cửa sổ bảo trì có kiểm tra hash. Sáu file frontend mới không có trong
ZIP cũ; giữ riêng, không tự xóa file hoặc thay đổi mới của người dùng. Không
lấy cả backend cũ hoặc downgrade schema0071.

Tiếp theo **Giai đoạn3 — CI/private production thuộc S6.2** theo master. Chỉ
chuẩn bị/kiểm trong phạm vi được cấp; push/hosted CI/host riêng/HTTPS/reboot/key
ops chưa có quyền/môi trường thì pending. Không mở Ads/Telegram hoặc tạo dữ liệu
primary để vượt gate S6.1 đã hoãn; owner pilot và toàn S6 vẫn chưa hoàn tất.

Hướng dẫn: [M6 UX](M6-COMMAND-CENTER-UX-USER-GUIDE.vi.md).
Thứ tự tiếp theo do [master](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu.
