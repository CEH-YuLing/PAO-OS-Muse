# PAO local — nghiệm thu UX và giao diện sáng/tối

> Bổ sung21/10: có thêm lựa chọn Tự động theo giờ thiết bị, giữ nguyên Sáng/Tối.
> Xem [báo cáo Auto](LOCAL-THEME-AUTO-2026-10-21.vi.md). Các kết quả18/10 bên dưới
> giữ nguyên theo source/ngày cũ, không phải bằng chứng cho phần Auto mới.

Ngày bàn giao: **18/10/2026, Asia/Saigon**. Target: `F:\PAO-ACOS`.
Phạm vi: rà soát UI và hợp đồng backend phục vụ UX, cải thiện khả năng sử dụng,
triển khai hai giao diện trên local. Không phải audit bảo mật toàn backend,
nghiệm thu toàn M6/S6, kết nối thật hoặc production.

## 1. Kết quả

**Lát cắt UX này đã nghiệm thu local và cài vào Web3200.** Giữ 12 khu vực,
các trang con, chat/Copilot và Settings theo nền tảng. Không thay API/nghiệp vụ,
schema, dependency, secret, quyền SME hoặc cờ kích hoạt dịch vụ.

| Vấn đề trước đây | Thay đổi |
|---|---|
| Màu dark viết cứng rải rác, khó thêm light nhất quán | Bảng màu ngữ nghĩa chung cho nền, panel, chữ, viền, trạng thái và focus; không dùng bộ lọc đảo màu |
| Chữ nhỏ, trạng thái kỹ thuật luôn chiếm chỗ | Tăng cỡ chữ cơ sở ở navigation/workspace, cân khoảng cách; thông tin kỹ thuật có thể mở/đóng |
| Chưa chọn được sáng/tối | Nút mặt trời/mặt trăng trên header; phần Giao diện hiển thị trong Settings; áp dụng cả trang đăng nhập/tham gia |
| Khó nhận biết bước bắt đầu | Dashboard có hướng dẫn ba bước; link kế hoạch vẫn phụ thuộc khả dụng/quyền do server trả |
| Một số nhãn chính còn tiếng Anh | Việt hóa nhãn hiển thị ở Dashboard/PAO AI; giữ nguyên provider, enum, ID, URL, nội dung người dùng và dữ liệu API |
| So sánh hai giá trị thiếu có thể hiển thị READY | Thiếu/không hợp lệ/0 trên 0 không được suy thành hoàn thành |
| PAO AI có nhãn Runtime/Voice READY viết cứng | Trạng thái cấu hình phân biệt bật/tắt/chưa xác minh; voice đọc endpoint hiện có, xóa trạng thái khi đổi ngữ cảnh và bỏ response cũ |
| Copilot đóng vẫn có phần tử nhận focus | Chỉ mount khi mở; Escape đóng, đặt focus ban đầu và trả focus về nút gọi |

Đã chuyển **49 file frontend**, không viết lại stack hay thêm backend thứ hai.
Các module vẫn dùng FastAPI modular monolith và các dịch vụ Run/Task/Goal/Studio
hiện có. Giao diện không cấp thêm quyền hoặc làm bằng chứng kết nối provider khỏe.

## 2. Cách sử dụng

1. Mở `http://127.0.0.1:3200`.
2. Bấm biểu tượng mặt trời/mặt trăng góc trên bên phải để đổi giao diện.
3. Hoặc vào **Cài đặt và kết nối → Tổng quan → Giao diện hiển thị → Sáng/Tối**.

Lựa chọn được nhớ trên trình duyệt này, đồng bộ giữa các tab cùng trình duyệt.
Mặc định vẫn là tối để giữ trải nghiệm cũ. Đây không phải cài đặt tài khoản
đồng bộ giữa máy hoặc dữ liệu thuộc SME. Chỉ lưu giá trị `light`/`dark` tại khóa
`pao.ui.theme`, không lưu token/secret. Khi trình duyệt chặn lưu trữ, nút đổi
giao diện vẫn dùng được trong tab hiện tại. Bootstrap trước paint hạn chế nháy
sai theme khi tải lại.

