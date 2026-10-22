# Đợt cơ cấu AI dùng chung, đa model, mức suy luận và giao diện chat

Ngày20/10/2026. Người dùng đã duyệt triển khai toàn bộ yêu cầu trong cuộc trao
đổi; không chỉ di chuyển giao diện hoặc ẩn các quyền cũ.

## Phạm vi đã duyệt

1. CLI/API là tài nguyên của một bản cài PAO. Quản trị bản cài kết nối một lần;
   người dùng PAO hợp lệ sử dụng theo vai trò ứng dụng, không tự cấu hình grant,
   hồ sơ AI cá nhân hoặc thời hạn. Dữ liệu SME/Brain và quyền công cụ vẫn tách.
2. Tách kết nối/xác thực khỏi danh mục và lựa chọn model. Đọc danh mục thật,
   không bịa ID; hỗ trợ nhiều model trên cùng kết nối. Danh mục không chứng
   minh entitlement/quota hoặc nghiệm thu model thật.
3. Mức suy luận lấy theo khả năng từng model. Lưu và truyền tới backend/CLI/API
   khi thực thi; không chỉ thêm nhãn High trên UI. Không tự chuyển API tính phí.
4. Chat chọn model cho PAO điều phối. Agent và từng bước/tác vụ có lựa chọn
   riêng hoặc kế thừa. Ghim lựa chọn trên mỗi lần chạy; không sửa lịch sử hoặc
   repin công việc cũ khi đổi mặc định. Tái sử dụng engine/accounting/runner.
5. Đưa bộ chọn model lên đầu chat; quyền riêng tư/quản lý/thống kê hội thoại
   lên góc trên phải của trang. Cả sáng/tối, desktop/tablet/mobile, bàn phím.

## Thứ tự thực hiện và tiêu chí

- RAI1: checkpoint nguồn; hoàn thiện di chuyển điều khiển chat và nghiệm thu
  bố cục/popover/keyboard/API handler hiện có trước khi mở rộng backend.
- RAI2: schema và authority cho tài nguyên bản cài, quyền quản trị bản cài
  khác owner của một SME; không cho SME khác sửa khóa dùng chung. Không tự
  lấy credential từ ứng dụng ngoài hoặc ngầm công bố hồ sơ cá nhân cũ.
- RAI3: catalog có tên hiển thị, khả năng/mức suy luận và nguồn kết nối. Refresh
  metadata có chủ ý, không gọi inference khi mở trang; xử lý tài khoản đổi/
  model mất quyền mà không fallback tính phí hoặc hardcode một model.
- RAI4: truyền model/effort vào engine pin, runtime, usage, agent/step/job và
  kiểm thu hồi/SME/Brain/role. Cập nhật runtime pin/image có kiểm thử nếu cần.
- RAI5: Settings gọn3Client/nhà cung cấp API; loại bỏ wizard/grant cá nhân
  khỏi luồng mới. Giữ khả năng đọc lịch sử và đường lui, không xóa dữ liệu cũ.
- RAI6: migration/restore disposable, regression, build, browser, cài đặt có
  checkpoint và kiểm health/contract/replay. Live từng provider phải ghi riêng.

## Trạng thái hiện tại

Tiếp nối: đã cài [OpenAI effort](OPENAI-EFFORT-2026-10-20.vi.md) theo3exact-ID,
bindingf596abc4/schema0075/API429. Catalog/model/effort qua native accounting
và UI đã có bằng chứng; không live provider, không toàn đợt. Các mốc7ccc bên
dưới giữ như lịch sử.325test chức năng đạt nhưng aggregate primary-isolation
FAIL do hoạt động đồng thời; bằng chứng cài/GET-only riêng đạt, không viết lại fail.

**In progress, chưa hoàn tất toàn đợt.** Đã cài UI mới và nền tảng tài nguyên
API dùng chung trên schema0075,161bảng/API429. RAI1 đạt local; RAI2/API và
phần API của RAI3–RAI5 đã có code và kiểm thử local. RAI6 đạt các kiểm tra
cài đặt giới hạn bên dưới, không phải nghiệm thu toàn bộ CLI hoặc production.

Không di chuyển/copy credential. Chưa dùng chung hồ sơ CLI đang có. Runtime
Codex ứng viên chưa thay bản đang phục vụ. Không lấy108/212 của smoke trước
hoặc2258 của CI lịch sử làm bằng chứng cho source mới.

Checkpoint nguồn trước sửa:
`.runtime/p84-foundation-fd499ffcab8542fdb73690ca5da3d925/source-baseline.zip`.

Antigravity hiện còn chốt native init60tools trước prompt; Claude chưa có
thuê bao để nghiệm thu. Tài liệu nhà cung cấp và khả năng dùng chung phải
được đối chiếu theo đúng phương án triển khai; việc khách hàng duyệt UX không
biến phiên cá nhân thành danh tính tổ chức được nhà cung cấp hỗ trợ.
Chốt bên ngoài phải ghi pending, không bỏ assertion hoặc relabel local pass.

