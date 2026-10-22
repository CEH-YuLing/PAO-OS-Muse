# S2 — Nghiệm thu tích hợp cuối, 14/10/2026

Checkout: `F:\PAO-ACOS`; giữ nguyên nguồn được bảo vệ `F:\Apex`.
Trạng thái: **local_accepted — toàn S2, 14/10/2026**. S2.1/S2.2/S2.3A–F và
cổng tích hợp đã đạt trong phạm vi local dưới đây; không phải production-ready.

## 1. Phạm vi

- Nền tảng connection/grant theo SME, model/MCP/Ads read authority, vault/version,
  quota models/reads/metadata, legacy accounting và Memory/Knowledge embeddings.
- Settings observations, cloud/MCP/Ads/host lifecycle, team/account/mobile;
  kiểm tra hồi quy S1/P6/P7 để không chỉ nghiệm thu từng module độc lập.
- Database thử riêng `pao_test`, Redis DB15, API/Web thử do harness sở hữu.
  Installed API8100/Web3200 chỉ đọc; không bật connector, chi tiền, quảng cáo,
  gửi tin thật hoặc deploy. Fixture transport không phải nghiệm thu provider thật.

## 2. Lỗi phát hiện và cách xử lý

### Test harness và các hợp đồng cũ

Lượt đầu dừng vì test downgrade dùng fixture không còn tạo multi-agent history:
lệnh downgrade chạy trên database thử dùng chung đã hạ schema tới0002. Database
chính không bị tác động. Chỉ dừng cây pytest thuộc lượt này; khôi phục schema
`pao_test` bằng migration tới head0058. Test downgrade nay gọi guard native trong
transaction luôn rollback, xác nhận history tồn tại trước và revision không đổi
sau. Fixture client thêm kiểm tra revision/danh sách bảng, dừng suite ngay nếu
test làm lệch schema; không âm thầm sửa database giữa các test.

Các test positive legacy cần opt-in hợp đồng engine/chat hiện hành; fake gateway
phải có provider/model đúng, typed ExecutionPlan và bounded max_tokens. Không
bật flags toàn suite hoặc hạ chuẩn fail-closed: planner sai nay bị từ chối trước
inference. Usage kiểm theo normalized output_tokens, không theo raw provider key.
Fixture ba tài khoản dùng chung hash Argon2 thật của mật khẩu thử để giảm chi phí
setup; login vẫn xác minh bằng thuật toán production, không mock authentication.

Hai helper crash/recovery Skill/ARQ cũng cập nhật hợp đồng admission; giữ nguyên
worker thật, kill/restart, thời gian lease thật và kiểm tra đúng một tool claim.
P7 restore checker chấp nhận additive revisions0057/0058, giữ nguyên hash/dedup/
no-resend. S1.3 kiểm tra revocation spy đúng resolver hiện có thay vì symbol đã
được loại bỏ; vẫn chặn gateway và bảo vệ private Brain/SME khác.

### Lỗi native Telegram admission

Telegram legacy tự tạo Run, thiếu immutable engine/accounting/Brain pins.
`apps/api/pao/telegram.py` nay gọi shared `admit_run(..., commit=False)` như
Web/Channels: receipt, Run và accepted delivery nằm trong một transaction.
Session phải đồng thời thuộc peer.workspace_id và peer.user_id, khóa cùng
conversation để giữ một active run. Hai negative cases chặn session của SME khác
hoặc member khác, không lưu Run/receipt/delivery. Không sửa hoặc repin history,
không bật Telegram thật, chưa triển khai multi-bot S3.

Backend binding sau rollout có kiểm tra idle/process identity:
`3d811e0e99227ea0ba4c0f8634ee00bbbf7023d6b8f510575746784501d6e294`.
Schema0058 và contract334operations/43routers không đổi. Installed API/ARQ đã
restart có kiểm soát; không thay `.env`, Docker, Web hoặc external flags.

## 3. Bằng chứng và các lượt chưa đạt

Không cộng các lượt test chồng nhau thành một số pass tổng giả định.

