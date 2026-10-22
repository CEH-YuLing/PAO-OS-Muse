# S2.2B3 — Quota Settings và nghiệm thu tích hợp local

Ngày14/10/2026. Target `F:\PAO-ACOS`; không sửa protected source.
Phạm vi: frontend dùng ba API resource đã nghiệm thu, không thêm database,
ledger, vault, scheduler hoặc router mới. Backend/schema/contracts không đổi.

## Kết quả chức năng

- Settings → General có quota của đúng doanh nghiệp đang chọn: AI/embeddings,
  MCP/Ads read jobs và metadata/discovery. Owner/admin quản lý; operator không
  đọc/gửi resource endpoint từ panel. Backend tiếp tục kiểm quyền độc lập.
- Hiển thị policy version, trần host, usage và thời điểm đọc; không polling.
  Version0 là mặc định, GET không tạo policy. Usage thiếu/không hợp lệ khóa
  form, không chuyển thành0. Null chi phí/quota provider ghi “Chưa xác định”.
- Ngày quota là UTC, không ngày local; labels giải thích07:00 Việt Nam.
  Embeddings giữ chỗ theo UTF-8 byte không phải token thực. Metadata expired
  unknown là toàn lịch sử; read jobs không tương đương số HTTP requests.
- Form chỉ nhận số nguyên dương trong ceiling. PUT dùng expected_version
  đã đọc; không overwrite/retry sau409. Lỗi hoặc response mất sau PUT khóa
  form, yêu cầu GET đối chiếu. Tải lại bỏ bản nháp, không tự gửi lại việc.
- Tenant transport no-store/abort/body ticket giữ nguyên. Card key theo
  actor/SME/role/scopeRevision; epoch+abort loại response cũ khi unmount.
  Models API chưa trả workspace_id, nên kiểm scope qua URL/ticket runtime;
  read/metadata thêm kiểm workspace_id trong snapshot.
- Hướng dẫn daily/concurrency/queue denial, Memory/Knowledge keyword fallback,
  không chuyển cloud/SME để vượt quota. Lưu policy không cấp model/tool/Brain
  consent, không bật Ads writes, refund usage hay hủy việc đang chạy.

## Thay đổi

- `ResourceQuotaPanel.tsx` + CSS: ba cards trong General Settings, help và
  khả năng thao tác mobile. Không thay form secrets/connection flags.
- `resource-quota.mjs` + declaration/tests: labels, strict parsing/snapshot
  validation, CAS payload và manual recovery help.
- `s22b3_browser_acceptance.py` + browser script: fixture pao_test/Redis15,
  server HTTP thật, không gọi provider. Không ghi policy lên main để làm xanh.

## Kiểm chứng

- Backend affected: **128 passed**,0skip; model/read/metadata resources,
  shared embedding và Knowledge embedding gates, gồm các test real ARQ.
  Có3 warnings ARQ.close đã tồn tại; không sửa ngoài phạm vi.
- **35 Node/runtime/SSE tests** đạt (25 cũ+10 quota); TypeScript và generated
  contracts đạt. Production build cách ly:21/21 trang. Cảnh báo lint cũ giữ
  riêng; warning cleanup mới của panel đã sửa, không tắt lint để làm xanh.
- Browser HTTP thật **1/1 đạt21.16s**: owner save/reload, strict invalid input,
  CAS xung đột từ request thật khác, PUT đã commit nhưng response bị mất,
  không tự resend, GET A bị trễ lúc chuyển SME B, admin lưu đủ ba pool,
  mobile390x844 thực sự lưu, mobile menu switch, operator không resource API,
  switch lại A không lẫn bản nháp/usage. Không page errors/overflow ngang.
- Lượt đầu128backend đạt/browser1lỗi do test dùng desktop selector bị ẩn
  trên mobile. Sửa test dùng menu mobile thật, chỉ rerun browser bị lỗi;
  không tuyên bố lượt193.20s đầu là129/129 xanh.
- Screenshot/report riêng:
  `.runtime/s22b3-quota-browser-5af0bcaa24af4e9ebefdd3c4c7494041/`.
  Đã xem screenshot; không gọi toàn bộ Settings mobile đã tối ưu chỉ vì quota
  thao tác được. Floating composer/layout tổng thể thuộc S2.3.
- Installed0058/live334/binding`c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`
  khớp; API/ready/Web200,workerhealthy,M2replay3/3. Cold-start Web lần đầu
  chưa200; rerun nguyên checker sau readiness, không bỏ endpoint.
- `.env` SHA256 giữ nguyên
  `5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`.
  Native connection counts và metadata hashes không đổi bởi live checker.
  Giữ1 lease model_catalogue hợp lệ của user,0metadata policies, không xóa.
- Candidate checkpoint trước startup:
  `.runtime/checkpoints/p0-20261014T041559-82b195cc/manifest.json`,993source,
  125physical/124business/3archives,0058. Seal cuối tạo sau cập nhật tài liệu;
  checkpoint riêng lưu runtime, exact restore clone kiểm row hashes/schema và
  primary unchanged. Không đưa dump/secrets vào source/Git; chỉ xóa clone do
  đúng invocation tạo, giữ dump/source backup để phục hồi.

## Docker recovery

Engine ban đầu tắt; log14/10 xác nhận inaccessible dockerInference. Stop CLI
20s chưa hoàn tất; đã kiểm executable/start-time, dừng đúng processes và
kiểm kê/cách ly đồng thời hai runtime directories chỉ socket0byte, directory
không reparse. Late stop hoàn tất sau đó; startup tiếp báo socket mới tái sinh.
Kiểm lại log/entries, dừng đúng processes, cách ly lần cuối rồi Engine29.4.3
phản hồi. Giữ hai cặp để rollback, suffix:

- `stale-s22b3-2a87e4ef8c94473bb4aa82edc2b0b4d0`
- `stale-s22b3-65f1e879aa724823b9ba7237f81f0af7`

Không xóa socket cũ/volumes/settings, reset/reinstall/update/reboot. PG/Redis
ACOS healthy; startup đúng target sau checkpoint0058. Đây không phải production
reboot drill. Hướng dẫn Docker có thêm ghi chú tránh late-stop race.

## Ranh giới và tiếp theo

**B3 và S2.2B native scoped coverage: local_accepted.** Không full backend mới,
không fullS2, không global host fairness/performance benchmark, không provider
billing/subscription quota hoặc live connector acceptance. Các quyền native,
generation/unknown/replay/ACL đã nghiệm thu không nới.

**Checkpoint tiếp theo duy nhất S2.3 Settings hợp nhất** theo master:
provider-specific help, SME/brand/member/account choice, chính xác trạng thái
saved/configured/connected/healthy/accepted, lifecycle/error/mobile/reload và
loại stale drafts trên các panels còn lại. Sau đó mới final integrated S2 gate.