## Đã cài và kiểm chứng

- Model ở đầu/phải khung chat; hội thoại/quyền riêng tư/thống kê ở đầu/phải
  tiêu đề trang, không còn hai hàng cũ chen vào ô nhập. Popover ở top layer,
  không bị khung chat cắt; Escape/Enter/đóng và trả focus; mở không đẩy tin nhắn.
- Bỏ PersonalCodexSettings, danh sách hồ sơ và grant wizard khỏi màn hình
  Client. Tab AI mặc định dùng cấu hình tài nguyên bản cài, không còn wizard
  API cá nhân. Giữ các API/policy cũ để đọc lịch sử và tương thích, không xóa.
- API provider vẫn4ô, có trạng thái khóa đã lưu/đã nhập/chưa lưu, Lưu/Xóa;
  không trả secret về UI, không lưu khóa chưa lưu vào browser storage.
- Registry tài nguyên bản cài tham chiếu kết nối mã hóa gốc. Chỉ quản trị
  bản cài được công bố/đổi mặc định; owner một SME không tự có quyền này.
  Bản local đã provision quản trị bằng owner hiện tại được xác minh, không
  tạo grant AI cho nhân sự. Chỉ thêm INSTALLATION_AI_ENABLED và danh sách
  quản trị; nội dung cấu hình cũ còn nguyên sau chuẩn hóa xuống dòng.
- Thành viên được dùng API chung theo quyền ứng dụng; dữ liệu/Brain/brand,
  token/usage/lease vẫn theo SME và người gọi. Viewer chỉ có chat chỉ đọc;
  không phát sinh quyền sửa công việc hoặc công cụ. Recheck membership,
  auth version, quản trị bản cài, quyền của người giữ kết nối gốc, credential
  và revision trước thực thi/trả kết quả. Thu hồi không làm sống lại grant cũ.
- Danh mục API gồm nhiều ID thật đã đọc qua đường metadata có admission;
  mở Settings/đọc registry không gọi inference. Refresh không tự bật resource.
  Codex catalog có phân trang tối đa500 và metadata effort từ model/list;
  popup kết nối có nút Đọc danh mục, không đổi model toàn hồ sơ khi đọc.
- Agent có bộ chọn model riêng/kế thừa; định nghĩa mới vẫn phải validate/
  review/publish. Routing SME/brand/agent/step/job tái dùng runner S5. Agent
  specialist không ghi đè model điều phối trong hội thoại. Lựa chọn và effort
  được chốt vào engine snapshot; không sửa run cũ hoặc tự fallback.
- Mốc đầu: explicit effort chỉ được truyền qua OpenRouter khi metadata
  model công bố supported_efforts/default_effort. OpenAI/Anthropic/Gemini
  lúc đó dùng mặc định khi chưa có adapter capability đã đối chiếu/nghiệm thu;
  không giả hiện High hoạt động cho mọi model. ID model vẫn đọc động.

## Bằng chứng local mới

1. Backend:278passed/0failed/0error/0skip; gồm native Run/Accounting với
   provider giả lập, multi-SME, agent model khác orchestrator, privacy deny,
   thu hồi caller/custodian và tương thích engine/enterprise/business/Codex cũ.
   `.runtime/installation-ai-tests-3b3922c00482439abc1c24790b459c32/receipt.json`.
   Đây là hồi quy tập trung mở rộng, không phải full backend regression mới.
2. Migration0074→0075→0074→0075 trên clone phục hồi: bảng cũ và3archive
   không đổi; chỉ xóa clone tự tạo, giữ dump. Không restore primary.
   `.runtime/installation-ai-migration-0a58453fb696403e877e0b8c8c231b48/receipt.json`.
3. Chat browser fixture: dark/light1600/1024/768/390/320, bàn phím, hình học
   message giữ nguyên, chọn resource+model+High gửi đúng body. Legacy chooser
   cũng được kiểm tra riêng. Không forward backend/provider.
   `.runtime/chat-controls-browser-1792502142390/receipt.json` và
   `.runtime/chat-controls-browser-1792501590093/receipt.json`.
4. Settings fixture:3Client/4API, Lưu/Xóa, masked state, nhiều bản nháp,
   lost ACK không tự retry, mặc định resource, viewer, phạm vi/late response,
   dark/light1440/390/320.
   `.runtime/model-provider-tabs-browser-1792502127506/receipt.json`.
5. Codex binary0.157.1 trong container network-none/nonroot/readonly, không
   auth mount: default, tool injection, High/Low tới Responses giả lập đạt.
   `.runtime/installation-codex-protocol-48712ef3156140d894532ca0ed684b43/receipt.json`;
   image nguồn overlay tại
   `.runtime/p84-codex-image-542ef8046f154b6ab381eb9c54b2f4a2/image.json`.
   Đây không phải quota/model thật hoặc PAO chat acceptance của runtime mới.