| Lượt | Kết quả | Bằng chứng |
|---|---|---|
| Full đầu | interrupted; schema test lệch, không có full summary | Không dùng để đóng gate |
| Bounded diagnostic |782passed/10failed/0skip;952.86s |`.runtime/s2-final-backend-20261014T092140.xml` |
| Focused diagnostic |151passed/1failed;62.30s |Telegram native admission thiếu pins |
| Full trước sửa cuối |1676passed/6failed/0skip;1448.02s |`.runtime/s2-final-backend-20261014T094507.xml` |
| Focused sau sửa |93passed/0failed;91.10s |Telegram/helper boundary/Channels/P7 restore/S1.3/Skill process/legacy-model fences |
| Full cuối |1684passed/0failed/0errors/0skip;1603.63s |`.runtime/s2-final-backend-20261014T101850.xml`; real ARQ wall-clock bật |
| Browser tích hợp đầu |19passed/2failed;495.08s |`.runtime/s2-final-browser-20261014T104605.xml`; metadata old selector, MCP route failure |
| Browser focused recovery |3passed;57.57s |`.runtime/s2-browser-focused-recovery.xml`; metadata + hai ca MCP |
| Browser tích hợp cuối |21passed/0failed/0errors/0skip;418.84s |`.runtime/s2-final-browser-20261014T105719.xml`; tuần tự sau focused recovery, không tranh database/cache |
| Node/runtime/SSE |80passed/0failed/0skip |11test files của `apps/web/lib` |
| TypeScript + production build | passed;21/21routes | Không bỏ lint/type checking |
| Synthetic shell smoke |12routes passed |`verify_workspace_ui.cjs`; mocked API, không gọi đó là real browser acceptance |
| Installed GET-only |passed trước/sau backend rollout |8manager GETs,401/404,no-store,3quota pools,health/ready/Web200 |

Installed checks xác nhận0058/OpenAPI334/current binding/125physical tables/
3M2archives. Hash toàn bộ business tables và `.env` không đổi qua lượt GET-only.
Backup/exact restore backend mới đã đạt ở
`.runtime/checkpoints/p0-20261014T110012-c7728227/manifest.json`:
1051source files,0058,124business/125physical tables,3archives, row hashes khớp,
schema definitions tương đương và primary unchanged. Chỉ xóa clone thuộc phép thử,
backup giữ lại. Source archive không chứa `.env`; khóa phục hồi giữ riêng theo
quy trình private. Sau đồng bộ tài liệu, tạo thêm checkpoint niêm phong và chạy
`check_s03_restore.py` trên manifest đó; exact manifest được cung cấp ở handoff,
không sửa báo cáo sau niêm phong chỉ để thêm tham chiếu tự trỏ vào snapshot.

Browser metadata cũ vẫn tìm `.st-model-grid`/placeholder/bấm Models và auto-save
model; không tương thích Cloud Settings mới. Harness cập nhật theo accessible
labels, consent metadata và explicit save, vẫn kiểm native429/usage3/active0,
reload và SME khác không có model/key. Không sửa frontend hoặc backend để né gate.
MCP có một lỗi route `/v1/model-providers` không phân loại ở lượt tích hợp đầu;
lượt focused và lượt tích hợp cuối không tái hiện. Chưa xác định root cause,
**không gọi đã sửa**; giữ như rủi ro ổn định harness cần theo dõi nếu tái hiện.
Harness bổ sung first-line diagnostic đã bỏ URL/UUID, giữ error gate nguyên vẹn;
không in headers/bearer hoặc toàn bộ Playwright call log.

## 4. Giới hạn và bước tiếp theo

Full backend có41cảnh báo ARQ deprecation đóng connection; frontend có warnings đã biết,
không đổi lint config để làm xanh. Kết quả provider thật, Meta OAuth/app review,
MCP server thật, global host fairness, remote CI/HTTPS/reboot/offsite DR/billing
vẫn là gates riêng. Không dùng local acceptance để gọi PAO production-ready.

Các gate local trên đã đạt; đồng bộ master/unified/S2 register/README/ADR/P6/P7.
Đúng một checkpoint kế tiếp: **S3.1 — Telegram connection identity và
explicit legacy mapping**; chưa tự migration hoặc nối bot thật trong lượt S2 này.
