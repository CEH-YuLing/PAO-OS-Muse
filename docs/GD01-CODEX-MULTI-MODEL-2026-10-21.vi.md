# GD01 — Codex nhiều model, 21/10/2026

Nguồn `F:\PAO-ACOS`. Đây là nghiệm thu danh mục/chọn model native cá nhân có phạm
vi, không phải toàn GD01, shared CLI hoặc mọi nhà cung cấp.

## Cách dùng và bản sửa

PAO AI → Chọn mô hình → Client → Codex → **Cập nhật danh mục Codex** → chọn model
→ **Áp dụng mô hình**. Chỉ đổi hội thoại hiện tại, không đổi default/hồ sơ hoặc
các hội thoại khác. Không thêm màn cấp grant nhân sự hoặc yêu cầu API key.

Client 0.157.1 hiện trả sáu model: `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`,
`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`. Danh mục lấy động, không hardcode;
không tự thêm 6.1-sol khi client chưa trả về. model/list có thể bundled/cached,
không chứng minh quyền suy luận/quota. Chưa thử suy luận thật cả sáu model.

Trước đây API/dispatch guard chỉ nhận model default của hồ sơ. Bản sửa lưu danh
mục trong PersonalCliRevision sẵn có, tách metadata khỏi policy; run chốt catalog
record/hash và source/version/profile/auth pin. Kiểm tra lại lúc thực thi; model
giả, nguồn khác, hash/pin sai bị từ chối. Không thêm bảng hoặc runner. Catalog
refresh giữ popup/draft cùng scope; đổi SME/session vẫn xóa trạng thái riêng.

Migration0077 thay guard để nhận lựa chọn hợp lệ, down_revision0075; candidate0076
không cài. Startup/restart pin0077, không tự migration. Native Docker runtime/image,
credential và .env không đổi. Adapter hiện nhận model/prompt, chưa nhận effort
override: UI hiển thị mặc định, không giả vờ truyền High/Max; API effort giữ nguyên.

## Kiểm chứng

| Phạm vi | Kết quả / receipt trong .runtime |
| --- | --- |
| Backend GD01 liên quan | 499 đạt, 0 fail/error/skip; gd01-tests-f4f91219bccd414887632a627a9dfb52/receipt.json |
| Frontend | 250 Node/typegen/typecheck/build; model-provider-tabs-frontend-57b2c7a20a654ac1937d7c7de1ad6e5e/receipt.json |
| Browser fixture | Connect/lost ACK/default/scope/mobile; model-provider-tabs-browser-1792573084054/receipt.json |
| Popup/model refresh | chat-controls-browser-1792573487757/receipt.json |
| Installed GET-only | 6model/2SME/3replay/light-dark/mobile; gd01-installed-e390b1fa099d46d1a2592522104f888b/receipt.json |
| Migration clone | 0075→0077→0075→0077, hash/archive giữ nguyên; codex-models-migration-a05a1e71ca904387a658b64ad48cafe5/receipt.json |
| Primary rollout | checkpoint trước, row nghiệp vụ giữ nguyên; codex-models-install-d5552dd8ab614cb9b983e201c7846f0a/receipt.json |

API/ready/Web200, worker khỏe, source/live/stored contract khớp. Schema0077,
161bảng/429operations, binding916039de38dccec97a878d925f8a384e635448ef67afee0e94a8ff742e3faadf.
Đây không phải lượt full-system2258 mới.

## Lỗi thật đã gặp và phần còn thiếu

Qua phiên UI thật, run875ee2f3-c3ee-45b1-ade5-b26f697a2837 dispatch đúng gpt-6-luna
nhưng thất bại cli_plan_invalid. Input tổng hợp, không tool/dữ liệu doanh nghiệp.
Đã sửa prompt planning và JSON parser: nhận raw JSON hoặc một JSON code fence;
vẫn từ chối duplicate key/text thừa/plan sai schema. Bảy test mới nằm trong499test
đạt; bản sửa đã nạp API/worker. Không fail-open hoặc fallback sang API.

**Chưa nghiệm thu lại bằng quota thật sau sửa**: phiên PAO hết hạn; lượt tiếp tục
Chrome báo Debugger unattached. Không mượn token hoặc tạo phiên ghi thay người dùng.
Không coi danh mục là quota/chi phí thực. Giữ lỗi cũ và mọi receipt thất bại trước
sửa fixture/guard/popup. Claude adapter, Antigravity inference, Muse, shared CLI,
native effort override còn thiếu. Toàn GD01 in_progress; GD02/production=false.

## Cập nhật nghiệm thu thật — 19:55 ngày 21/10/2026

Sau khi người dùng đăng nhập lại, đã thử hai lượt qua UI trong hội thoại kiểm thử
riêng, dùng input tổng hợp, bộ nhớ/tri thức tắt. Đã đối chiếu SELECT-only backend:

| Model | Run | Kết quả | Thời gian backend |
| --- | --- | --- | --- |
| `gpt-6-luna` | `b4daf0fc-d36b-48f8-a56a-a90863a37e9a` | Đúng `PAO_CODEX_LUNA_OK` | 27,67 giây |
| `gpt-5.6-luna` | `5f879394-6faf-4a33-902b-a017b59635dc` | Đúng `PAO_CODEX_56_LUNA_OK` | 24,77 giây |

Cả bốn attempt (planner/final) completed, đúng `codex_cli` và model đã chọn;
bốn dispatch completed, 0 tool, 0 specialist, không fallback API. Default hồ sơ
vẫn `gpt-6-astra`, source version10. API/ready/Web200, schema/binding không đổi.
Receipt `.runtime/gd01-codex-live-db28a6f0b08e418091740033e60543ff/receipt.json`.

Lỗi planner trước sửa vẫn được giữ; gate hết phiên/Chrome của lượt trước đã được
giải quyết cho hai bài thử này. Probe đối chiếu đầu tiên dùng service có row lock
trong transaction read-only nên bị PostgreSQL từ chối; giữ receipt thất bại
`gd01-codex-live-d61c74081b34492a8216187535d95598`. Probe sau dùng SELECT trực tiếp,
giữ read-only, không sửa auth/service/database để vượt lỗi chẩn đoán.

Không chạy lại regression499/250 vì không đổi code. Dữ liệu hội thoại kiểm thử được
tạo có chủ đích, không tuyên bố primary hoàn toàn không đổi trong lượt UI này.
Người dùng đồng thời chuyển tab sang Settings sau khi hai phản hồi đã quan sát;
ảnh Settings lưu riêng, không dùng làm bằng chứng nội dung phản hồi. Không sao
chép phiên/credential sang tab khác. Chỉ hai model này được nghiệm thu suy luận mới;
không chứng minh quota còn lại, cả sáu model, shared CLI hoặc toàn GD01.

## Backup

Trước migration: checkpoint .runtime/checkpoints/p0-20261021T090450-ca24f7ad/manifest.json;
bản xuất F:\PAO-BOS Backup 001\PAO-ACOS-Backups\20261021T091238Z-63a4b6b661ab473b8511bdece171bcd0.
Đó là bản trước sửa planner, không phải source cuối. Sau tài liệu này, checkpoint
→ restore clone riêng → export vào thư mục mới; kết quả/đường dẫn cuối ghi tại
.runtime/gd01-current-status.json mục codex_models. Không ghi đè backup/restore
primary/chép credential store CLI. Same-drive/DPAPI không phải offsite/portableDR.
Không commit/push/deploy hoặc bật Ads.

Nguồn chính thức đối chiếu21/10/2026:
[App-server](https://learn.chatgpt.com/docs/app-server),
[Models/inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference).
