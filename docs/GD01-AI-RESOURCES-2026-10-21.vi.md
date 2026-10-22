# GD01 — Tài nguyên AI chung, model và mức suy luận

Ngày: **21/10/2026**. Source: `F:\PAO-ACOS`.

## Kết luận và phạm vi

GD01 **đang triển khai, chưa đóng toàn giai đoạn**. Lõi API đã qua kiểm thử
offline và nghiệm thu Chat/agent bằng OpenAI thật trên dữ liệu tổng hợp/DB test.
Không suy từ đó ra ba CLI dùng chung, môi trường production hoặc hành động Ads thật.
Trạng thái tổng được ghi tại `.runtime/gd01-current-status.json` sau kiểm tra cài đặt.

Không thay `.env`, key đã lưu, quyền nghiệp vụ, schema0075 hoặc image/profile Codex.
Không cài candidate0076, sao chép credential của Javis, tự mua gói hoặc bật fallback trả phí.

## Các thay đổi của lượt này

| Khu vực | Đã thực hiện | Giới hạn |
| --- | --- | --- |
| Catalog tài nguyên chung | Thêm revision/hash/loại nguồn/thời điểm capture; tách bằng chứng chạy thành công của SME đang xem và hạn mức chưa biết | Capture cũ chưa có timestamp được giữ là chưa biết, không bịa hoặc sửa lịch sử |
| Anthropic API | Metadata mức suy luận cho exact-ID đã đối chiếu; gửi `output_config.effort`; thu input usage từ `message_start`, output từ `message_delta` | Không tự nhận mọi alias/model mới hỗ trợ; chưa có key để live test |
| Gemini API | Metadata exact-ID cho một số model text; gửi `generationConfig.thinkingConfig.thinkingLevel` | Không áp mức suy luận của text sang Live/Image/2.5 budget-based; chưa live test |
| Kết quả/usage Gemini | Loại phần `thought` khỏi câu trả lời và JSON; cộng token suy nghĩ vào token đầu ra khi nhà cung cấp báo hợp lệ | Không hiển thị private reasoning; token không phải tiền đã trừ hoặc quota còn lại |
| Bộ nhớ | Run API dùng tài nguyên chung mới ghim extraction vào chính nguồn/model/effort của run; recheck nguồn trước/sau I/O | Run lịch sử giữ nguyên local extraction; embedding vẫn là capability riêng; không đổi mặc định quyền riêng tư |
| Kế toán và hủy | Trace ghi provider/model/effort thực của adapter; extraction có context attempt và trạng thái cancelled, giải phóng lease | Không repin run cũ; không thêm job runner hoặc ledger thứ hai |
| Lỗi và chống gọi dồn | Phân biệt 401/403, 429, 5xx; dùng ledger hiện hữu để tạm ngừng sau ba lỗi tạm thời liên tiếp trong60giây | Phạm vi SME/model/revision; không global provider quota probe, retry tự động hoặc fallback |
| Giao diện | Thông báo lỗi tiếng Việt có cách xử lý; Settings phân biệt đã bật, bằng chứng cũ và hạn mức chưa xác minh | Nút kết nối/mô hình không phải giấy phép dùng công cụ hoặc kết luận live |

Các đường Chat/Studio/business job/schedule vẫn đi qua pin/resolver và native
AccountingEngine/Run đã có. Báo cáo số liệu và câu trả lời trích dẫn không gọi AI
không bị biến thành yêu cầu AI trả phí. Không xóa đường tương thích cá nhân/legacy
khi còn lịch sử; không tự chuyển tài khoản cá nhân thành tài nguyên chung.

## Nghiệm thu và lỗi đã giữ lại

- Backup trước thay đổi: `.runtime/checkpoints/p0-20261021T072849-04e1f803/manifest.json`.
  Source1624file; schema0075/161bảng/3archive. Phục hồi clone đối chiếu hash tất cả
  row và định nghĩa schema đạt, primary không đổi; clone riêng đã được dọn.
