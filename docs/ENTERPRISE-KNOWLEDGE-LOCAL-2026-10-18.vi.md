# Doanh nghiệp, nhãn hàng và Kho tri thức — local18/10/2026

Trạng thái nguồn: **local_source_accepted**. Bản cài local chỉ được chốt đạt
khi `.runtime/organization-completion.json` có `pass=true`; receipt đó ghi
folder browser/live và binding thực tế sau khởi động lại. Không coi nguồn
đạt hoặc tiến trình khởi động là bằng chứng bản cài đã đạt.

## Phạm vi và quyết định đã chốt

- Chủ doanh nghiệp hiện có được tạo thêm doanh nghiệp do chính mình sở hữu.
  Tài khoản vẫn theo lời mời; không mở đăng ký công khai.
- Doanh nghiệp mới chỉ có Workspace và thành viên chủ tạo mới, không sao chép
  nhân viên, nhãn hàng, bộ nhớ, cấu hình, kết nối hoặc quyền từ SME trước.
- Cài đặt thêm tab Doanh nghiệp và nhãn hàng: tạo/đổi tên doanh nghiệp, tạo/
  đổi tên nhãn hàng, đường dẫn hồ sơ/đội ngũ/kết nối hiện có.
- Kho tri thức gồm hồ sơ doanh nghiệp, hồ sơ nhãn hàng, Skills cho agent và
  Tri thức/bộ nhớ. Hồ sơ dùng BusinessProfile/BusinessProfileVersion hiện có,
  không thêm kho hồ sơ khác. Quyền hồ sơ giữ owner/admin như backend hiện có.
- Skills phân nhóm theo chuyên môn, tìm/lọc, gắn phiên bản agent đã công bố;
  có biểu mẫu soạn agent/skill, kiểm tra lược đồ, duyệt/công bố và lịch sử.
  Gán lại agent tạo nháp mới, không thay phiên bản đang dùng hoặc công việc cũ.
  Phân nhóm chỉ là StudioEvent metadata; không sửa payload/hash thực thi.
- Giữ Studio nâng cao, Skills báo cáo hệ thống và đọc lịch sử; `/skills`
  chuyển về `/knowledge?tab=skills`. Không tạo menu chính thứ13.
- Không có runner mới, schema mới, quyền ghi Ads mới hoặc media renderer.
  Skill vẫn `llm_text`; nhóm Thiết kế/Editor không chứng minh có tạo ảnh/video.

## Quyền và giới hạn

Chủ doanh nghiệp tạo/đổi tên doanh nghiệp. Tuyến quản lý nhãn hàng mới dành cho
owner/admin; API nhãn hàng legacy giữ quyền hiện có, không tuyên bố đã thu hẹp
toàn hệ thống. Quyền soạn/duyệt Skills kế thừa Studio; model/agent/category không
cấp quyền Brain, tài nguyên, chi tiền hoặc dịch vụ ngoài.

Tạo doanh nghiệp có khóa giao dịch theo actor và Workspace, kiểm lại phiên và
thành viên, khóa idempotency theo actor, giới hạn20SME sở hữu/10lượt mỗi giờ.
Tên giới hạn120ký tự, không ký tự điều khiển; nhãn hàng tối đa100/SME, kiểm trùng
không phân biệt hoa/thường trong SME. Đổi tên kiểm phiên bản để không ghi đè mù.
Audit chỉ lưu định danh/fingerprint/phiên bản, không chép tên/secret vào details.

Danh mục Skills giới hạn200định nghĩa như Studio hiện có. Mẫu hệ thống chỉ đọc,
cần clone. Nhãn phân nhóm metadata chưa cam kết đi kèm mọi export/import legacy.
Không có bộ xóa doanh nghiệp/nhãn hàng, public signup hoặc tự động purge mới.

## Chuẩn bị an toàn

Nguồn thử riêng: `F:/Apex/enterprise-knowledge-candidate`.
Nguồn phục vụ giữ `F:/PAO-ACOS`; không sửa Apex/apex cũ hoặc Javis OS.
Checkpoint trước thay đổi:
`.runtime/checkpoints/p0-20261018T032559-1e25c407/manifest.json`, verified,
1320source/153tables/3archives/schema0071. Không sao chép `.env`, dependencies,
runtime hoặc Git vào source ZIP. Node dependencies chỉ dùng junction đọc lại.

Không migration mới:0071/153physical tables giữ nguyên. API dự kiến49routers/
406operations, tăng7operation tổ chức/catalog. Backend binding sẽ đổi theo
source mới; cần kiểm reader3archives, không sửa binding artifact cũ.

## Các kiểm tra và lỗi đã giữ lại

- Focused đầu:174pass/1fail ở đọc revision nhãn hàng. Sửa biểu thức JSON của
  SQLAlchemy sang `as_string()`; không sửa dữ liệu hoặc bỏ assertion.
