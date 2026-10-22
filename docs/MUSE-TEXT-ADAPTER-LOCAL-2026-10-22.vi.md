# Muse Code — adapter văn bản đã cài trên PAO local

Ngày 22/10/2026 · nguồn `F:\PAO-ACOS`.

Biên bản này cập nhật bước kết nối/auth ngày 21/10, không sửa bằng chứng lịch sử.
**Muse đã có adapter văn bản và đã chạy bằng thuê bao thật. Toàn GD01 vẫn chưa xong.**

**Cập nhật cùng ngày sau biên bản này:** đã nghiệm thu hai job nghiệp vụ phụ thuộc
qua ARQ/Muse thật trong pao_test. Xem [biên bản job](MUSE-BUSINESS-JOB-ACCEPTANCE-2026-10-22.vi.md).
Trạng thái job còn chờ bên dưới phản ánh mốc trước bài nghiệm thu mới, không còn
là việc chưa thực hiện cho vòng kỹ thuật local; Goal runner/Temporal vẫn chưa đạt.

## Kết quả theo phạm vi

| Phần | Kết quả xác minh |
|---|---|
| Đăng nhập Muse | Chủ sở hữu đã đăng nhập chính chủ vào profile PAO riêng; không sao chép token từ Muse cũ |
| Bản cài PAO | Đã khởi động API/Web/ARQ; API, readiness và Web HTTP200; schema0077/161 bảng, contract435 operations |
| Settings → Client | Bấm Kết nối Muse trong phiên chủ sở hữu; lưu revision2 và công bố vào registry AI bản cài hiện có |
| PAO AI | Nhận đủ 5 model có thể chọn; Spark1.3 có minimal/low/medium/high/xhigh/max; không thêm màn cấp grant nhân sự |
| AI mặc định | OpenAI mặc định bản cài và Codex đang chọn trong hội thoại được giữ nguyên; chọn thử trong popup rồi đóng, chưa bấm Áp dụng trên hội thoại của chủ |
| Chat và Studio Skill thật | Spark1.3/minimal và Spark1.2/low hoàn thành trong `pao_test`, chỉ dữ liệu tổng hợp; replay không gọi thêm model |
| Điều phối thật | Run tổng hợp hoàn thành qua planner + final Spark1.3/minimal; 0 tool và 0 specialist. Bài pytest gốc lỗi assertion của fixture, không coi là lượt pytest xanh |
| Agent/job routing | Đã nối lựa chọn Muse/model/effort vào resolver/Studio/business routing hiện có. Chưa nghiệm thu trọn job kinh doanh/Goal/Temporal bằng Muse thật |
| Hạn mức | Ghi actual token từ response native, quota còn lại chưa xác minh; không dự phòng sang API trả phí |
| Windows/Linux/production | Nghiệm thu local Windows theo phạm vi dưới đây; chưa Linux/VPS/public/pilot hoặc toàn GD01 |

## Danh mục thực tế

| Model | Các mức suy luận native | Mặc định |
|---|---|---|
| muse-wonder-1.0 | minimal, low, medium, high, xhigh, max | high |
| muse-spark-1.3 | minimal, low, medium, high, xhigh, max | high |
| muse-spark-1.3-contributor | minimal, low, medium, high, xhigh, max | max |
| muse-spark-1.2 | minimal, low, medium, high, xhigh | high |
| muse-spark-1.2-contributor | minimal, low, medium, high, xhigh | high |

Đọc từ `variants` của native, không hardcode danh sách giả. Năm lựa chọn catalog
không có nghĩa năm model đều đã chạy thật. Chưa thử hai Contributor; không tự đổi
lựa chọn riêng tư hoặc gửi dữ liệu doanh nghiệp để thử.

## Thiết kế và giới hạn cần biết

- Dùng binary Meta Muse Code `1.4.10-R6427.1`, SHA256
  `893a04138b81d844cc53e25216fafe0cbf7c786423534b93aacf1419a840f6b7`.
  Không cập nhật native, không nhập API key hoặc lấy token từ profile khác.
- Tài nguyên nằm trong InstallationAIResource/Revision hiện hữu. Chat/Studio
  tiếp tục dùng Run/LlmAttempt/ledger và dispatcher sẵn có; không tạo runner hay
  bảng quyền AI mới. Credential chung không trộn nội dung SME/Brain.