- Bản đích: `F:\PAO-BOS Backup 001\PAO-ACOS-Backups\20261021T073403Z-ed028f5689ac4379af57d68d41eaf574`.
  Source/dump/manifest kiểm hash, cấu hình PAO mã hóa DPAPI được giải mã thử trong RAM.
  Index dùng đường dẫn tương đối; manifest gốc giữ nguyên để đối chiếu, không dùng
  đường dẫn staging lịch sử như thể đã là nơi lưu mới. Không có token native CLI.
  Đây vẫn cùng ổ F và phụ thuộc tài khoản Windows, chưa phải offsite/portable DR.
- Kiểm thử trung gian456/456: `.runtime/gd01-tests-42877345ab7c4edaaa368ad2c72a555b/receipt.json`.
  Sau bổ sung circuit/cancel,48kiểm thử mới đạt trong
  `.runtime/gd01-tests-35d9ae3c39864d4b96a7de284e548734/receipt.json`.
  Các số này không cộng dồn thành một full regression hệ thống mới.
- Live cuối: `.runtime/gd01-tests-6e6e3cc32ebf4800bd8de89f61b116a4/receipt.json` và `live-summary.json`.
  Một native Chat `gpt-6.1-sol/low` (192input/9output) và một native Studio skill
  `gpt-6-luna/medium` (263input/45output), đúng source/model/effort ở attempt.
  Hai POST đến OpenAI thật,0tool; replay không phát sinh request. Hội thoại giữ
  model riêng khi agent dùng model khác. Không gửi dữ liệu doanh nghiệp chính.
- Hai lượt live trước **không đạt**, được giữ nguyên:
  `gd01-tests-bfd63b52d9924becae23a9aa36ab2540` thiếu consent cho reference tổng hợp;
  `gd01-tests-b4396d6faeb047ec8bf92d1481b382bc` bật planner làm hết trần hai request
  trước lượt agent. Đã sửa test consent và tách Chat trực tiếp khỏi planner,
  chạy chính kịch bản này offline đạt rồi mới chạy lại live; không nới gate production.
  Lượt cuối hai request không phải tuyên bố toàn bộ lượt làm việc chỉ dùng hai request.
- Frontend243Node/typegen/typecheck/build đạt:
  `.runtime/model-provider-tabs-frontend-73ea6be92d53470eb6c870662155a3e8/receipt.json`.
  Hồi quy cuối **469/469**,0fail/error/skip:
  `.runtime/gd01-tests-0686ee062d5842c7aed09abe9157a04a/receipt.json`.
  Installed GET-only/browser:
  `.runtime/gd01-installed-a8e21b340a654b43801d0cfd16c02d50/receipt.json`;
  hai SME,3HTTP replay,37GET UI,3Client/4API card, dark/light1440/390/320 đạt.
  Lượt browser trước `gd01-installed-4005de5c30b14bce82d7fb4792efcdc9` thất bại
  do test đếm card trước khi tải xong; đã thêm chờ card, giữ nguyên số lượng yêu cầu.
  API/ready/Web200,worker healthy sau restart; primary/hash/schema/.env/pin nguyên trạng.
  Binding hiện tại: `e2785c20cc61e2100c7a0f35dde4e34b8526963b20cdb666c42d1f220a87fbf2`.
  Đây là469test liên quan, không phải full regression toàn hệ thống2258 hoặc lớn hơn.

## Trạng thái từng nhà cung cấp và việc còn lại