- Focused tiếp:202pass/0fail/error/skip, gồm tổ chức/catalog, Studio, account/data
  lifecycle, app factory và125business tests. Bản receipt mới phải thêm hash
  nguồn đang thử và binding Windows của candidate để chốt cài đặt.
- Frontend132Node, TypeScript và production build23 đã chạy trên candidate.
  Có cảnh báo React hooks như log build; không tắt lint để tạo kết quả đạt.
- Native M6 business journey/12area/scope/history/recovery/mobile đạt; luồng
  tổ chức/Skills thêm riêng. Đã sửa nhãn truy cập rõ ràng cho textarea/select;
  test chuyển SME phải chờ context được xác nhận, không điều hướng giữa chừng.
- Linux6c190218... và9c3c39f... được dừng trước khi hoàn tất sau khi nguồn cần
  điều chỉnh; **không coi là full pass**. Container do từng UUID sở hữu được
  dọn, primary/env không đổi. Log/source/manifest thất bại được giữ nguyên.
- Linux nguồn cuối6a0bf77eb0794c779b04e4581c648e2d đạt cùng CI entry18stage.
  Operator readiness mới có7offline tests riêng; không cộng vào backend tests
  hoặc tự gọi chúng là đã chạy trong frozen CI trước khi file được thêm.

### Kết quả nguồn cuối

| Kiểm tra | Kết quả |
|---|---|
| Full Linux CI18stage | PASS,2272backend/0fail/error/skip,1384.97s,62cảnh báo ARQ |
| Node/TypeScript/build trong cùng pipeline |132Node/0fail, TypeScript PASS,23trang |
| Windows focused cùng nguồn/binding |202/202/0fail/error/skip; Py3.12.14 và lock đúng runtime mới |
| Native browser trên DB riêng | M6 business journey và luồng tổ chức/Skills PASS; sáng/tối,320/390px, lost ACK không gửi lại, dirty guard, operator bị chặn, SME mới riêng biệt |
| Operator readiness mới |7offline tests PASS, kiểm riêng sau frozen CI; không cộng vào2272 |
| Primary/env sau CI và browser | Không đổi; container/DB/process kiểm thử do harness tạo đã được dọn |

CI: `.runtime/s6-linux-6a0bf77eb0794c779b04e4581c648e2d/manifest.json`,
source SHA256 `ec07513fb74c52d259d43673277cb8809f64dc5808f5dbcbf8a4744fa07715f4`.
Windows: `.runtime/organization-focused-ee1d975c5696449ca4f80bd63f144066/receipt.json`.
Browser: `.runtime/organization-browser-runs/pao_s5_browser_c74a325b9f384082b06f037db2c47a8f/receipt.json`.
Binding Windows nguồn mới: `32f61a3ad3f7af17b811e6f9acd70c5d737c09fc9bcd8d9c13820ea8b3de1d0f`.
Linux dùng Python3.12.15, không giả rằng binding bằng Windows3.12.14; hash app/
test/contract và lock đối chiếu độc lập. CI này chạy local Linux, không phải
GitHub-hosted CI. Source app/test/contract không đổi sau frozen CI; tài liệu và
operator readiness được kiểm riêng, không mạo nhận cả các file thêm sau đã chạy
trong CI. Cảnh báo hook/lint và5high dev advisories kế thừa còn ghi trong log;
runtime audit không thay đánh giá production, không chạy audit-fix force.

## Nghiệm thu và đưa vào local

Chỉ cài sau khi đủ full CI đúng hash app/test/contract, Windows focused đúng
source/binding, production browser thật trên DB dùng một lần, cleanup và
primary/env unchanged. Cài có idle gate, xác minh PID/executable/start-time,
backup nguồn/cache, chỉ thay API/worker/Web sở hữu; không thay Docker, DB,
Ollama, secrets hoặc feature flags. Có rollback nguồn/cache, không restore
database chính để ép hash khớp.

Bản cài cần HTTP200/workerlease, OpenAPI406/schema0071/153tables, đọc3archive
giữ hash, browser chỉ đọc sáng/tối/mobile và so sánh toàn bộ bảng trước/sau.
Điểm chốt: `.runtime/organization-completion.json`; `pass=true` cùng
`primary_unchanged/env_unchanged=true` mới là local_accepted của bản cài.
Canonical S6 preflight sẽ nhận bằng chứng phiên bản mới; receipt S6.2/Phase3/
hosted cũ giữ nguyên tính lịch sử, không đổi thành CI cho source mới.

Toàn M6/S6, dữ liệu thật, provider/Ads, pilot owner và production chưa được
suy ra từ fixture. Thứ tự tiếp tục vẫn theo master: local → S6.1dữ liệu thật
đúng SME/brand/kỳ → pilot local → VPS/public khi được yêu cầu lại.

Hướng dẫn sử dụng: [Doanh nghiệp, nhãn hàng và Skills](ENTERPRISE-KNOWLEDGE-USER-GUIDE.vi.md).