6. Cài đặt: checkpoint mới
   `.runtime/checkpoints/p0-20261020T132233-b4755cb9/manifest.json`;
   chỉ dừng API/worker đã kiểm executable/start-time/command và idle, migration
   giữ hash bảng cũ/3archive; Web/Docker/CLI registry không thay.
   `.runtime/installation-ai-install-99f9d9b70f7a4144adc503bbffcaf8b5/receipt.json`.
7. Installed GET-only/browser: API/ready/Web200, worker khỏe; source/live
   contract429 khớp; schema0075/161bảng; replayHTTP3/3, không chạy lại tool.
   UI thật GET-only, không Connect/Test/Save;3Client/4API, dark/light320–1600.
   Hash dữ liệu chính không đổi trong lượt kiểm tra, pin Codex vẫn hợp lệ.
   `.runtime/installation-ai-live-c93216998e434d7993eb5536c5f10052/receipt.json`.
   Diagnostic bearer không phải đăng nhập/đồng ý hay owner pilot.
8. Agent UI fixture: chọn model riêng+High gửi đúng payload; chuyển Kế thừa
   lưu phiên bản mới, giữ nguyên phiên bản đầu; dark/light1600/390/320.
   `.runtime/agent-model-browser-1792503782280/receipt.json`.

Frontend213Node/typegen/typecheck/build23 đã qua trên source mới/contract429;
kiểm tra cuối tại
`.runtime/model-provider-tabs-frontend-96a1201f4b994108a4ad23cb17ece300/receipt.json`.
Luồng vận hành cũng đưa grant cũ vào phần nâng cao, không buộc chọn grant
AI cá nhân khi chạy bằng tài nguyên chung. Không có runner mới.

Các failure trước đó được giữ: fixture assertion nhầm source_id với
installation_resource_id; helper trỏ nhầm tên test; test agent chưa bật cloud
bị chặn đúng privacy; nhãn truy cập select thiếu aria-label. Không bỏ privacy,
auth assertion, không restore dữ liệu để làm xanh test.

## Chưa hoàn tất — không được coi là dùng chung ba Client

- Codex: danh mục/effort reader và runtime ứng viên đã chuẩn bị. Chưa chuyển
  registry/profile pin và dispatch guard trên bản cài chính, chưa nghiệm thu
  quota thật cho đường mới. Candidate cách ly đã nối model/effort qua snapshot/
  agent/native accounting/dispatch và qua220tests cùng6ca binary offline;
  đây không phải adapter shared đã cài. Hồ sơ cá nhân đang chạy giữ nguyên.
  Cần giải quyết danh tính triển khai được nhà cung cấp hỗ trợ trước khi
  hoàn thiện/admit adapter chung. Không tự chuyển gói hoặc API tính phí.
- Claude Code: user đã hoãn do chưa có Pro/Max; adapter/live acceptance
  chưa hoàn tất, UI ghi rõ chưa hỗ trợ. Không coi card là đã tích hợp.
- Antigravity: đọc được catalog không gỡ chốt tools60. Chưa gửi prompt cho
  đường mới hoặc nối inference/usage/cancel vào runner. Không tắt assertion,
  lấy OAuth token, dùng ADC hoặc API billing làm lối vòng.
- OpenAI đã có adapter/capability3exact-ID theo báo cáo tiếp nối. Gemini và
  Anthropic còn cần adapter riêng trước khi mở explicit effort. Chưa dùng
  API/model thật trong đợt này.
- Chưa owner pilot, Ads/action, SaaS/commercial acceptance, full regression
  mới hoặc VPS/public. Toàn đợt RAI vẫn in_progress; đây không phải hết roadmap.

Runtime candidate được giữ dưới
`packages/cli-runtime/candidates/installation-ai/`; chỉ overlay khi build rõ
--runtime-candidate. Không import vào backend đang chạy. Không thêm runner.

## Nguồn đã đối chiếu cho thiết kế

[Codex App Server](https://learn.chatgpt.com/docs/app-server#list-models-modellist):
`model/list`, supportedReasoningEfforts/defaultReasoningEffort/inputModalities;
lựa chọn theo dữ liệu trả về, không cố định tên/mức trong ảnh chụp.

## Tiếp nối20/10 — candidate backend đã có bằng chứng riêng

Xem [báo cáo candidate Codex](CLI-MULTIMODEL-CANDIDATE-2026-10-20.vi.md) cho
220tests/clone roundtrip/6ca binary, phục hồi dịch vụ và trạng thái GET-only.
Chốt danh tính thật vẫn đóng; release pin và live quota/owner acceptance chưa
xong. Không cộng220vào278hoặc gọi đây là full regression/whole phase pass.
