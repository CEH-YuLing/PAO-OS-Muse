# ADR-S1.2 — Cô lập dữ liệu phía trình duyệt theo SME

Ngày 11/10/2026. Target `F:\PAO-ACOS`. Tiếp nối ADR-S11; không thay tenant
authorization phía server, database, credential hoặc gate thực thi.

## Quyết định

Mỗi thế hệ context trong một tab có một ticket và AbortController riêng.
Chuyển SME, logout, mất membership hoặc thay role làm ticket cũ hết hiệu lực,
hủy request phía client, thu hồi object URL và remount subtree dữ liệu/draft.
Không gọi cancel server run, chuyển workspace của run hoặc sửa execution pins.
User/SME/revision khác nhau không được dùng lại closure API cũ.

- `tenant-transport.mjs` quản lý ticket, ép `cache: no-store`, kết hợp signal của
  caller và context; kiểm trước/sau headers, trước/sau đọc JSON/text/blob/
  arrayBuffer/formData/bytes, cả Response clone và body reader/SSE.
- `api`, `apiRaw` và runtime SSE dùng transport chung. `apiRaw` giữ các headers
  của caller (If-Match, Content-Type) nhưng Authorization lấy phiên hiện hành.
- Download Brain/file/ZIP/chat/attachment đi qua helper chung; chỉ tạo URL/click
  sau khi body hoàn tất và ticket còn hiệu lực. Thu hồi URL khi đổi context hoặc
  sau download. Không thu hồi được file đã tải xuống máy trước thời điểm switch.
- Voice giữ cơ chế cleanup audio/microphone/generation đã có, nhưng đọc raw body
  có thêm transport fence. Hint turn và prompt mới dùng namespace
  `pao.scope.v1.<actor>.<SME>.<kind>.<resource>`, escape cả dấu chấm.
  Logout dọn namespace của chính actor. Không nhập prompt/voice hint legacy
  không có actor; preference workspace chỉ là ID, không phải quyền truy cập.
- Membership được đọc lại qua `/v1/me` khi focus/pageshow/tab hiện lại, mỗi
  30 giây nếu tab visible, và nút “Làm mới quyền doanh nghiệp”. Probe timeout
  5 giây; lỗi xác minh thì xóa active context (fail closed). Probe cũ không thể
  xóa selection/identity mới. Role đổi thì remount context, mất membership thì
  xóa preference và yêu cầu chọn rõ, không tự chuyển sang SME còn lại.

## Giới hạn có chủ đích

Client fencing là chống hiển thị nhầm dữ liệu, không phải authorization.
Server vẫn phải kiểm membership/quyền Brain/resource/action; worker/outbox/
queued execution negative corpus thuộc S1.3. Role/membership trên browser
không cập nhật tức thời: có cửa sổ tới lần probe tiếp theo; quyền hành động do
server quyết định. Browser offline không được tiếp tục giữ active context sau
probe thất bại. Không đồng bộ selection giữa các tab; sessionStorage theo tab.

Không thể “rút lại” dữ liệu đã đọc hợp lệ, file đã lưu hoặc bản sao do người dùng
tạo trước revocation. Không triển khai server cache/RLS/JWT rotation/single
sign-out toàn thiết bị trong checkpoint này. Dùng AbortSignal.any/timeout nên
gate hiện hành là Edge/Node trên máy này, không suy ra hỗ trợ mọi browser cũ.

## Kiểm chứng

`scripts/check_s12_tests.py` ép pao_test/Redis15, chạy pure transport/runtime,
TypeScript, tenant/chat/voice backend và ba browser gates S12/S11/P7.
S12 dùng API/DB/Next proxy thật; chỉ seed synthetic run/events trong pao_test.
Middleware test giữ trễ body export thật sau 64KiB để thử switch sau headers.
Hai tab, prompt scope, focus role refresh và revoke membership có handshake
fixture; không gọi LLM, không send channel hoặc dùng microphone thật.
Kết quả được ghi riêng trong S12 acceptance, không suy ra nghiệm thu production.