- Mỗi lần suy luận dùng HOME/data/workspace riêng trong profile PAO; chỉ cấu hình
  đăng nhập đã duyệt dùng chung. Phát hiện cấu hình/hook/MCP ngoài phạm vi thì từ
  chối, không tự xóa hoặc bỏ kiểm soát của profile cũ.
- `exec --preset empty` và cờ native tắt shell/write/web/reminder/input, một model
  step. Request thực tế không có tools được kiểm tra. Không có tạo ảnh/video,
  terminal tự do hoặc công cụ native được cấp ngầm.
- Child Windows được tạo suspended, gắn Job trước khi resume; đóng cả cây process
  và xác minh cleanup. Đây là containment vòng đời, **không phải sandbox filesystem/network**.
  Kiểm tra membership/nguồn/pin/cancel trước và sau, một dispatch trên attempt;
  mất ACK không tự gửi lại prompt hoặc chuyển model/API.
- Output Muse hiện được gom đến terminal rồi trả qua luồng PAO; **chưa streaming
  token-by-token native**. Đường SSE/replay hiện hữu không đồng nghĩa Muse đã stream từng token.
- JSONL1.4.10 không báo usage trực tiếp. Codec dùng transport trace của native
  trong RAM để đọc `response.completed.usage`, không lưu/ghi log raw prompt,
  suy luận riêng hoặc trace. Codec phụ thuộc version/SHA và bề mặt debug: native
  đổi định dạng cần kiểm tra lại, không coi là SDK ổn định.
- Hướng dẫn native có overhead khoảng14.000 token input ngay cả prompt ngắn.
  Ledger dự phòng16.000 token cho phần này; đây là **ước lượng dự phòng**, khác
  số token provider thực báo. Khi Áp dụng Muse trên Chat, UI công khai việc đặt
  ngữ cảnh ít nhất32.768 và ngân sách lượt chạy ít nhất65.536; không đổi quyền
  riêng tư/công cụ hay hội thoại khác. Job phải có ngân sách được duyệt ít nhất
 32.768 trong phiên bản mới; mặc định cũ4096 không tự tăng hoặc repin.
- Native request quan sát có `max_output_tokens=128000`; bản CLI này chưa có cờ
  được tích hợp để áp hard output cap của PAO tại provider. PAO có deadline120s,
  giới hạn wire/output và từ chối kết quả vượt ngân sách, nhưng **không hoàn lại
  quota đã tiêu và không bảo đảm hard token cap upstream**. Cần tối ưu trước
  khi dùng hàng loạt hoặc dữ liệu kinh doanh thật.

## Bằng chứng nghiệm thu

Các đường dẫn dưới đây tương đối với `F:\PAO-ACOS`.

| Kiểm tra | Bằng chứng |
|---|---|
| Backend có phạm vi | `.runtime/gd01-tests-d3229b4ac3004db88e7c0333b0eecb05/receipt.json`: 543 pass, 0 fail/error/skip; source/env/pin/schema/dữ liệu chính giữ nguyên. Không phải toàn bộ2258 regression mới |
| Unit native/profile/containment | `scripts/test_muse_execution.py`:9 pass; `scripts/test_muse_client.py`:22 pass; chạy lại sau cài, không gọi provider |
| Frontend | `.runtime/model-provider-tabs-frontend-97aa76bc847b4643a155911fa9936835/receipt.json`:257Node/typegen/typecheck/production build đạt |
| Browser fixture Chat | `.runtime/chat-controls-browser-1792638993741/receipt.json`: model/effort/context disclosure, bàn phím, dark/light320–1600; không backend/provider thật |
| Browser fixture Settings | `.runtime/model-provider-tabs-browser-1792639080228/receipt.json`: auth/cancel/lostACK/role, dark/light1440/390/320; không gọi provider thật |
| Chat + Skill quota thật | `.runtime/gd01-tests-6dc6ace90d6a442abcdd07218b8c6459/live-summary.json`:2 native call completed, usage reported, cleanup verified, replay0call, không tool/API fallback |
| Planner/final đối chiếu chỉ đọc | `.runtime/muse-orchestrator-review-af7a785310d14c9cbca373d563c24ae9/receipt.json`:2 attempt completed, đúng marker, Chief of Staff step0,0specialist/tool; không gửi thêm prompt |
| Bản cài sau kết nối | `.runtime/gd01-installed-2cf6974d1d9d4d879d019fd76bb071f0/receipt.json`:2SME cùng thấy5model Muse selectable,6Codex,3replay; contract khớp, HTTP200,0mutation/provider, dữ liệu chính không đổi trong lượt GET |
| UI Chrome của chủ | `.runtime/muse-installed-20261022/model-picker.png`:5model Muse xuất hiện thật; đóng popup giữ Codex hiện tại |