| Nguồn | Bằng chứng hiện có | Còn thiếu |
| --- | --- | --- |
| OpenAI API | Key đã lưu được sử dụng thành công, Chat + Studio thật với hai model/effort | Không kết luận mọi139ID trong catalog đều là model chat; không biết quota/hóa đơn thực |
| OpenRouter | Cấu hình cũ471model; adapter/effort và đường chung được kiểm bằng fixture | Chưa gọi OpenRouter thật trong lượt này; không tự publish/đổi mặc định |
| Claude API | Effort/stream/JSON/usage qua transport giả lập | Cần key do người dùng nhập trong Settings nếu muốn live; chưa bắt buộc để dùng core |
| Google Gemini API | Effort/stream/JSON/usage qua transport giả lập | Cần key trong Settings nếu muốn live; tách biệt tài khoản Antigravity |
| Codex | Binary0.157.1, profile cũ và candidate native đa model/effort được giữ | Đường official plan usage/admission và promotion/release/rollback candidate vẫn chưa triển khai hoàn tất;0076 chưa được cài |
| Claude Code | Binary2.1.220 hiện diện | User đã hoãn vì chưa có gói; chưa nghiệm thu inference hoặc shared identity |
| Antigravity | Binary1.4.3; detection/catalog cũ được giữ | Consumer wrapper chưa được Google hỗ trợ, gate cô lập tools trước đây chưa đạt; không lặp smoke quota không đổi |
| Ollama/embedding | Provider local và lexical/degraded retrieval cũ được giữ | Không tuyên bố toàn bộ local dependency đã được loại bỏ; đường lịch sử còn dùng local |

**Chưa đóng GD01:** còn công việc phần mềm và điều kiện provider ở nhánh CLI,
catalog capability/modality toàn diện và rà soát migration/deprecation legacy.
Không gọi tất cả phần còn thiếu là "chỉ thiếu API key". Không tự chuyển sang GD02
như thể GD01 đã hoàn thành, hoặc bắt người dùng nhập lại key để chữa lỗi adapter.

## Hướng dẫn về khóa và tài khoản

Hiện **không cần nhập key mới** để dùng nguồn OpenAI API đã nghiệm thu. Nếu muốn
nghiệm thu Claude/Gemini, nhập khóa trực tiếp tại **Cài đặt và kết nối → AI và giọng
nói → Nhà cung cấp mô hình → Kết nối qua API → thẻ tương ứng**, lưu rồi đọc catalog.
Không gửi key/mật khẩu/token qua chat. Thuê bao ChatGPT/Claude/Google không mặc
nhiên là API credit. Codex/Claude Code dùng luồng đăng nhập chính thức tương ứng,
không phải yêu cầu "API key Codex". Đổi nguồn có thể đổi chi phí; PAO không tự đổi.

## Nguồn chính thức đã rà soát21/10/2026

- [OpenAI ChatGPT plan usage](https://developers.openai.com/siwc/token-sharing-open-source):
  đường app OSS/local có consent riêng; app trả phí/remote cần làm việc với chương trình.
  Đây không phải bằng chứng cho phép chia sẻ login cá nhân hoặc bán lại thuê bao.
- [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server):
  cấu hình Responses, app identity, token riêng của app và refresh; catalog không xác nhận entitlement.
- [Giới hạn preview](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations):
  route plan usage có hạn chế tham số/công cụ; không lấy hợp đồng API key hiện tại
  thay thẳng cho OAuth. Cần giải quyết giới hạn đầu ra/tool isolation trước promotion.
- [Claude auth](https://code.claude.com/docs/en/authentication),
  [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview),
  [Claude API effort](https://platform.claude.com/docs/en/build-with-claude/effort):
  API effort là `output_config.effort`, không phải thêm chữ High vào prompt.
- [Gemini Generate Content thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking):
  schema `thinkingConfig.thinkingLevel`, mức theo từng model; không bật `includeThoughts`.
- [Google Antigravity FAQ](https://www.antigravity.google/docs/faq/):
  headless cho scripting/CI không đồng nghĩa hỗ trợ wrapper ứng dụng bên thứ ba
  bằng consumer plan; Google nêu Gemini Enterprise/AI Studio như đường riêng.

OpenAI Docs skill được dùng để đối chiếu hợp đồng OpenAI và tách API key khỏi
plan usage, không dùng làm lý do bỏ qua nghiệp vụ hoặc giả báo CLI live.