## 3. Kiểm chứng và phạm vi bằng chứng

| Kiểm tra | Kết quả |
|---|---|
| Node unit tests, gồm theme và nhãn trạng thái mới | **128/128**, 0 fail/skip |
| TypeScript và production frontend build | **Đạt**, 23 trang |
| Business journey qua API native và database thử riêng | **Đạt**: profile/version/plan/routing/job/draft review/history; SME/vai trò/nháp/deep-link/network/keyboard/mobile |
| UI hai theme trong môi trường thử riêng | **13 màn hình × 2 theme**; persistence, cross-tab, blocked storage, mobile390/320 và Copilot Escape/focus đạt |
| Kiểm tra chỉ đọc trên Web cài thật | **4 màn hình × 2 theme**, tab kết nối và mobile390 đạt; 0 API mutation/0 provider call/0 browser error |
| Live API/contract và lịch sử | **0071**, 399 operations, 153 bảng physical, replay chỉ đọc **3/3** |
| Health cuối sau khởi động lại | API health/ready/Web **200**, worker healthy |
| Đối chiếu trước/sau lượt kiểm installed | Primary snapshot, `.env`, frontend hash và backend binding khớp |

Mẫu tương phản chữ đã đo: light tối thiểu **5.25:1**, dark **7.73:1** trên
các nhãn/navigation/KPI/context được chọn; không phải chứng nhận WCAG toàn bộ
giao diện hoặc kiểm mọi pixel/mọi trạng thái. Native business journey sử dụng
fixture trong database riêng, không phải nghiệm thu dữ liệu doanh nghiệp thật.

Không chạy lại toàn bộ2258backend trong lượt UX vì source backend/dependencies
không đổi. Hosted CI commit3151851/run39030584315 là baseline lịch sử đã có,
**không phải hosted CI cho 49 file UI mới**; không cộng các lượt riêng thành
một full regression mới. Lượt này có Node/build/browser/live read-only riêng.

### Bằng chứng

- Node: `F:\Apex\local-ux-node-final.log`.
- Build: `F:\Apex\local-ux-build-v3-clean.log`.
- Candidate source: `F:\Apex\local-ux-candidate`.
- Native business/theme browser và cleanup:
  `.runtime/local-ux-browser-runs/pao_s5_browser_5c314e9e460440c3b614300fe89e2337/`.
  `receipt.json`, `theme-browser.json`, `cleanup.json` đều pass; database thử
  đã dọn và cổng thử đã trả lại.
- Release manifest: `F:\Apex\local-ux-candidate\.runtime\local-ux-release.json`.
- Installed: `.runtime/local-ux-installed.json` và
  `.runtime/local-ux-completion.json`.
- Installed screenshots/log:
  `.runtime/local-ux-live-63a3b9c977e3412eb1f6612fa76fb188/`.
- Live: `.runtime/s62-live.json`; backend binding
  `8e9a71b996dee609d36868b8a254073c9ea16d4d78f56cf790d86690cf1b591b`.

Giữ bằng chứng runtime tại local, không đưa dump/ảnh dữ liệu/JWT vào Git.
Diagnostic JWT chỉ tồn tại trong tiến trình kiểm thử, không ghi trong fixture.

## 4. An toàn, phục hồi và các lần lỗi được giữ lại

Checkpoint trước thay đổi:
`.runtime/checkpoints/p0-20261017T140245-abd8b8e6/manifest.json`, verified,
1292 file source, 153 bảng physical, 3 archive, schema0071. Bộ cài kiểm hash
nguồn trước/sau và chỉ thay apps/web, không đè file ngoài release allowlist.
Source cũ và cache cũ được giữ để hoàn tác tại:
`.runtime/local-ux-install-667c1ca78aac4803ae0cbb2ff371c65c/`.
Không tự restore database để khớp snapshot.

Các lỗi trước khi bàn giao không bị xóa hoặc đổi thành pass:

- Lượt theme browser đầu thiếu chọn SME trong test; sửa test chọn workspace
  và chờ trạng thái scoped, không nới auth/quyền. Giữ folder9c6d... và cleanup.
- Thay nhãn quá rộng làm sai hai props `active`; TypeScript bắt lỗi trước
  build/cài, đã phục hồi props và chỉ dịch nhãn hiển thị.
- Build từng bị EPERM cache candidate; xác minh đúng đường dẫn và chuyển cache
  cũ sang `.runtime/build-cache-before-v3-66e721d3f4174b17b73fce12e5300fb1`
  trong candidate để phục hồi, clean build sau đó đạt; không xóa source/cache
  của dự án khác.
- Lượt installed đầu18/10 dừng trước browser do PostgreSQL chưa chạy sau boot;
  không tạo completion pass. Log Docker mới xác nhận lỗi socket dockerInference.
  Đã dừng đúng tiến trình Docker đã kiểm executable/creation time và cô lập
  socket-only directories, giữ bản cũ. Thao tác tạo lại thư mục secrets lần đầu
  báo đã tồn tại: dừng để kiểm kê lại, sau đó rename riêng thư mục socket rỗng
  còn lại và kiểm nguồn đã biến mất trước tạo mới. Không xóa/reset/reinstall,
  không đổi Docker settings/volumes, không reboot Windows.
- Các bản giữ socket có suffix `stale-ux-d7fdc272dbea4b5e984fd627481a8df3`;
  bản secrets kiểm lại có suffix
  `stale-ux-recheck-3ec3b2542547491ebcdafc465603d090`, dưới AppData/Local.
  Không tự áp dụng lại recovery này nếu chưa xác minh log/process/path mới.
- Engine29.4.3 đã phản hồi; chỉ start lại hai container ACOS có sẵn. Đọc schema
  trước launcher vẫn0071; launcher không có migration mới. Chỉ khởi động các
  dịch vụ theo cờ hiện hành, Telegram/Studio durable vẫn tắt.
- Health đầu lúc Web cold-start báo unavailable; sau Ready24.6s và tải trang,
  đã chạy lại checker nguyên vẹn, đạt cả ba endpoint và worker. Đây không phải
  production reboot/recovery drill.

Backend/API source, schema và `.env` không bị sửa để chữa UI. Không bật Ads,
Google, Telegram, voice, Temporal hay retention; không chi tiền, gửi tin,
public deploy hoặc push/commit trong lượt này. File scripts hỗ trợ nghiệm thu
là operator tooling, không phải runner nghiệp vụ mới.

## 5. Đánh giá cấu trúc và phần tiếp theo

Giữ kiến trúc hiện tại hợp lý hơn đổi stack cho nhu cầu này: token giao diện
tập trung, theme provider chung và helper trình bày có test giải quyết thiếu
nhất quán mà không kéo theo thay đổi authority dữ liệu hoặc API. Backend giữ
kiểm quyền SME tại server; Business Planning vẫn tách `available/can_manage`
và external action. UI voice chỉ đọc endpoint hiện có, không bật runtime.

Chưa tuyên bố mọi form/empty state/luồng chuyên sâu đã tối ưu hoặc Việt hóa
100%; chưa đo toàn bộ accessibility, hiệu năng production dài hạn, chất lượng
trên mọi model hay dữ liệu thật. Nợ dev npm5high, ARQ warnings và Actions/image
drift vẫn giữ review riêng, không được coi đã xử lý bởi theme.

Roadmap thống nhất được cập nhật: **local core → dữ liệu thật local → pilot
local → VPS/public sau**. Phần tiếp theo là rà soát các khoảng trống còn lại
trong vòng hồ sơ → kế hoạch → chọn AI/job → chạy → duyệt → báo cáo, lịch sử
phiên bản và retry/phục hồi trên nền đã có; không làm lại P6/S5 hoặc thêm runner.
Gate dữ liệu/provider thật chỉ mở theo SME/brand/tài khoản/phạm vi được chọn;
host/HTTPS/keys/offsite/alerts/reboot và production vẫn hoãn theo người dùng.