Token thật trong các bài nghiệm thu (không phải quota còn lại):

| Luồng | Model/effort | Input | Output |
|---|---|---:|---:|
| chat_final cách ly | Spark1.3/minimal | 14153 | 25 |
| studio_skill cách ly | Spark1.2/low | 14232 | 233 |
| chat_planner | Spark1.3/minimal | 14636 | 164 |
| chat_final sau planner | Spark1.3/minimal | 14164 | 32 |

### Giữ nguyên lịch sử lỗi

- `.runtime/gd01-tests-9e2862914820468b94d63a99f4d0774b/receipt.json` vẫn failed:
  assertion cũ đòi0AgentRun trong khi core luôn ghi Chief of Staff. Run thực tế đã
  completed. `provider_calls:0` trong receipt cũ là **lỗi thu thập bằng chứng**:
  assertion xảy ra trước khi gom usage; đối chiếu DB chứng minh2call đã xảy ra.
  Không viết lại receipt; helper mới ghi số dispatch yêu cầu trước khi gửi và
  dùng unknown khi thiếu bằng chứng. Đã sửa fixture đúng0specialist, không bỏ guard.
  Review chỉ SELECT không chứng minh nhánh replay cuối của bài pytest lỗi đã chạy.
- Giữ các lượt failed fixture `983c905a31cd466a8ea0845bbc284947`,
  `81efa9d3d6f543beb135c31d53130bfb`, và lỗi browser sai URL
  `model-provider-tabs-browser-1792639004888`; không ghép chúng thành một pipeline xanh.
- Lượt installed trước bổ sung assert Muse có nhãn hardcoded `muse_metadata_only`;
  receipt mới dùng `muse_metadata_reads_only` và kiểm model selectable thực tế,
  không sửa bằng chứng cũ.

## Backup, vận hành và việc tiếp theo

Backup trước adapter đã xác minh tại
`F:\PAO-BOS Backup 001\PAO-ACOS-Backups\20261021T144832Z-3ef0cedaa78e42508733b3d6a4d33e5f`;
manifest `.runtime/checkpoints/p0-20261021T144819-cf30d9a4/manifest.json`.
Không ghi đè backup cũ, không sao chép profile/token Muse. Bản này không phải
backup sau adapter, offsite hoặc bằng chứng phục hồi đăng nhập Muse trên máy mới.

Bản API/Web trước kiểm tra đã dừng; khởi động bằng launcher hiện hữu và xác minh
lại health/worker/contract/replay. Không sửa `.env`, migrate DB, reset Docker,
restore dữ liệu chính, commit/push hoặc deploy.
Thao tác Connect chủ động đã thêm/cập nhật cấu hình AI bản cài; không gọi đó là
toàn lượt chỉ đọc hoặc dữ liệu chính không thay đổi từ trước khi Connect.

Tiếp theo: nghiệm thu job nghiệp vụ Muse nhỏ có ngân sách mới được duyệt; tối ưu
overhead và kiểm chứng cancel/recovery dài hạn. Claude thuê bao đã hoãn,
Antigravity inference/shared Codex và các gate nhà cung cấp vẫn theo roadmap,
không được coi hoàn tất từ riêng tích hợp Muse này.

Tài liệu nhà cung cấp đã đối chiếu trong lượt triển khai21–22/10:
[Auth](https://dev.meta.ai/docs/muse-code/auth),
[Permissions](https://dev.meta.ai/docs/muse-code/permissions),
[Configuration](https://dev.meta.ai/docs/muse-code/configuration),
[Subscriptions](https://dev.meta.ai/docs/muse-code/subscriptions).
