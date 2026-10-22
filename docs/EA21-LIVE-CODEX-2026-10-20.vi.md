# EA2.1 — Thử Codex thật và xử lý thông báo lỗi

Ngày20/10/2026, nguồn và bản cài `F:\PAO-ACOS`.

## Kết luận

**Nghiệm thu model thật chưa đạt.** Một yêu cầu thật đã được gửi từ trình duyệt
đang đăng nhập chính chủ qua API/ARQ/native accounting/Codex Docker, không phải
chạy CLI riêng rồi coi là PAO đã đạt. Thất bại `cli_provider_failed`; chưa xác
định được nguyên nhân sâu hơn. Không tự retry hoặc fallback API trả phí.

Thiết lập cá nhân được thấy ở revision1/bật/mặc định ngay khi mở trang, khác
trạng thái revision0/tắt lúc cài EA2.1. Agent không bật lại policy hoặc tạo grant.
Không suy từ trạng thái profile connected thành model hoạt động.

## Bài thử và bằng chứng

- Workspace `ef221310-5afc-4c21-9f9e-4aa9bf4b3e79`, chính chủ
  `165b1fa6-f443-4f66-bddb-51eb5b6e6fa5`.
- Tạo hội thoại riêng `c6cddc07-401b-41c5-8add-e3252992365e` bằng UI thật.
- Giữ model đã chọn `codex_cli / gpt-6.1-sol`; không đổi model/tài khoản.
- Thu hẹp chính sách hội thoại mới: tối đa1lần gọi, output128; cloud references
  tắt, knowledge tắt. Không cấp quyền công cụ hay thêm tài liệu.
- Prompt tổng hợp chỉ yêu cầu chuỗi `PAO_CODEX_OK`, không chứa dữ liệu kinh doanh.
- Run `4b4ba824-4d5d-4e61-b813-d0a9f73f9720` thất bại.
- LlmAttempt `6e4ff9e0-51ad-493f-bdfc-869cb5091db2`: nguồn `chat_planner`,
  authority `personal_cli`,12750ms, failed, usage unknown, input/output token null.
- Dispatch `8af4c590-18e9-4139-b17b-1b3de3177fa8`: failed; không còn dispatch
  dispatched/unknown sau bài thử. ToolCall0, MemoryJob0. Không kết luận quota0.

Hội thoại vẫn có cờ memory_enabled=true do UI tạo mặc định; đường cloud không
lấy memory vào inference, và bài thử thất bại không tạo job trích xuất bộ nhớ.
Không tuyên bố đã tắt cờ memory hoặc nghiệm thu luồng memory độc lập Ollama.
Không xóa hội thoại, dữ liệu hoặc lịch sử thất bại để làm sạch kết quả.

Chứng cứ `.runtime/ea21-live-20261020/before.json`, `after-first.json`,
`real-trial-failure.png`. Helper quan sát đầu tiên có lỗi dùng MemoryJob.id
(bảng dùng run_id); chỉ sửa helper rồi đọc lại, không thực hiện inference mới.

## Chẩn đoán an toàn đã làm

Đọc cấu trúc log trong đúng volume profile bằng container không mạng/chỉ đọc,
không đọc token/auth cache hoặc xuất raw log. Các log phân loại tìm thấy thuộc
19/10, không phải bằng chứng nguyên nhân của lần thử20/10.

Bootstrap offline xác minh binary và trạng thái CLI, tới được điểm exec. Chặn
exec ở lượt đó nên không gọi model. Startup thực với profile read-only báo lỗi
filesystem; đây là hạn chế của chẩn đoán read-only, **không chứng minh** nguyên
nhân lỗi ở native transport vốn dùng profile writable. Phương án HOME rỗng,
network-none không copy auth kết thúc do timeout15s; cũng không chứng minh
nhà cung cấp lỗi hay model không được hỗ trợ.

Hệ thống an toàn từ chối nâng diagnostic mount thành writable vì CLI có thể
cập nhật trạng thái phiên/auth. Lệnh bị từ chối chưa chạy. Không vượt chốt bằng
copy credential/profile. Đã hỏi một lần cho phép chẩn đoán ghi đúng profile và
tối đa một lần thử thật sau khi xác định/sửa lỗi; đang chờ người dùng trả lời.

## Phần tiếp tục triển khai đã cài

Sửa UI không còn hướng dẫn mọi lỗi model sang “worker và Ollama”. Các mã Codex
được giải thích tiếng Việt theo tình huống; mã lỗi nhà cung cấp chung được ghi
rõ là chưa biết nguyên nhân, không khẳng định sai hết quota/đăng nhập/model.
Không phản chiếu nội dung lỗi tùy ý; nhắc không retry/fallback trả phí tự động
và usage có thể chưa biết. Không đổi backend/API enum, quyền hay dispatcher.

Bản nguồn thử source-only1497file, backup `ui-before.zip`. Đã cài đúng4file:
helper `.mjs`, declaration `.d.mts`,11test mới và import vào `usePaoRuntime.ts`.
Toàn198Node đạt0fail/skip, TypeScript và build23trang đạt trong một lượt cuối.
Giữ lỗi build đầu EPERM/mkdir; lượt cuối được chạy lại đủ các stage, không ghép
hai lượt thành một pass. Warnings Next root/hooks có sẵn không bị tắt.

Sau cài: chỉ4file code đổi so với checkpoint; source backend/schema0074/contract421
giữ nguyên, `.env` và CLI registry hash giữ nguyên. Health/ready/Web200;
không còn dispatch CLI treo. Gate helper đầu đọc JSON tiếng Việt theo encoding
Windows sai nên báo lệch title.default; sửa helper đọc UTF-8 thì contract khớp,
không sửa API hoặc restart để che lỗi. Xem `ui2-check.json` và
`installed-ui-check.json`. Không có full backend regression mới.

Ảnh trước sửa ghi được lỗi thật; kiểm tra UI sau hot-refresh bị timeout trình
duyệt. Sau reload trang khôi phục phiên; chưa ghi được ảnh thông báo mới, vì
reload không tự phát lại run thất bại. Không coi build/unit là nghiệm thu browser
thông báo mới hoặc bấm retry để tạo ảnh.

## Chặng kế tiếp

1. Khi được phép, thu được chẩn đoán chuẩn hóa từ đúng CLI/profile, không raw
   token/log; xác định nguyên nhân trước khi thay model/auth/runtime.
2. Sửa nguyên nhân nếu nằm trong PAO, kiểm thử candidate và cài có rollback;
   không đổi subscription hoặc mua quota thay người dùng.
3. Tối đa một native job mới có scope nhỏ để nghiệm thu lại; không tự phát lại
   attempt cũ. Chỉ đóng gate khi ledger lẫn kết quả thật phù hợp.
4. Sau gate đó mới mở EA2.2 shared identity theo cơ chế provider hỗ trợ và EA3.

EA2.1 setup/fixture vẫn local_accepted; live job chưa đạt. EA2.2/EA3/P8.4-D,
toàn S6, owner pilot và production chưa được nghiệm thu bởi lượt này.

Đã đối chiếu hướng dẫn chính thức OpenAI ngày20/10:
[Authentication](https://learn.chatgpt.com/docs/auth),
[Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).
Không xem lưu phiên đăng nhập là bằng chứng inference hoặc quota còn lại.
