# PAO — Master Gap & Roadmap: Business OS và trợ lý tri thức

## Cập nhật21/10 — đã mở8công tắc nội bộ cho phát triển local

Theo xác nhận của người dùng, đã bật kết quả trong ứng dụng, learning có duyệt,
outcome observations, sự kiện/receipt nội bộ, phê duyệt tập trung, tiếp nhận
mục tiêu và quản lý lịch. Không có công tắc bỏ bảo mật hoặc auto-approve.
Chat/Brain/Knowledge/Studio/lập kế hoạch đã bật từ trước, không tính là mới.

148test chức năng20/10 đạt,9operator guard riêng đạt; installed GET21/10
trên2SME/1Brain đạt. API/ready/Web200, worker khỏe, schema0075/161bảng,
OpenAPI429/bindingf596abc4 giữ nguyên. Không đổi code backend/UI, credential,
schema hoặc provider activation; không có full regression/build UI mới.

Giữ các receipt lỗi do cache Next và bộ đọc UTF-8 của nghiệm thu. Sáu bảng
cấu hình/kết nối đã thay trong thời gian gián đoạn được bảo toàn; không gọi
toàn lượt là primary unchanged. Chỉ cửa sổ nghiệm thu GET mới giữ hash tất cả
bảng. Đã khởi động lại local; không có thử reboot/production acceptance.

Goal admission/schedule manager vẫn ghi đúng dry-run/quản lý, chưa phải AI
autonomous execution. Antigravity isolation/shared CLI, Claude thuê bao,
connector thật và hành động bên ngoài còn các chốt riêng; không xóa điều kiện
để che phần chưa triển khai. Toàn RAI/S6/production không được đánh dấu xong.
Xem [báo cáo mở chức năng local](LOCAL-FEATURE-ACTIVATION-2026-10-20.vi.md).

## Cập nhật20/10 — thử lại Antigravity: chưa đạt quota thật

Theo yêu cầu kết nối và chạy quota thật, đã gọi lại native catalog (6 model)
và smoke hiện hành: chặn `tools_not_disabled` trước prompt. Probe thêm 3 cách
nhận diện thư mục dự án đều còn60tool; đã dừng riêng các tiến trình, không
nới chốt hoặc sửa global settings. Không có câu trả lời/usage thật và không
bật Antigravity cho chat/job. FAQ Google hiện không hỗ trợ consumer CLI wrapper
trong ứng dụng bên thứ ba; đây là chốt riêng với chốt cách ly kỹ thuật.

PAO vẫn0075/161bảng/API429/bindingf596abc4, API/ready/Web200,
installed GET-only/replay3/3/pin đạt. Không sửa ứng dụng/env/DB hoặc restart.
Chi tiết, receipt mới và việc còn thiếu tại
[kiểm tra lại Antigravity](ANTIGRAVITY-QUOTA-RECHECK-2026-10-20.vi.md).
Đây không phải nghiệm thu provider hoặc hoàn tất toàn đợt.

## Cập nhật20/10 tiếp — đã cài mức suy luận OpenAI API theo model

Đã hoàn thiện/cài adapter OpenAI API: catalog động, bảng capability exact-ID
đã đối chiếu cho gpt-6.1-sol/gpt-6-astra/gpt-6-luna, effort theo model, truyền
`reasoning_effort` thật trong stream/JSON, giữ giới hạn token, tách model agent
và orchestrator, không grant cá nhân/native tools/fallback trả phí.

**Hiện tại0075/161bảng/API429, bindingf596abc4**; env/khóa/CLI pins giữ nguyên.
325test chức năng và37focused đạt nhưng hai aggregate receipt giữ FAIL vì
hoạt động đồng thời làm thay phiên/metadata lease; không gọi325là all-green
isolation. Audit, checkpoint mới và bằng chứng cài đặt riêng giữ nguyên toàn
bảng sau dừng/restart; installed GET-only/contract/replay3/3/pin đạt. UI OpenAI
fixture sáng/tối320–1600đạt; không có build/full regression mới hoặc provider thật.

Codex shared/live/pin, Claude CLI, Antigravity isolation, effort Gemini/Anthropic
và các gate thương mại/production vẫn chưa xong. Toàn RAI tiếp tục in_progress.
Xem [báo cáo OpenAI effort](OPENAI-EFFORT-2026-10-20.vi.md), gồm cách sử dụng,
nguồn tài liệu và failure/drift; không lặp phần Codex đã nghiệm thu offline.

## Cập nhật20/10 tiếp — candidate Codex đa model/effort đã qua kiểm thử, chưa cài shared

Đã nối selection/API cấu hình → snapshot/agent override → native accounting/
dispatch → tham số model/effort trong bản nguồn cách ly;220backend tập trung
đạt,0failure/error/skip. Candidate0076 thử lên/xuống trên database riêng và
clone backup, giữ hash hàng cũ/3archive. Binary Codex thật qua6ca offline,
gồm2model tổng hợp và High/Low; không auth mount/provider/quota thật.

**PAO chính vẫn0075/161bảng/API429 và binding7ccc7455**, không chuyển runtime/
profile pin, không kích hoạt CLI chung. Chốt danh tính dùng chung còn đóng;
sau khi có phương án được hỗ trợ vẫn cần triển khai/nghiệm thu bước release
pin và model thật, không sửa lịch sử hay tự đổi gói/API billing. Claude tiếp
tục hoãn; Antigravity tools60 chưa được gỡ. API effort ngoài OpenRouter còn
chưa nghiệm thu. Toàn đợt vẫn `in_progress`, không commercial/production pass.

Đã phục hồi API/worker thoát do window-CLOSE bằng startup ẩn sau preflight;
API/ready/Web200, worker khỏe, contract429/replay3/3/pin/dữ liệu chính đạt
GET-only. Không sửa Docker hoặc schema chính. Chi tiết và việc còn lại:
[nghiệm thu candidate Codex](CLI-MULTIMODEL-CANDIDATE-2026-10-20.vi.md).
Không lặp baseline hoặc xây thêm runner trong lúc chốt danh tính còn thiếu.

## Cập nhật20/10 — UI chat mới và nền tảng tài nguyên AI bản cài; toàn đợt chưa xong

Theo yêu cầu mới, ưu tiên cơ cấu AI dùng chung, đa model/effort và UI chat,
không tiếp tục wizard grant AI cá nhân. Đã cài0075/161bảng/API429: model ở
đầu chat, quyền riêng tư/thống kê ở đầu trang;3Client/4API, bỏ khối thiết lập
Codex cá nhân/hồ sơ/grant khỏi UI thường. Registry API chung vẫn tách dữ
liệu/Brain/usage SME/người gọi và quyền công cụ, quản trị bản cài khác SME owner.
Agent/step/job có lựa chọn API riêng/kế thừa, ghim run, không đổi lịch sử.

278backend tập trung mở rộng/0fail/error/skip; migration roundtrip trên clone
giữ bảng cũ và3archive; browser fixture sáng/tối desktop/tablet/mobile và
installed GET-only đạt, API/ready/Web200, worker khỏe, replay3/3. Chỉ thêm hai
cấu hình installation AI, không đổi cấu hình/khóa cũ, không chuyển registry
hoặc profile Codex, không kích hoạt provider, không inference thật.

**Chưa hoàn tất toàn đợt:** Codex multi-model/effort chat dùng chung còn chờ
danh tính hỗ trợ và nối dispatch/runtime đã chuẩn bị; Claude adapter/live
chưa hoàn tất và user đã hoãn thuê bao; Antigravity còn tools60 trước prompt.
Effort API hiện chỉ bật khi OpenRouter metadata công bố mức; provider khác
chưa được giả định hỗ trợ. Không gọi runtime/container fixture là quota hoặc
commercial pass. Không full2258 mới, owner pilot hay production/VPS/public.

Trạng thái và việc còn lại tại
[báo cáo cơ cấu AI/model/effort](AI-RESOURCE-MODEL-EFFORT-REDESIGN-2026-10-20.vi.md).
Các mục20/10 bên dưới là lịch sử, không thay status0075 hiện tại.

## Cập nhật20/10 — CLI mới tương thích; đã cài chốt thử Antigravity, chưa model pass

Đã xác minh chữ ký Google và ghim riêng binary mới cho provision local hiện
có; không tự tin binary sau cập nhật. Native đọc6model, UI có nút thử riêng
với xác nhận quota. Backend chặn **trước prompt** nếu init còn công cụ; CLI
thật hiện vẫn khai báo60tool dù agent tools rỗng. Lượt cuối bị chặn đúng chốt,
prompt_sent=false: **chưa nghiệm thu model thật hoặc chat/runner Antigravity**.

108backend tập trung/212Node/typecheck/build23 và browser fixture desktop/
mobile dark-light đạt. Sau cài API427/schema0074,159bảng/3archive/env/Codex
registry giữ nguyên, API/ready/Web200 và worker khỏe. Không full regression
mới, API billing, token extraction, migration hoặc provider activation.

Tiếp theo: xử lý/chứng minh native tool isolation, rồi model/usage thật và
attempt/accounting/cancel trước khi nối chat/routing. Không coi nút thử hoặc
catalog thành inference/provider-supported/commercial pass; không mở lại
Claude/EA2.2/VPS. Chi tiết tại
[báo cáo smoke và chốt còn lại](ANTIGRAVITY-SMOKE-GATE-2026-10-20.vi.md).

## Cập nhật20/10 — Đã cài nút nhận Antigravity native, không mật khẩu PAO

Theo yêu cầu làm giống cách Javis nhận Client: nút Antigravity dùng phiên PAO
hiện tại, gọi CLI chính chủ `agy models` bằng phiên native trên máy, không
đọc/copy token. Probe thật đọc6model; bản1.2.12 không nhận cờ JSON cho models,
đã dùng đúng cú pháp văn bản. Chỉ cấp cho actor/SME local đã provision; không
share ngầm. GETstatus không gọi CLI; có Ngắt riêng trạng thái PAO.

**Đạt lát cắt nhận Client/danh mục, chưa chat/runner/inference Antigravity.**
89test backend tập trung,211Node/typecheck/build23 và browser fixture dark/
light1440/390/320 đạt. API426/schema0074/159bảng; sau cài hash hàng/3archive,
env/Codex registry giữ nguyên, API/ready/Web200 và worker khỏe. Không migration,
API billing, Google token extraction hoặc primary restore. Failure/receipt giữ.

Google không hỗ trợ consumer CLI wrapper: UI yêu cầu xác nhận và ghi rõ cảnh
báo, không coi catalog thành provider-supported/live-model/commercial pass.
Chưa gọi POST từ phiên owner thật hoặc tiêu quota model; không mint diagnostic
JWT để mutation. Bản MCP ngược chiều trước đó không phải luồng kết nối này.
Tiếp theo còn native inference isolation/ledger/model/owner acceptance; không
mở lại Claude/EA2.2 hoặc VPS. Xem [báo cáo kết nối native](ANTIGRAVITY-NATIVE-CONNECTION-2026-10-20.vi.md).

## Cập nhật20/10 — PAO MCP chỉ đọc đã triển khai local; chờ người dùng nối Antigravity

Theo lựa chọn thử hướng đảo chiều: **Antigravity chính chủ → MCP → API PAO**.
Đã thêm package stdio riêng và setup/check/disconnect, không wrapper agy, không
Google token hoặc API fallback. Chọn riêng actor/SME/project/Brain, đồng ý chia
sẻ dữ liệu; token PAO mã hóa Windows CurrentUser, mỗi call kiểm lại native
session/owner-admin/Brain ACL và phạm vi. Không có công cụ ghi hoặc legacy facts.

Nguồn cuối **28unit/stdio/DPAPI +6test API thật trên pao_test đạt**,0fail/error/
skip; API/ready/Web200, schema0074/159 và hash serving backend/env/Codex giữ
nguyên trong bài test. Không migrate/restart hoặc đổi UI/dependency. Không
cộng với95unit protocol EA3 hoặc gọi là full backend regression.

**Đạt bản thử local, chưa đạt native Antigravity handshake/model:** cần người
dùng đăng nhập PAO trong setup, chọn phạm vi và mở thư mục thử ở Antigravity
chính chủ, kiểm `/mcp`. Lưu profile không chứng minh connected. Chưa có UI quản
trị/delegated-token/audit-hardening cho thương mại, chưa lưu kết quả nháp, chưa
provider Antigravity trong chat PAO. Claude/EA2.2 vẫn hoãn, VPS/public vẫn hoãn.
Xem [hướng dẫn và bằng chứng MCP](PAO-MCP-ANTIGRAVITY-LOCAL-2026-10-20.vi.md).
Mục provider-eligibility dưới đây áp dụng cho PAO gọi thuê bao như model,
không phải bằng chứng phủ nhận hướng native MCP mới này.

## Cập nhật20/10 — Claude hoãn theo người dùng; Antigravity đã đo CLI, chưa bật OAuth

Người dùng chưa có Claude Pro/Max và yêu cầu **tạm dừng Claude, ưu tiên
Antigravity**. Không mở lại đăng nhập Claude hoặc yêu cầu mua gói. Hồ sơ ứng
viên được giữ; kiểm tra dừng xác nhận không còn container auth/operation lock.
Codex cá nhân đang hoạt động và EA2.2 hoãn giữ nguyên.

EA3 hiện có **95unit offline đạt** (không cộng với69unit trước), cùng kiểm
chứng Claude nguyên bản2.1.220 trong container chưa đăng nhập/network-none;
không phải Claude live hoặc connector đã đăng ký. Antigravity đã đo trực tiếp
`agy --version/--help`: **1.2.12**, có print/input-format/output-format/model.
Không đọc keyring, auth/catalog, gọi model hoặc lấy phiên Javis.

**Antigravity live còn chốt nhà cung cấp:** điều khoản cá nhân khoản6 hạn chế
phần mềm bên thứ ba truy cập service, ví dụ Antigravity OAuth. Headless có
thật không tự chứng minh PAO được miễn. SDK chính thức có API/Enterprise/local;
chưa có bằng chứng đường thuê bao cá nhân cho PAO được hỗ trợ. Không tự bật
ADC/API, chuyển billing hoặc giả connected để đóng gate. Tiếp theo là xác nhận
cơ chế được Google hỗ trợ hoặc lựa chọn riêng một đường API/Enterprise; sau
đó mới tích hợp native ledger/isolation/UI và nghiệm thu model thật.

Không thay backend/schema0074, frontend, dependency, `.env` hay transport/pin
Codex để triển khai ứng viên. EA3 vẫn chưa hoàn tất; VPS/public vẫn hoãn.
Xem [báo cáo Antigravity và quyết định Claude](EA3-ANTIGRAVITY-2026-10-20.vi.md).
Các snapshot bên dưới là lịch sử; trạng thái mới nhất ở mục này.

## Cập nhật20/10 — Hoãn EA2.2 theo người dùng; EA3 đã chuẩn bị protocol offline

Người dùng chọn **tạm hoãn Codex dùng chung, tiếp tục Claude Code/Antigravity**.
EA2.2=`deferred_by_user`, không phải hoàn tất hoặc bắt buộc mua gói tổ chức;
Codex cá nhân gpt-6-astra/profilev6/personalpolicyv2 giữ nguyên, không share.

EA3: thêm hai parser ứng viên text-only/NDJSON ở package riêng, **69unit đạt**,
không DB/network/provider; file binary Claude/agy đã tìm thấy nhưng chưa probe
auth/version/inference. Không sửa transport Codex đã ghim, backend/schema/UI/
env/dependency hoặc tạo runner. Source pin khớp; API/ready/Web200; dispatch0treo.
**Không phải connector live hoặc hoàn tất EA3.** Claude cần chốt native auth và
isolation; Antigravity OAuth qua PAO còn provider-eligibility gate theo terms.
Không tự dùng API, ADC hoặc pay-as-you-go để đóng gate. Thứ tự EA2.2→EA3 bên
dưới là lịch sử trước quyết định hoãn mới này, không phải yêu cầu làm lại.
Xem [chuẩn bị EA3 và các chốt còn lại](EA3-LOCAL-PREPARATION-2026-10-20.vi.md).

## Cập nhật20/10 — Native chat Codex cá nhân đã đạt bằng model thật

Sau đăng nhập lại PAO, đã nghiệm thu trực tiếp UI: đọc danh mục Codex → chọn
`gpt-6-astra` mặc định Client → Lưu model(profilev6) → Lưu lại thiết lập cá nhân
(revision2) → chat mới không memory/knowledge → một native test job thành công.
Phản hồi chính xác `PAO_CODEX_OK`; planner/final đều completed/reported,
4013input+78output=4091token,0tool/0MemoryJob/0dispatch treo, không API fallback.
Token reported không phải quota còn lại hoặc hóa đơn. API/ready/Web200,
Postgres/Redis local healthy; không tuyên bố Temporal lịch sử đang dừng đã đạt.

Chốt pending đăng nhập/model/job trong mục bên dưới đã được đóng cho **phạm vi
personal Codex chat local**. Giữ nguyên failure/receipt lịch sử; không phải
full regression mới, toàn EA2/P8.4/S6/production hay nghiệm thu Claude/Antigravity.
Tiếp theo **EA2.2 → EA3** theo gate riêng; không tạo runner mới hoặc bật công cụ.
Xem [nghiệm thu native thật](CODEX-NATIVE-LOCAL-ACCEPTANCE-2026-10-20.vi.md).

## Cập nhật20/10 — Đã sửa và cài luồng chọn model Codex; live chờ đăng nhập PAO

Người dùng đã ủy quyền tự sửa/triển khai lại. Diagnostic thật xác định HTTP400
do `gpt-6.1-sol` bị từ chối. CLI `model/list` trả6model, mặc định `gpt-6-astra`,
không có model cũ; không đổi account/copy token/fallback API. Đã cài13file:
đọc/chọn model riêng cho chủ hồ sơ, version/fence/recheck/consent, UI tiếng Việt,
sửa planner prompt/schema và không bật legacy memory ngầm ở chat Codex mới.

Nguồn cuối413backend tập trung/0fail/error/skip,209Node/TypeScript/build23;
schema0074/159bảng/423API, hash hàng cũ và3archive giữ nguyên ngay sau cài,
readonlyreplay3/3, API/Web/worker đạt. `.env`, CLI image/binary/library/registry
không đổi. Không phải full regression hoặc toànEA2/P8.4/S6/production.

**Còn chốt thật:** phiên đăng nhập PAO hết hạn. Chưa đổi cấu hình đang lưu
`gpt-6.1-sol`/profilev5/personalpolicyv1 và chưa chạy lại native job. Không dùng
JWT chẩn đoán/SQL thay đăng nhập owner để sửa model/consent. Sau đăng nhập:
đọc danh mục → chọn/Lưu model → Lưu lại thiết lập cá nhân → chat mới → tối đa
một job test nhỏ (planner/final có thể2calls). Chỉ đóng live gate khi thực sự đạt.
Xem [báo cáo sửa và triển khai](CODEX-MODEL-REPAIR-2026-10-20.vi.md).
Ghi nhận chờ quyền chẩn đoán bên dưới là lịch sử, đã được yêu cầu mới thay thế;
gate hiện tại là authenticated owner session, không phải xin quyền sửa lại.

## Cập nhật20/10 — Native Codex thật chưa đạt, chờ quyền chẩn đoán profile

Theo yêu cầu nghiệm thu bằng model thật: một native run từ UI chính chủ,
`codex_cli / gpt-6.1-sol`, authority `personal_cli`, thất bại
`cli_provider_failed` sau12750ms. Đúng1attempt/1dispatch,0tool/0MemoryJob;
usage unknown/token null, không tự retry/fallback API. Thiết lập cá nhân đã
được thấy revision1/bật trước thao tác của agent; không tạo grant hay bật policy.
Không dùng fixture để coi lỗi này đã được xử lý.

Đã cài bản sửa thông báo UI để không hướng dẫn lỗi Codex sang Ollama:198Node,
TypeScript/build23;4file UI/helper/test, backend/schema0074/421API/env/registry
giữ nguyên, API/ready/Web200, không còn dispatch treo. Không phải full backend
hoặc browser acceptance mới. Chẩn đoán offline chưa xác định nguyên nhân;
hệ thống an toàn chặn writable-profile diagnostic vì có thể cập nhật phiên.
Đang chờ người dùng cho phép bước đó và tối đa1lượt thử thật sau xác định/sửa
lỗi. Không copy auth, đổi account/model, mua quota hoặc triển khai VPS/public.
Xem [báo cáo thử thật20/10](EA21-LIVE-CODEX-2026-10-20.vi.md).

Thứ tự: xử lý lỗi và nghiệm thu native thật → EA2.2 → EA3; các gate khác giữ
nguyên. Ghi nhận “chưa bật/gọi quota” của EA2.1 bên dưới là lịch sử lúc cài,
không phải trạng thái sau lần thử thật này.

## Cập nhật 20/10 — EA2.1 Codex cho chính chủ đã cài local

**EA2.1 local_accepted / installed0074:** thêm thiết lập **Dùng Codex cho tôi**,
không cần tạo grant hoặc đặt thời hạn ngắn. Chủ sở hữu/quản trị viên chỉ chọn
hồ sơ của chính mình, bật, đồng ý sử dụng và Lưu; có thể chọn làm mặc định cho
hội thoại mới của mình. Không chia sẻ cho quản trị viên khác hoặc nhân viên.

Đã đạt385backend tập trung/0fail/error/skip,187Node/typecheck/build23, migration
roundtrip/chặn downgrade có lịch sử, browser fixture dark/light1440/390/320 và
UI bản cài GET-only1440/390. API/Web200, worker khỏe; các bảng dữ liệu cũ giữ nguyên hàng,
3archive/replay đạt; schema0074/159bảng/421API. Không bật cấu hình thật, tạo grant,
gọi quota, sao chép auth, đổi `.env` hoặc CLI registry. Không phải full regression
mới hoặc nghiệm thu model thật. Xem [báo cáo EA2.1](EA21-PERSONAL-CODEX-LOCAL-2026-10-20.vi.md).

Thứ tự còn lại: nghiệm thu một native job thật có đồng ý riêng, rồi EA2.2 kết
nối chung cho nhóm nhỏ theo cơ chế provider phù hợp; EA3 Claude/Antigravity và
P8.4-D bỏ Ollama bắt buộc vẫn chưa hoàn tất. Không mặc định yêu cầu tài khoản
dịch vụ cho chính chủ; chưa nghiệm thu SaaS/hosted, toàn P8.4, S6 hoặc production.
Các ghi nhận19/10 bên dưới là lịch sử trước lần cài này, không phải việc cần làm
lại. Quyền Codex cũ còn ở Nâng cao; tắt thiết lập mới không tự thu hồi quyền cũ.

## Bổ sung 19/10 — Một chủ sở hữu trước, nhóm nhỏ là tùy chọn

Người dùng chốt: PAO phục vụ một người vận hành doanh nghiệp hoặc nhóm2–3
người, phần lớn là owner/admin. Không bắt tạo nhân sự, mời tài khoản hoặc thiết
lập bộ máy phân quyền để bắt đầu. Một workspace là một không gian dữ liệu riêng;
không đổi API enum, vai trò hoặc tự gộp dữ liệu theo cách gọi trên UI.

Lát cắt UX local đã cài: **Kết nối AI → AI mặc định → Giọng nói**, hướng dẫn ba
bước; tự đọc trạng thái chỉ GET, đề xuất nguồn API duy nhất nhưng chưa bật/lưu,
một nút Lưu và phần quyền cá nhân cũ đóng trong Nâng cao. Mời cộng sự là tùy
chọn. Backend/schema0073/419API/env/CLI/grants không đổi; không tự dùng quota.
179Node/typecheck/build23, browser fixture dark/light/1440/390/320 và UI thật
GET-only1440/390 đạt. Đây không phải EA2 hoặc toàn CLI hoàn tất. Xem
[nghiệm thu và giới hạn solo-first](SOLO-FIRST-AI-UX-LOCAL-2026-10-19.vi.md).

Ưu tiên EA2 được làm rõ, không đổi lịch sử EA1:

1. **EA2.1 — Codex cho chính chủ:** rút gọn đăng nhập/chọn model/đồng ý sử dụng;
   không bắt người dùng tự thao tác bảng grant/TTL. Hiện luồng cũ còn cần quyền
   cá nhân trong Nâng cao; chưa được coi là đã giải quyết bằng đổi giao diện.
   Giữ native accounting, source/revoke/cancel và không gọi model khi chỉ Lưu.
2. **EA2.2 — Nhóm nhỏ:** dùng kết nối backend chung nơi cơ chế provider cho phép;
   không yêu cầu nhân viên nhập khóa riêng, vẫn tách dữ liệu và quyền hành động.
   Không tự chuyển cache Codex cá nhân thành hồ sơ dùng chung.
3. **EA3:** Claude Code/Antigravity theo cùng trải nghiệm đơn giản; không giả kết
   nối từ nút UI. API/local là tùy chọn, không fallback trả phí tự động.

Không mặc định yêu cầu tài khoản dịch vụ cho luồng Codex cá nhân. Cơ chế danh
tính tổ chức chỉ được xét khi cần và provider hỗ trợ; không mua gói hoặc đổi
sang cơ chế tính tiền thay người dùng. Owner pilot/local thật trước VPS/public.

## Quyết định 19/10 — PAO riêng cho từng SME, AI cấp doanh nghiệp

Ưu tiên thương mại mới được người dùng xác nhận: **một SME / một VPS riêng**,
thường 1–3 người; khách hàng chỉ đăng nhập PAO. Client/API ở backend, thành viên
kế thừa quyền AI theo chính sách doanh nghiệp, không cần cấp từng grant model.
Phân quyền dữ liệu và hành động vẫn theo vai trò ứng dụng. Giữ workspace/brand/
private Brain/ledger/approval; không gộp dữ liệu hoặc tự chia sẻ CLI cá nhân.
Quyết định này ghi đè hướng thương mại shared SaaS ngày 11/10, không xóa lịch sử
hay tự mở triển khai VPS/public đã tạm hoãn.

Theo [ADR AI doanh nghiệp](ADR-ENTERPRISE-AI-DEDICATED-2026-10-19.vi.md):

| Chặng | Phạm vi | Trạng thái |
|---|---|---|
| EA1 | Policy kế thừa, API, chat người xem chỉ đọc, UI và kiểm thử/migration/khôi phục | local_accepted_API_slice / installed0073:343backend tập trung,167Node,build23; chưa bật policy/gọi provider; không phải CLI doanh nghiệp hoàn tất |
| EA2 | Chính chủ trước, rồi profile/identity dùng chung phù hợp provider | EA2.1 native chat chính chủ gpt-6-astra đã đạt; EA2.2 deferred_by_user20/10; không chuyển cache cá nhân |
| EA3 | Claude Code/Antigravity và Client routing/usage theo cùng chính sách | in_progress:69unit protocol candidate đạt; native adapter/auth/isolation/provider eligibility và live proof chưa đạt |
| EA4 | Owner pilot local rồi bộ cài/vận hành VPS riêng | Chưa đạt; production/public vẫn hoãn |

Xem [nghiệm thu EA1 và hướng dẫn cấu hình](ENTERPRISE-AI-EA1-LOCAL-2026-10-19.vi.md).
Bản cài có157bảng/419API; đối chiếu ngay sau cài giữ nguyên các hàng cũ và3
archive/replay. UI thật chỉ GET đạt kiểm tra chức năng; lượt so dữ liệu tiếp
theo thất bại do có hoạt động đồng thời được người dùng xác nhận. Không phục
hồi primary, không sửa receipt thất bại thành pass, không coi đây là một full
regression mới hoặc nghiệm thu toàn P8.4/S6/production. EA2 là bước tiếp theo.

Lượt thử Codex thật 19/10 lúc 20:08 giờ Việt Nam qua PAO đã tạo đúng một
dispatch `codex_cli / gpt-6.1-sol`, sau đó thất bại `cli_provider_failed`.
Usage là unknown, token null: không khẳng định quota chưa bị trừ hoặc inference
đã thành công. Không retry tự động, không fallback API. Điều này bổ sung tình
trạng C/E bên dưới, không ghi đè các receipt trước lúc người dùng đăng nhập.

## Ưu tiên mới18/10 — P8.4 kết nối CLI, đang triển khai C

Người dùng duyệt kế hoạch Codex, Claude Code và Antigravity; bắt đầu bằng
P8.4-A/B offline trước khi nối tài khoản thật. Đây là nhánh tích hợp engine,
không mở full coding executor/P8 hoặc viết lại P6/S0–S5. Ghi đè thứ tự tiếp
theo trong thời gian làm nhánh này, không thay lịch sử/gate S6/production.

Theo [ADR P8.4](ADR-P84-CLI-CONNECTIONS.vi.md):

| Chặng | Trạng thái hiện tại | Kết quả cần đạt |
|---|---|---|
| A/B | local_accepted_offline18/10 | 26unit Windows x3 và26Linux network-none; hợp đồng scope, bounded process, fixture, cleanup và source/schema guards; chưa đăng ký live engine |
| C | in_progress / owner_profile_auth_observed19/10 | Nền tảng native có full2343 cũ. Lát cắt đăng nhập mới: coverage2356 bằng1416 pass trước lỗi helper restore và940 pass tiếp diễn sau sửa phạm vi đường dẫn; không phải một full xanh mới. 9 restore guards, native RPC offline,167Node/typecheck/build23 và browser fixture đạt. Đã cài schema0072/155bảng/416API; API/Web200, worker khỏe, hash dữ liệu và3HTTP replay đạt ngay sau cài. Người dùng thao tác đăng nhập: profile connected/v5; chưa grant/quota/native inference. Lượt so snapshot tiếp theo khác do có hoạt động người dùng được xác nhận; giữ lỗi, không phục hồi primary |
| D | implementation_pending | Ollama không bắt buộc; memory/embedding riêng; bảo toàn dữ liệu/pin cũ |
| E | in_progress / Codex_model_access_UI_local_accepted19/10 | Client trước/mặc định, ba ô Client; API sau, bốn ô có Lưu cấu hình/Xóa khóa và mask trạng thái. Codex đăng nhập/profile riêng đã ghi nhận; có mục Quyền dùng Codex tái sử dụng native grants, self-only, nhãn hàng/TTL, lưu/kích hoạt/thu hồi riêng, mất ACK đọc lại.167Node/typecheck/build23 và3browser suites đạt. Chưa tự tạo quyền hoặc chạy job thật; Claude/Antigravity, routing/usage còn gate, default/fallback không đổi |
| F.1 | implementation_pending / vendor_usage_gate | Claude Code CLI/SDK, không thu token hoặc dùng chung thuê bao ngầm |
| F.2 | implementation_pending / vendor_usage_gate | Antigravity adapter offline; điều kiện third-party OAuth chưa được xác nhận phù hợp |
| G | pending | Hồi quy, live proof từng provider, chuyển mặc định từng phạm vi |

Cả ba provider có thiết kế, không đồng nghĩa đã kết nối. Bản **đang phục vụ**
đã cài nền tảng Codex CLI local: launcher dualPYTHONPATH, schema0072, API và
engine enum mới; chỉ thêm `CLI_CONNECTIONS_ENABLED=true` vào `.env` và registry
device có image/binary/host-source pin. Lượt cài backend đó không đổi bố cục UI/default model,
không sao chép auth, cấp grant hay dùng thuê bao thật. Native backend installed
khác nghiệm thu job thật; toàn C/D/E/F/G và S6/production chưa hoàn tất.
Bản backup và
G:/Javis giữ nguyên. Đích sau D là không phụ thuộc bắt buộc Ollama, không phải
không còn dùng LLM. API/local model vẫn tùy chọn; không fallback trả phí tự động.
Kết nối SaaS/hosted cần review riêng, không suy từ local fixture. S6.1 real data,
owner pilot và VPS/public vẫn chưa đạt/deferred theo quyết định hiện hành.

Cập nhật cài đặt đăng nhập19/10: thêm riêng `CLI_BROWSER_LOGIN_ENABLED=true`
cho local cá nhân và 4 API auth, không migration/bảng mới, không đổi registry,
Python pin, model/default hoặc credentials khác. Đã kiểm tra bản cài với nguồn
đúng kế hoạch, hash dữ liệu cũ và 3 replay chỉ đọc. Xem
[hướng dẫn và bằng chứng đăng nhập](CODEX-UI-LOGIN-LOCAL-2026-10-19.vi.md).
Luồng app-server này **chưa được nghiệm thu cho commercial/hosted/SaaS**;
không chia sẻ thuê bao cho nhân viên. Mã xác nhận chỉ gửi đúng phiên PAO,
không lưu trình duyệt/log. Đã quan sát profile connected sau khi người dùng
tự thao tác; bước còn lại của C là grant/model consent → một native job có
ledger/usage/cancel/revoke, không tự cấp quyền hoặc gọi model để đóng gate.

Lượt tiếp theo19/10 hoàn thiện giao diện **Quyền dùng Codex**, không đổi backend,
schema0072/416API/env/pin/dependencies. Xem
[hướng dẫn cấp quyền và kiểm thử](CODEX-MODEL-ACCESS-LOCAL-2026-10-19.vi.md)
và `.runtime/codex-access-current-status.json`. Chủ tài khoản cần chọn đúng SME/
nhãn hàng/thời hạn, lưu rồi kích hoạt; tiếp theo chọn quyền cho một hội thoại
văn bản mới và nghiệm thu native run/ledger/usage. Không tự giả phiên chủ tài khoản
để tạo grant; diagnostic bearer vẫn chỉ dùng GET. Các bài browser là fixture,
không đóng gate một job thật, S6 hoặc SaaS/production.

[Báo cáo A/B](P84-CLI-FOUNDATION-LOCAL-2026-10-18.vi.md) ghi receipt, checkpoint,
lịch sử sandbox/socketpair và lỗi Windows pipe đã sửa. Không phải full regression
mới hoặc nghiệm thu toàn P8.4. **P8.4-C — Codex local** đã kiểm tra phiên bản,
parser và một lượt gọi trực tiếp theo yêu cầu người dùng. Xem
[kết quả kiểm tra trực tiếp](P84-CODEX-DIRECT-LOCAL-2026-10-18.vi.md).
Lượt này không qua PAO và không mở quyền tool/SaaS. Bước tiếp theo vẫn là
native authority/accounting, profile có phạm vi và cách ly trước chạy job.
[Báo cáo native19/10](P84-CODEX-NATIVE-CANDIDATE-2026-10-19.vi.md) có phạm vi,
receipt, cài đặt0072 và lịch sử lỗi. Luồng đăng nhập riêng được bổ sung/quan sát
ở cập nhật mới phía trên. Hiện còn grant/model consent → một native job có
ledger/usage và các chốt cancel/revoke/recovery; chưa chuyển sang D.

Bổ sung UX19/10 theo yêu cầu người dùng: **Nhà cung cấp mô hình** có hai tab
con, **Kết nối qua Client** đứng trước/mặc định (Codex, Claude Code, Antigravity),
**Kết nối qua API** đứng sau (giữ bốn provider hiện có). Đây chỉ là lát cắt
P8.4-E; không tự đổi model/default hoặc fallback trả phí. Bằng chứng UI đầu tiên
chỉ có đọc metadata; lượt đăng nhập Codex mới ở trên đã bổ sung nút Kết nối.
Claude/Antigravity
ghi rõ chưa triển khai, không nhận token hoặc giả lập đã kết nối. Xem
[nghiệm thu và giới hạn](MODEL-PROVIDER-TABS-LOCAL-2026-10-19.vi.md).
Chưa dùng kết quả UI này để đóng C/E/F, nghiệm thu thuê bao, S6 hay production.

Lượt UI tiếp theo19/10 theo ảnh mẫu: ba ô Client gọn, bốn ô API nhập trực tiếp,
trạng thái khóa đã nhập/chưa lưu/đã lưu và nút Lưu cấu hình/Xóa khóa. Các tùy
chọn model nâng cao được thu gọn; giữ xác nhận lưu, xóa và kiểm thử có phí.
[Báo cáo ô kết nối](MODEL-PROVIDER-CARDS-LOCAL-2026-10-19.vi.md) ghi 164Node,
build23 và browser fixture mới. **Chưa xong kết nối thật ba Client**: Codex đã
có onboarding chính thức và đã ghi nhận profile đăng nhập; Claude/Antigravity
vẫn bị vô hiệu kèm lý do, không thay metadata thành kết nối giả. Ưu tiên còn
lại của C là đăng nhập người dùng và job thật; các
gate provider/SaaS và F không được bỏ qua để làm giao diện có vẻ hoạt động.

## Khắc phục audit local18/10 — truy vết và bằng chứng hiện tại

Được duyệt sửa log yêu cầu an toàn, readiness và test frontend cũ. Không mở
milestone mới, thay mô hình SaaS hoặc bật kết nối thật. Xem
[phạm vi và chốt kiểm chứng](AUDIT-REMEDIATION-2026-10-18.vi.md).
Các bằng chứng UI/backend cũ giữ nguyên; backend bổ sung truy vết có binding
mới, không tự kế thừa full2.293 cũ. Readiness phải phản ánh fail/stale có cấu
trúc và giữ chốt primary drift chưa xác định nguồn. Không tự đóng sự cố chỉ
vì một lượt test mới sạch. S6/owner pilot/production vẫn chưa nghiệm thu.

## Bổ sung local18/10 — xóa công việc tạo nhầm/tạo lỗi

Thêm xóa có xác nhận trong chi tiết công việc, quyền owner/người tạo còn quyền
ghi, kiểm tra phiên bản và liên kết tại backend. Chỉ công việc thủ công chưa có
lượt chạy/kết quả; chặn đang chạy, hoàn tất, Goal/workflow và phụ thuộc. Xóa khỏi
bảng bằng dấu xóa và trạng thái đã hủy, giữ lịch sử, không xóa dữ liệu vĩnh viễn.
Xem [hướng dẫn và phạm vi](TASK-DELETION-LOCAL-2026-10-18.vi.md).

Đây là thay đổi backend/API (407operations, không migration, schema0071), không
phải UI-only. Binding mới không tự kế thừa full2272backend cũ. Nghiệm thu chức
năng bằng focused regression, contract, production build và browser API native;
bản cài chỉ được xác nhận khi `.runtime/task-delete-completion.json` pass=true.
Các receipt/readiness UX trước đó giữ nguyên như bằng chứng lịch sử; không sửa
hash để coi là CI đầy đủ mới. S6.1 dữ liệu thật, owner pilot và production vẫn
chưa nghiệm thu; không bật kết nối hoặc xóa công việc thật để thử tính năng.

## Ưu tiên UX đã duyệt18/10 — tách chức năng trước S6.1

Người dùng duyệt một đợt tái cấu trúc giao diện local gồm bốn phần: điều hướng
và đăng nhập/lời mời; Cài đặt theo mục đích; Kho tri thức/Skills/Kế hoạch;
các màn hình vận hành và nghiệm thu toàn bộ. Không tạo roadmap cạnh tranh,
không thêm backend/connector hoặc mở lại P6/S2–S5.

Cài đặt có bảy nhóm và mục con riêng; Kế hoạch có năm tab; Skills chỉ mở
trình biên tập khi cần; Ads nhóm chế độ xem, Công việc phân biệt dữ liệu với
cách xem, Hộp thư tách hội thoại/kênh/tin gửi/nhật ký. Đăng nhập có nút tạo tài
khoản bằng mã mời, vẫn invite-only. Hỗ trợ sáng/tối, điện thoại, bàn phím,
liên kết cũ và bảo vệ nháp. Xem [phạm vi/hướng dẫn nghiệm thu](UI-UX-RESTRUCTURE-2026-10-18.vi.md).

Chỉ chốt local_accepted khi `.runtime/ux-restructure-completion.json` pass=true
và readiness `s6-local-ux-restructure-v1` đạt.157Node/build23 và native browser
là bằng chứng UI; baseline2272backend/202focused chỉ tái sử dụng khi API/locks
và binding không đổi. S6/production chưa đóng. Sau đợt UX vẫn S6.1 dữ liệu thật
trên local → owner pilot → VPS/public khi người dùng mở lại.

## Bổ sung local18/10 — phân nhóm Cài đặt / Kết nối

Giao diện chia thành bốn nhóm: tài nguyên quảng cáo, hệ thống BOT, ứng dụng và
plugin, MCP/công cụ. Kho plugin có chín khu vực và bảy ứng dụng quy hoạch.
Meta/Google/Telegram/MCP giữ luồng hiện có; các nền tảng chưa có backend chỉ là
vị trí chờ, không nhận khóa, không cài đặt hoặc gọi nhà cung cấp. Zalo Bot khác
Zalo OA; GPT Ads không phải tuyên bố có API quảng cáo GPT đang hoạt động.

Nguồn UI đã đạt148Node, TypeScript, production build23trang và native browser
(sáng/tối,320/390px, bàn phím, lịch sử điều hướng, bảo vệ cấu hình chưa lưu).
Sáu kiểm thử offline chốt bằng chứng UI đạt; không thay backend, schema, `.env`
hoặc chính sách SME. Baseline2272backend/202focused cũ chỉ được dùng lại khi
hash backend và binding khớp. Bản cài chỉ được coi local_accepted khi
`.runtime/connections-ui-completion.json` pass=true và chẩn đoán readiness
`s6-local-connections-ui-v1` đạt; không suy từ việc build/copy nguồn.

[Hướng dẫn và phạm vi nghiệm thu](CONNECTIONS-HIERARCHY-LOCAL-2026-10-18.vi.md).
Đây là cải thiện UX trên roadmap hiện tại, không mở milestone mới; S6.1 dữ liệu
thật, pilot và production giữ nguyên các chốt bên dưới.

## Bổ sung local18/10 — doanh nghiệp, nhãn hàng và thư viện Skills

Người dùng chốt chủ doanh nghiệp hiện có được tạo thêm doanh nghiệp mình sở hữu;
vẫn invite-only, SME mới không sao chép dữ liệu/nhân viên/kết nối/quyền. Đã
hoàn thiện và nghiệm thu nguồn lát cắt quản lý tổ chức/Kho tri thức trước S6.1;
không mở lại S2–S5 hoặc thay roadmap bằng một dãy milestone khác.

- Cài đặt: tạo/đổi tên doanh nghiệp, tạo/đổi tên nhãn hàng, điều hướng đội ngũ/
  hồ sơ/kết nối hiện có; kiểm quyền và phiên bản phía backend.
- Kho tri thức: hồ sơ doanh nghiệp, hồ sơ nhãn hàng, Skills cho agent, tri thức/
  bộ nhớ. Dùng BusinessProfile và Studio hiện có, không thêm kho/runner khác.
- Skills: nhóm chuyên môn, tìm/lọc, soạn agent/skill, gán phiên bản agent được
  công bố, kiểm lược đồ, duyệt/công bố, lịch sử; nhóm không cấp quyền công cụ.
- Nguồn đạt2272full Linux backend/18stage,202Windows focused,132Node/build23 và
  native browser. Bản cài local_accepted được chốt bằng
  `.runtime/organization-completion.json` pass=true sau health/replay3/readonly
  browser/primary-env hash; không suy từ việc chỉ copy source hoặc khởi động.

[Báo cáo và bằng chứng](ENTERPRISE-KNOWLEDGE-LOCAL-2026-10-18.vi.md),
[hướng dẫn sử dụng](ENTERPRISE-KNOWLEDGE-USER-GUIDE.vi.md).
M6/S6/production chưa đóng; tiếp theo vẫn S6.1 đúng SME/brand/kỳ và pilot local.

## Ưu tiên hiện hành — 18/10/2026: hoàn thiện local trước

Theo quyết định mới của người dùng: **hoàn thiện khung local → nghiệm thu bằng
dữ liệu thật trên local → pilot local → lập kế hoạch VPS/public sau**. Mục này
thay thế các chỉ dẫn “tiếp theo là hạ tầng production” ở phần lịch sử bên dưới;
không xóa hoặc sửa ngược bằng chứng M/P/S đã có.

| Thứ tự hiện hành | Phạm vi | Điều kiện chuyển |
|---|---|---|
| 1 | M6 UX phục vụ S6: giao diện sáng/tối và khả năng sử dụng local | Nghiệm thu bản cài thật theo [báo cáo UX](LOCAL-UX-LIGHT-DARK-2026-10-18.vi.md); không suy ra toàn M6/S6 hoàn tất |
| 2 | Vòng vận hành local trên nền S5/M6 — local_accepted18/10 | Hồ sơ/kế hoạch có cấu trúc → AI theo job → duyệt → báo cáo; theo dõi job, cancel ACK, lost-response recovery, phụ thuộc và làm lại qua kế hoạch mới đã kiểm.132Node/125focused backend/build23/native browser; [báo cáo](LOCAL-OPERATING-CYCLE-2026-10-18.vi.md). Không phải full2258backend mới hoặc toàn M6/S6 |
| 3 | S6.1: nghiệm thu dữ liệu thật trên local | Người dùng cung cấp/chọn đúng SME, brand, tài khoản, kỳ dữ liệu hoặc file xuất; bắt đầu read-only, đối chiếu nguồn; action thật phải được duyệt riêng |
| 4 | S6.3: pilot local | Owner hoàn thành trọn vòng, đo chất lượng, usage, sai sót và khả năng phục hồi; giải quyết lỗi chặn trước mở rộng |
| 5 | S6.2: VPS/public production | `deferred_by_user`; mở lại khi người dùng quyết định. Host/HTTPS/keys/offsite/alerts/reboot/owner review vẫn chưa đạt, không bỏ gate |

Không hỏi lại dữ liệu thật khi đang chuẩn bị local. Hosted CI tại commit3151851
là baseline đã có, không phải CI cho các file UX mới. Giữ schema0071, API và
phân quyền SME; không bật Ads/Telegram/voice, không tự push/merge/deploy.
Toàn S6/production vẫn chưa được nghiệm thu. Các mục “hiện tại/duy nhất” có
ngày cũ bên dưới chỉ mô tả lịch sử nếu trái thứ tự này.

**Tiếp theo: S6.1 — nghiệm thu dữ liệu thật trên local**, khi người dùng chọn
SME/brand/tài khoản/kỳ dữ liệu hoặc cung cấp file xuất. Chưa có dữ liệu thật
thì giữ `external_pending`, không tự nối/bật dịch vụ để vượt gate. Nghiệm thu
vòng local dùng gateway fixture và báo cáo nội bộ; không chứng minh AI tự lập
mọi kế hoạch kinh doanh, media hoàn chỉnh hay quảng cáo thật. Giữ các năng lực
mở rộng đúng phạm vi và chốt chất lượng riêng.

**Cập nhật kế hoạch 17/10/2026: kiến trúc đích AI Chief of Staff / Business OS; kế thừa baseline và bằng chứng local đã có, không khởi động lại M/P/S.**

## Lịch sử điều hướng — kiến trúc và lộ trình 17/10/2026

Master này sở hữu thứ tự thực hiện. [Kế hoạch kiến trúc và triển khai chi tiết](PAO-TARGET-ARCHITECTURE-AND-DELIVERY-2026-10-17.vi.md)
phân rã đầu ra, module ảnh hưởng, phụ thuộc và nghiệm thu; không tạo roadmap cạnh
tranh. Các đoạn “tiếp theo” ngày cũ bên dưới là lịch sử nếu trái mục này.

**Hiện tại: Giai đoạn3 — local_prepared=true và hosted CI đã đạt;
nhưng toàn Giai đoạn3/production/S6 chưa đóng.**
Đã push source đã review lên nhánh `phase3/hosted-ci` của repository private
CEH-YuLing/Pao-ACOS, commit3151851; main giữ nguyên. GitHub run39030584315 đạt
18stage/2258backend/0fail/error/skip,120Node/TypeScript/build23 và audit runtime
Python57/0, npm0. Đã tải/đối chiếu JUnit và artifact theo đúng commit, không dùng
local pass thay hosted. Xem [nghiệm thu hosted CI](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md).
Trạng thái tổng hợp mới `.runtime/phase3-current-status.json`; receipt local cũ
giữ nguyên theo phạm vi lịch sử. Không merge, không đổi code/DB/.env/runtime đang chạy.
CI Linux11b0... đạt cùng18stage:2258backend/0fail/error/skip,120Node/TypeScript/
build23,13native smoke và audit Python57packages/0advisory. Windows focused111
và installed readonly UI/live/worker/replay3 đạt; không gọi là full Windows mới.
API/worker đã chuyển sang PyJWT2.15.1/cryptography50.0.2 trong runtime pin riêng,
`.venv` cũ giữ nguyên; `.env`, mã API/nghiệp vụ, schema0071/399/153 và binding
Windows8e9a71b9 không đổi. Private profile mới TLS/minimum-role/non-root/restart
đạt; clone153tables/3archive trên Python3.12.15 đọc đúng hash, chặn scope/hash
sai và cả3execution khác binding. Không sửa reader hoặc execution gate.
Xem [báo cáo xử lý chốt](PHASE3-GATE-REMEDIATION-2026-10-17.vi.md),
[lịch sử Giai đoạn3](PHASE3-CI-PRIVATE-PRODUCTION-2026-10-17.vi.md) và
[runbook](PHASE3-PRIVATE-PRODUCTION-RUNBOOK.vi.md).
Npm runtime0 nhưng còn5high dev/braces chưa có bản vá, cần residual-risk review;
không xóa lint hoặc audit-fix force. Hosted CI đã đạt riêng; VPS/domain/public HTTPS/private
storage/keys-offsite/alerts/reboot/owner review vẫn external_pending. Chưa bật
provider/quảng cáo/dữ liệu thật; release_promotable=false. Giữ lịch sử CIbaca...
FAIL và drift đã phát hiện, không restore đè dữ liệu. Lượt11b0 mới snapshot
primary trước/sau khớp, không lấy probe rời thay full pass. Tiếp theo là gates
môi trường thật/review được cấp quyền; không lặp P6/lifecycle hoặc tự chạy pilot.

Baseline giữ: Giai đoạn2 — lát cắt M6 UX phục vụ S6 đã local_accepted trọn phần;
Giai đoạn1 S6.2 lifecycle giữ local_accepted. Toàn M6/S6/production chưa đạt.
120Node/typecheck/build23; Edge production candidate + API native/DB0071 riêng
đạt trọn journey,12khu vực,SME/vai trò/nháp/deep-link/lỗi mạng/keyboard/mobile.
Đã chuyển đúng frontend đã kiểm chứng, UI cài thật kiểm read-only, API/ready/
Web200, worker khỏe, replay3/3. Backend/schema/dữ liệu cũ/`.env` không đổi;
kế thừa2258/2258, không gọi đây là một full backend mới.
Xem [báo cáo M6](M6-COMMAND-CENTER-UX-LOCAL-ACCEPTANCE-2026-10-17.vi.md)
và [hướng dẫn](M6-COMMAND-CENTER-UX-USER-GUIDE.vi.md).
**Giai đoạn3 — CI và private production thuộc S6.2 đang thực hiện**, trạng thái
và chốt bảo mật ở đầu tài liệu. Hosted CI đã đạt; chưa có host/HTTPS/reboot/key recovery thì giữ gate tương ứng pending,
không tự push/deploy hoặc mở provider. Dữ liệu thật vẫn hoãn theo người dùng.

Baseline Giai đoạn1 được giữ nguyên:
Đã bảo vệ phiên bản, triển khai lời mời/thành viên, thu hồi phiên và xuất/
yêu cầu xóa có xác nhận. Full Windows2258/2258/0skip,114Node/typecheck/build23,
browser thật hai SME/mobile và clone migration/restore đạt. Primary0071/live399/
153physical, health/Web200, worker khỏe, replay3/3; dữ liệu cũ/`.env` giữ nguyên.
Chưa bật provider/xóa tự động, chưa hosted CI/pilot/production;62ARQ warnings
và React-hook warnings vẫn là nợ kỹ thuật. Không suy nghiệm thu toàn S6.2 hạ tầng.
Xem [báo cáo hiện hành](S62-ACCOUNT-DATA-LOCAL-ACCEPTANCE-2026-10-17.vi.md)
và [hướng dẫn người dùng](S62-ACCOUNT-DATA-USER-GUIDE.vi.md).
Các checkpoint nhỏ được triển khai tuần tự nhưng bàn giao **cả giai đoạn**,
không dừng xin xác nhận sau từng bước. Chỉ dừng nếu thiếu quyền/môi trường thật.
Sổ S6/acceptance sở hữu bằng chứng; không suy production hay secret-clean từ local.

### Kiến trúc chốt để phát triển

- Frontend: Next.js/React/TypeScript, web responsive và tiếng Việt; PWA là
  hạng mục tương lai, Tailwind/shadcn không phải yêu cầu đổi stack.
- PAO Core là lớp trách nhiệm trong backend FastAPI modular monolith: ngữ cảnh
  SME, điều phối kế hoạch/task, chọn AI, policy/approval, memory và audit.
  Không mặc định thêm API Gateway service, backend Javis hay microservices.
- Execution: tái sử dụng Run/Task/Goal/Studio; DB outbox + ARQ/Redis cho giao việc,
  Temporal cho workflow dài/chờ/phục hồi khi bật. Không thêm runner/scheduler thứ hai.
- Data: PostgreSQL/pgvector là authority theo loại dữ liệu ở mục10.1; file/object
  storage có ACL/version/hash, vector/graph/export là projection có thể rebuild.
- Models: giữ hybrid Ollama + cloud theo SME/brand/agent/step/job; không hardcode
  vendor theo chức danh, không tự fallback gửi dữ liệu cloud nếu chưa có policy.
- Integrations: managed PAO app mặc định khi provider hỗ trợ, BYO nâng cao;
  token/bot có luồng riêng, mọi connection/grant/resource/delivery gắn đúng SME.
  Một bot chỉ thuộc một SME; một SME có thể nhiều bot. Model grant không là tool grant.
- Security: kiểm lại quyền ở API, queue, tool và delivery; ngân sách mô phỏng
  không là số tiền provider; duyệt plan không thay duyệt content/action.

### Lịch sử thứ tự phát triển17/10 — đã được mục18/10 cập nhật

| Ưu tiên | Checkpoint/năng lực đã có ID | Đầu ra và điều kiện chuyển |
|---|---|---|
| 1 | S6.2 chuẩn bị release — local_accepted17/10 | Checkpoint source/DB/restore; không commit/push. Full history/secret review trước publish và key/offsite recovery còn gate riêng |
| 2 | S6.2 A — local_accepted17/10 | Owner mời một lần/hết hạn, quản lý vai trò và gỡ quyền A không ảnh hưởng B; không public signup |
| 3 | S6.2 B — local_accepted17/10 | Thu hồi server-side từng phiên/tất cả phiên, recheck SSE/metadata; gỡ membership thu hồi queue/grants theo SME, logout không tự hủy mọi job |
| 4 | S6.2 C — local_accepted17/10 | Export danh mục/ACL có giới hạn, preview/yêu cầu xóa/xác nhận riêng; retention mặc định tắt, chưa có executor xóa thật |
| 5 | M6 lát cắt phục vụ S6 — local_accepted17/10 | Chuẩn hóa 12 khu vực, Settings theo nền tảng, một hành trình tiếng Việt profile→plan→job→review→report; refactor nhỏ có shim, không làm lại P0–P6/S1–S5 |
| 6 | S6.2 CI và production — hosted_ci_accepted / production_pending | GitHub run39030584315 trên3151851 đạt18stage/2258backend/120Node/build23, audit Python57/0 và npm runtime0; local/private/clone acceptance giữ nguyên. Còn5dev advisories, Actions/image drift và gates host/HTTPS/keys/storage/monitor/reboot/owner; không auto promote/merge/deploy |
| 7 | S6.1 / M3 — nghiệp vụ thật | Một SME/brand/provider/account/kỳ dữ liệu read-only được đối chiếu; một action thật chỉ sau đủ adapter, policy và phê duyệt riêng |
| 8 | S6.3 / M5B — pilot và kết quả | Owner dùng trọn vòng, đo chất lượng/usage/chi phí; outcome có nguồn và review. Chỉ đóng S6 khi đủ cả S6.1/S6.2/S6.3 |
| 9 | P7.5 / M8 — mở rộng nghiệp vụ | Telegram/voice thật, TikTok/Zalo OA/Botcake, media/publishing và CRM theo nhu cầu, từng adapter/use case nghiệm thu riêng; không gộp thành đã có |
| 10 | P8 / M7B / M8 — mở rộng có kiểm soát | Coding workers sandbox, extensions, PWA và thương mại hóa/billing được chọn theo nhu cầu sau pilot; không bắt buộc để đóng S6 |

S0–S5/P0–P6 giữ local acceptance theo phạm vi cũ; S3/S4/P5/P7.5 còn gate
provider thật không bị xóa. Các hàng9–10 là proposed, không là lệnh bật dịch vụ.
S6.1 dữ liệu thật đã được người dùng hoãn; không hỏi lại trong chuẩn bị local.
Không làm giả dữ liệu primary hoặc tự chọn account/đích để vượt gate.

Mỗi lần chỉ triển khai một giai đoạn, tuần tự các checkpoint; nghiệm thu cả phần khi đủ tests/contract/browser/
restore liên quan. External pending không biến thành pass và cũng không buộc
lặp baseline đã có khi inputs không đổi. Không hứa ngày hoàn thành/công suất
VPS khi chưa đo; phạm vi cắt MVP và điều kiện chấp nhận quan trọng hơn số module.

## Hiện trạng duy nhất — S6 chuẩn bị local ngày16/10

**S6 in_progress, local preparation đã kiểm chứng.** Người dùng xác nhận chưa
có dữ liệu thật, chỉ chuẩn bị local. Preflight S6 đọc lại live/health/worker/
replay và giữ các gate thật pending. Linux backend2224/2224 đạt,0fail/0error/
0skip; frontend kiểm riêng đạt114Node/TypeScript/build22 sau sửa archive thiếu
JSX. Giữ pipeline TypeScript lỗi nguyên trạng, không gọi đó là một pipeline
end-to-end xanh.18unit offline+4archive tests,44Windows cấu hình/restore và
9Temporal/ARQ Windows, browser/mobile/restore đạt. **GitHub CI chưa chạy hosted**.
Không sửa backend/UI/schema/.env, không restart hoặc bật provider; baseline
S5 bên dưới còn nguyên. Không gọi đây là toàn S6 hay production đã đạt.

[Sổ S6](S6-COMPLETION-REGISTER.vi.md) và
[runbook](S6-LOCAL-PREPARATION.vi.md) ghi bằng chứng/điều kiện. Việc tiếp theo
duy nhất: vòng đời tài khoản/dữ liệu S6.2 còn thiếu mã triển khai:
invite-only do owner mời, thu hồi phiên/quyền theo SME, export và yêu cầu xóa
có preview/xác nhận, chưa tự xóa. Đây là quyết định đã chốt, không hỏi lại và
không gọi việc còn thiếu mã là external_pending. Xem
[ADR S6](ADR-S6-ACCOUNT-AND-DATA-LIFECYCLE.vi.md) và
[log Linux/Windows](S6-LINUX-LOCAL-2026-10-16.vi.md).
Không làm lại Linux baseline/P6/S5 khi các inputs không đổi; không tự push,
tạo tài khoản/đích thật, bỏ gate hoặc public deploy.

### Baseline S5 đã đạt, không triển khai lại

**Toàn S5.1–S5.6 local_accepted:0070/live382.** Đã triển khai
native Run/Studio adapter, ghim AI theo công việc, duyệt nội dung, ledger/hành
động mô phỏng, dừng và báo cáo nội bộ giờ/ngày theo P6. Browser/restore populated
và chất lượng Ollama dữ liệu giả đạt. Hồi quy cuối2224/2224 passed,0fail/0error/
0skip, backend không đổi;114Node/build22 đạt. Primary149physical/148business,
3archives; API/ready/Web200, worker khỏe, replay3/3 và dữ liệu cũ không đổi.
Chỉ bật S5, launcher pin0070; secret/cấu hình khác giữ nguyên. Lượt full phát
triển đầu2217ca/14lỗi được giữ riêng, không gọi đó là pass. Hai model theo bước
được kiểm bằng fixture; chất lượng thực kiểm bằng một Ollama đã cài.
**Bước tiếp theo: S6 — chuẩn bị pilot và nghiệm thu các gate thật**, không tự
bật Ads/đăng bài/Telegram hoặc public deployment. Production chưa nghiệm thu.
Sổ S5 là nơi ghi kết quả mới nhất. Các checkpoint0066–0068 là lịch sử;
không làm lại job adapter hoặc thêm runner thứ hai.

Xem [sổ S5](S5-COMPLETION-REGISTER.vi.md),
[báo cáo tích hợp](S5-INTEGRATION-2026-10-16.vi.md) và
[hướng dẫn sử dụng](S5-USER-GUIDE.vi.md).

### Mốc lịch sử S4 — local_accepted, chuyển sang S5
Ứng dụng PAO/BYO theo SME, OAuth/config pins, resolver/worker/data fences và
Cài đặt tiếng Việt đã rollout0065/live353/136physical/3archives. API/ready/Web200,
workerhealthy,current binding aef/replay3/3/exact restore135business đạt.
2099ca có kết quả cuối đạt: full2089/10lỗi fixture, sửa fixture rồi52+82kiểm lại
đạt, backend không đổi; không gọi đây là full rerun xanh.114Node/TypeScript/
build21/browser Meta+Google và Telegram regression/lock-fresh-process đạt.
[Báo cáo S4](S4-INTEGRATION-2026-10-16.vi.md), [sổ S4](S4-COMPLETION-REGISTER.vi.md)
ghi gate; không dùng fixture hoặc configured làm real OAuth/production accepted.
S5 chưa được triển khai trong lượt S4 lịch sử; source candidate S5 bắt đầu trong
lượt tiếp theo bên trên. Không hỏi lại các quyết định SaaS đã duyệt.

## Kết quả S3 đã chốt ngày15/10 — mốc lịch sử

**Toàn S3.1–S3.3 đã local_accepted. Bước kế tiếp: S4 — Meta/Google theo SME.**
Webhook/mode/cursor epoch/báo cáo và Settings/pairing/team/Việt hóa đã có;
93focused/109Node/TypeScript/build21/browser tích hợp đạt. Full backend có
2077passed/1lỗi script allowlist revision; sửa script và27retry đạt,2078ca có
kết quả cuối đạt trên backend không đổi, không tuyên bố full rerun xanh.
Primary0064/live349/134physical/3archives; API/ready/Web200,workerhealthy,
current binding và3/3 replay chỉ đọc khớp, dữ liệu cũ/.env nguyên vẹn.

[Báo cáo tích hợp hiện hành](S3-INTEGRATION-2026-10-15.vi.md) và
[sổ S3](S3-COMPLETION-REGISTER.vi.md) sở hữu bằng chứng/gate. Chỉ bàn giao cả S3
sau khi đạt, không dispatch lại từng primitive. Bot thật/HTTPS/reboot vẫn là
external_pending; không tự bật cờ hoặc gửi tin. Sau S3 mới đến S4 theo thứ tự đã chốt.

## Hướng sản phẩm mới — SaaS Chief of Staff cho doanh nghiệp/nhãn hàng

**Nguồn thứ tự hiện hành:** mục Điều hướng17/10 ở đầu và mục12; chi tiết kiến trúc
tại [kế hoạch17/10](PAO-TARGET-ARCHITECTURE-AND-DELIVERY-2026-10-17.vi.md).
[Kế hoạch đồng bộ11/10](PAO-UNIFIED-DEVELOPMENT-PLAN-2026-10-11.vi.md) giữ audit
và lịch sử checkpoint, không thay thứ tự mới.
<details>
<summary>Lịch sử checkpoint trước nghiệm thu tổng S3 — không phải thứ tự hiện hành</summary>

Các số schema/test/binding và câu “tiếp theo” trong khối này thuộc thời điểm cũ.
Quyết định sản phẩm vẫn hiệu lực; tiến độ mới chỉ đọc ở mục Hiện trạng bên trên.

S0.1 audit/tài liệu đã thực hiện; S0.2 quyết định sản phẩm đã được người dùng
chốt ngày11/10 và mapping/quyền/threat model ghi trong
[ADR-S02](ADR-S02-SAAS-TENANT-AND-CONNECTIONS.vi.md).
**S0.3 đạt LOCAL 11/10:** Docker/PG/Redis đã phục hồi; API/ready/Web200,
workerhealthy, schema0048, contract308/binding/M2archives3/3 khớp. Verified
checkpoint821source/115physical tables/3archives, restore row hashes/schema
equivalence khớp, idle0. Xem [S0.3 acceptance](S03-LOCAL-BASELINE-ACCEPTANCE-2026-10-11.vi.md).
**S1.1 đạt LOCAL11/10:** context API/active SME selector và role theo SME đã rollout;
67focused backend,12pure/runtime,real HTTP browser,12module UI,build21 đạt.
Contract309/schema0048,API/ready/Web200,workerhealthy. Xem [S1.1 acceptance](S11-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
**S1.2 đạt LOCAL11/10:** ticket/abort/no-store/raw-body/SSE/download fencing,
actor-SME storage và membership refresh đã rollout.25pure/runtime,35focused backend,
S12/S11/P7 real HTTP browser,UI12 và build21 đạt. Xem [S1.2 acceptance](S12-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
**S1.3 đạt LOCAL11/10:** corpus hai SME/private Brain/parent IDs/job/outbox và
cleanup SSE đã kiểm chứng. Full ban đầu1177passed/2failed; hai lỗi được sửa và
26corpus/factory+65affected regression đạt trên bản cuối;25pure/runtime,
S12/S11/P7browser và build21 đạt. Xem [S1.3 acceptance](S13-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
**S2.1A đạt LOCAL11/10:** inventory chỉ đọc, native ownership/private Brain ACL
giữ nguyên và mapping preview không cấp quyền.111focused+26S13+43engine backend,
25pure/runtime,TypeScript/build21 đạt; live contract311/binding/M2replay3/3,
schema0048 và exact restore khớp. [Acceptance](S21A-LOCAL-ACCEPTANCE-2026-10-11.vi.md),
[ADR-S21A](ADR-S21A-CONNECTION-INVENTORY.vi.md).
**S2.1B1 đạt LOCAL11/10:** persisted staged reference/grant/audit,
eligibility local và migration0049 đã rollout; chưa cấp runtime authority.
172focused+32affected backend,25runtime/typecheck/build21 và live317 đạt;
full1240/0fail/0skip đạt; manifest/restore niêm phong cuối trong [Evidence](S21B1-LOCAL-ACCEPTANCE-2026-10-11.vi.md),
[ADR-S21B1](ADR-S21B1-STAGED-CONNECTION-GRANTS.vi.md).
**S2.1B2a đạt LOCAL11/10:** model registration-denial fences,
immutable legacy actor/brand/source pin, fresh checks và publication/legacy memory
fences.190focused+81affected/29model corpus,25Node/typecheck/build21 đạt;
3browser/live317/0049/replay3/3/pre-deploy exact restore đạt; seal cuối trong [Evidence](S21B2A-LOCAL-ACCEPTANCE-2026-10-11.vi.md),
[ADR](ADR-S21B2A-MODEL-EXECUTION-FENCE.vi.md). Không activate staged grants.
**S2.1B2b đạt LOCAL11/10:** explicit model consent/immutable grant pins và Settings;
full1298/0fail/0skip,29authority corpus/real ARQ,25Node/typecheck/build21 và browser đạt;
0050/live321/binding/M2replay3/3/exact restore đạt. P7 từng có lỗi thoáng qua chưa
tái hiện trong bốn lượt sau, không gọi đã sửa. [Evidence](S21B2B-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
**S2.1B2c đạt LOCAL11/10:** MCP consent/grant pins giữ native tool/Skill/Brain quyền,
234affected/25Node/typecheck/build21/browser2+3 đạt;0051/live323/restore119business
exact, không server thật hoặc anonymous tenant execution. [Evidence](S21B2C-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
**S2.1B2d đạt LOCAL12/10:** Meta/Google consent/exact account/job pins và typed
report, không cấp Ads writes;186affected/66focused/real ARQ/25Node/build21/browser4
đạt;0052/live327/exact restore119business. [Evidence](S21B2D-LOCAL-ACCEPTANCE-2026-10-12.vi.md).
**S2.2A đạt LOCAL12/10:** append-only reapply/version và native model probe fences,
247affected/25Node/typecheck/build21/browser4 đạt;0053/live328/exact restore119business.
[Evidence](S22A-LOCAL-ACCEPTANCE-2026-10-12.vi.md).
**S2.2B1 đạt LOCAL13/10:** backend model quotas/leases và probe cap,
171affected/25Node/typecheck/build21/browser4 đạt;0054/live330/exact restore121business.
[Evidence](S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md). Chưa quota UI/MCP/Ads queues.
**S2.2B2a đạt LOCAL13/10:** native read-job caps/fair dispatch/recovery;
238affected/33focused/25Node/typecheck/build21/browser5,0055/live332, legacy hashes
exact. [Evidence](S22B2A-LOCAL-ACCEPTANCE-2026-10-13.vi.md).
**Toàn S2 đạt LOCAL14/10; S3.1A+B đã đóng local15/10. Đầu việc tiếp theo duy nhất:
S3.2C — bridge/webhook/report integration** (A/B đã source_verified15/10;
[368affected/25Node/candidate0063](S32B-SCOPED-EXECUTION-2026-10-15.vi.md), primary0060 chưa đổi).
Production chưa đạt; không hỏi
lại ba lựa chọn đã phê duyệt. [Evidence tích hợp](S2-FINAL-INTEGRATION-2026-10-14.vi.md).
**Cập nhật S3.1B15/10:** explicit owner mapping + Settings đã rollout và đạt local:
1737backend/0fail/0skip,5browser/96Node/TypeScript/build21,0060/live338/current binding,
129physical/3M2archives/exact restore; [evidence](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md).
Không tự map SME/bot hoặc copy token; không làm lại S3.1. Docker đã recovery an toàn.
**S3.2A source_verified15/10:**143focused/52kernel; scoped envelope/owner checks,
PG bot lease/metadata HTTP guard, không schema/API/UI/worker wiring. Primary vẫn
S31B0060/338/bindinge7ddf35b; source candidate chưa rollout. [Evidence](S32A-KERNEL-2026-10-15.vi.md),
[A/B/C hữu hạn](ADR-S32-TELEGRAM-SCOPED-RUNTIME.vi.md). A/B đã source_verified;
C mới full integration/release. Không coi metadata kernel là nhiều bot đã chạy.
13/10 B2b metadata backend đạt local0056/live334: durable per-SME model/MCP
admission/leases/replay, source/actor/Brain publication và transport/body guards;
298affected/browser3/build21 đạt. [Evidence/phần còn mở](S22B2B-METADATA-QUOTA-2026-10-13.vi.md).
Credential payload/URL logging đạt local356affected/browser3, live0056/334,
binding85348d46 theo [evidence](S22B2B-CREDENTIAL-PAYLOAD-2026-10-13.vi.md).
Local discovery/selection quota đạt local425affected/browser4/0056/live334,
binding1bd51278 theo [evidence](S22B2B-LOCAL-DISCOVERY-2026-10-13.vi.md).
Legacy unaccounted inference đạt local theo
[evidence](S22B2B-LEGACY-ACCOUNTING-2026-10-13.vi.md): default policy cũng có caps,
mode-off từ chối trước factory/decrypt/ctx injection, queued unknown không repin;
472passed/1fixture lỗi được sửa và focused38/38, Knowledge3/3, browser4/4 đạt.
Live0056/334/bindingd41d7a1d/exact restore124business đạt, không full backend mới.
Shared embedding admission/Memory coverage đạt local theo
[evidence](S22B2B-MEMORY-EMBEDDINGS-2026-10-13.vi.md):189backend/25Node/typecheck/
contracts/build21/browser2+1,0057/live334/bindingb79a09f2, old-column hashes exact.
Không synthetic Run/LlmAttempt, không double charge, quota deny/offline vẫn
lexical-only có ACL; model/endpoint pin và no-resend unknown giữ nguyên.
Knowledge index/query đạt local0058/live334/bindingc136c3aa theo
[evidence](S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md):565integrated B2b,
25Node/contracts/typecheck/build21/browser2+1/exact restore124business.
Model/endpoint/generation và vector-space binding giữ source/Brain/actor ACL,
unknown retry không resend, explicit rebuild là intent mới, keyword fallback giữ.
**B3 quota Settings đạt local14/10; S2.2B native scoped coverage đóng local.**
128affected backend+35Node/typecheck/contracts/build21/browserHTTP1,
0058/live334/bindingc136c3aa không đổi/exact restore theo
[evidence](S22B3-QUOTA-SETTINGS-2026-10-14.vi.md). Owner/admin policy/usage,
CAS/lost-response/manual recovery và mobile/SME switch đạt; không billing claim.
**S2.3A observations đạt local14/10:**49Node/76affected gồm browser2/build21,
9/9installed snapshots/0058/live334/binding không đổi/exact restore theo
[evidence](S23A-SETTINGS-OBSERVATIONS-2026-10-14.vi.md). Refresh lỗi không giữ
state cũ; stored connected/config/flags không thành healthy; unknown không safe.
**S2.3B đạt local14/10:** tách cloud form/nonce/consent/key clear/unknown recovery/
registered probe refusal, provider dossier;147affected trước visual console audit,
57Node/typecheck/build21/finalbrowser3/0058/live334/binding không đổi/restore theo
[evidence](S23B-CLOUD-SETTINGS-2026-10-14.vi.md). Duplicate React key đã sửa,
console gate giữ nguyên. Không provider thật hoặc CAS mới cho mọi CRUD.
**S2.3C đạt local14/10:** MCP bearer clear/locks/discovery nonce/native rotation/
version conflict/manual recovery/disconnect/audit/help;157affected backend/64Node/
typecheck/build21/finalbrowser5/0058/live334/binding không đổi/exact restore theo
[evidence](S23C-MCP-SETTINGS-2026-10-14.vi.md). Không server thật/OAuth upgrade.
**S2.3D đạt local14/10:** own Ads status/OAuth popup allowlist/consent/cookie/
unknown recovery/cached accounts/jobs/disconnect;100native backend+5browser qua
affected/focused recovery,71Node/typecheck/build21/0058/live334/binding không đổi/
restore theo [evidence](S23D-ADS-SETTINGS-2026-10-14.vi.md). Meta official docs429,
provider thật/App Review/Cloud approval còn gate riêng; không tenant App S4.
**S2.3E đạt local14/10:** host App form synclock/epoch/secret clear/native CAS/
unknown/manual recovery/readonly/multi-SME gate;26affected gồm4browser/77Node/
finalTypeScript/build21/0058/live334/binding không đổi/exact restore theo
[evidence](S23E-HOST-CONFIG-SETTINGS-2026-10-14.vi.md). Temp config only, .env thật
không đổi; không restart/tenant App S4 hoặc production admin acceptance.
**S2.3F đạt local14/10:** account cá nhân/SME/role, native eligible team snapshot,
unknown/no stale/manual GET và mobile390/320 giữ quyền native;63backend/8browser/
80Node/typecheck/build21/0058/live334/exact restore theo
[evidence](S23F-TEAM-ACCOUNT-MOBILE-2026-10-14.vi.md). Không invite/grant/revoke
tự động hoặc tenant App S4. Agent catalogue không là hoạt động/model gán cho job.
**Toàn S2/S2.3 đạt local14/10:**1684backend/0fail/0skip,21browser tích hợp,
80Node/typecheck/build21,0058/live334/binding3d811e0e/exact restore đạt theo
[bằng chứng cuối](S2-FINAL-INTEGRATION-2026-10-14.vi.md). Telegram legacy đã dùng
shared admission/pins và chặn session sai SME/member; không bật bot thật.
MCP có một lỗi route harness thoáng qua chưa rõ nguyên nhân, không gọi đã sửa.
**S3.1A foundation đã đạt local14/10:**1709backend/0fail/0skip,4browser/80Node,
0059/live334/bindingb9365b68/exact restore; [evidence](S31A-LOCAL-ACCEPTANCE-2026-10-14.vi.md).
Không tạo/mapping connection thật, không token hoặc transport mới.
**S3.1B cũng đạt local15/10; S3.2A/B source_verified, tiếp theo duy nhất: S3.2C.** True-provider benchmark/global host fairness/
production vẫn chưa đạt; không lấy các lượt fixture làm live acceptance.
Audit ban đầu 11/10 từng thấy API/Web connection refused và Docker unavailable;
đã được recovery/gate S0.3 bên trên thay thế, không dùng health10/10 thay lần kiểm mới.

Yêu cầu người dùng ngày 10/10/2026: giao mục tiêu tháng cho PAO, nhận kế hoạch
tổng thể, phân công Content/Facebook, ảnh/video, Ads và phân tích; người dùng
duyệt trước khi thực thi ra ngoài. PAO theo dõi tiến độ/ngân sách và báo cáo
theo giờ/ngày. Kết nối được quản lý riêng cho SME trong Settings.
Đây là hướng sản phẩm, không phải các năng lực đã được nghiệm thu end-to-end.

**Yêu cầu đã chốt 11/10: custom AI theo từng job khi setup.** Không gán cứng
provider cho Content/Creative/Ads. S2 chuẩn bị connection/model/quota theo SME;
S5.3 triển khai lựa chọn SME→brand→agent→workflow step→job, immutable run pins,
capability/privacy/budget/fallback và approval. Model không thay quyền tools;
media generation là adapter riêng. Chi tiết/gate trong kế hoạch đồng bộ S5.3.

**Checkpoint kế tiếp: S3.2C — bridge/webhook/report integration**; S3.2A/B
source_verified, không restart bản chạy trước release tích hợp C. S3.1A namespace và S3.1B
explicit mapping đã đạt local theo [evidence mới](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md).
Thứ tự S3.1 — Telegram connection identity/explicit legacy mapping,
trước S3.2/S3.3 và S4; không mở rộng M6/P8. Mã S bổ sung cho SaaS, không đổi
tên/xóa lịch sử P/M.
S0.1/S0.2 chỉ cập nhật tài liệu; S0.3 recovery/startup/harness đã đạt local,
không migration mới, đổi credential/gate hoặc gọi provider.19focused backend,
7restore-checker,8runtime/SSE,browser shell12 và build21 đạt; full1156tests là
evidence10/10, không chạy lại trong S0.3. Các gate P7.5/M3/production vẫn mở.

**Tiến độ S3.2B15/10 — snapshot store/identity và kết quả cuối:** disabled credential store/generation/audit
và quarantine/cursor đã source_verified,199focused/56store, candidate0061 clone
roundtrip/old rows exact/populated downgrade refused. Primary vẫn0060/129tables,
không restart/activation. [Store evidence](S32B-DURABLE-STORE-2026-10-15.vi.md).
Identity registry/resolver legacy/native cũng đã source_verified sau đó:
238focused/39identity+199existing, candidate0062 clone roundtrips/old rows exact,
primary vẫn0060 theo [evidence mới](S32B-VERIFIED-IDENTITY-2026-10-15.vi.md).
Cập nhật cuối15/10: **toàn S3.2B đã source_verified**,368affected/41scoped+25Node,
candidate0063 clone roundtrips/schema equivalent/old rows exact, native admission/
outbox/accounting/revoke-restore fences đạt theo
[execution evidence](S32B-SCOPED-EXECUTION-2026-10-15.vi.md). Primary0060/338 chưa đổi,
chưa HTTP send/worker wiring/full release; tiếp theo duy nhất C, không làm lại B.

**S3.2C đang triển khai15/10:** polling/admission adapter source_verified,
408affected/40polling+25Node, candidate0063, không migration mới;
[báo cáo phần nhận tin](S32C-POLLING-ADAPTER-2026-10-15.vi.md) ghi gate và giới hạn.
Sau đó [sender có authority fence source_verified](S32C-SENDER-ADAPTER-2026-10-15.vi.md):
509affected/61sender+25Node, candidate0063, không migration mới. Sau đó đã nối
[worker riêng source_verified](S32C-WORKER-2026-10-15.vi.md),26worker/535affected+
25Node đạt với Redis/ARQ thật và HTTP fixture. Chưa webhook/report integration hoặc rollout; primary vẫn0060.
Tiếp theo trong C: webhook/mode/report, oversize/idle-week policy, concurrency còn
mở và release tích hợp; chưa chuyển S3.3.

</details>

### Yêu cầu bổ sung đã chốt 15/10 — tiếng Việt và quyền Telegram

Đây là đặc tả và snapshot trước triển khai. Pairing/team/Việt hóa nay đã có
trong candidate; trạng thái nghiệm thu xem mục Hiện trạng, không lấy các câu
“chưa triển khai” lịch sử bên dưới để làm lại các phần đã được kiểm chứng.

Toàn bộ giao diện khách hàng dùng tiếng Việt; mọi nhóm Cài đặt phải có hướng
dẫn mục đích/phạm vi/quyền, từng trường và nguồn lấy giá trị, bước cài đặt,
kiểm tra/trạng thái thật, xử lý lỗi, đổi khóa/thu hồi/ngắt kết nối. Giữ nguyên tên
sản phẩm và các giá trị kỹ thuật, không dịch API hoặc credential. Settings hiện
còn nhãn tiếng Anh; chưa coi đã đạt yêu cầu mới từ nghiệm thu S2.3 trước đây.

Telegram: một bot thuộc một SME, một SME có thể có nhiều bot/người dùng. Liên
kết Telegram ID với tài khoản PAO/membership phải rõ ràng; /start hoặc quản trị
nhóm không cấp quyền. Tách quyền cấu hình/giao việc/duyệt/nhận báo cáo, kiểm lại
Brain/nhãn hàng/quyền ở worker và trước gửi. Pairing/team UI chưa triển khai.

[Đặc tả và gate](PRODUCT-SETTINGS-AND-TELEGRAM-ACCESS.vi.md) áp dụng S3.2B/C
và S3.3. S3.3 nhận phần hướng dẫn/Việt hóa Cài đặt từng nhóm và thiết lập đội ngũ
Telegram; màn hình mới dùng tiếng Việt ngay. Không đổi thứ tự S3.2B → C → S3.3,
không tự bật bot hoặc gọi đây là hoàn thành toàn bộ Việt hóa PAO.

### S0 — hợp đồng sản phẩm và quyền điều khiển (quyết định sản phẩm đã chốt)

- Phân cấp: doanh nghiệp/workspace → nhãn hàng → kế hoạch → chiến dịch
  → task/artifact → phê duyệt → thực thi → báo cáo/outcome. Kiểm tra mapping
  các entity hiện có trước khi thêm bảng; không tạo task engine thứ hai.
- Một doanh nghiệp có nhiều thành viên/nhãn hàng/kết nối; một người có thể tham
  gia nhiều doanh nghiệp. Người dùng đã phê duyệt ngày11/10/2026.
- Mỗi màn hình và request xác định doanh nghiệp đang hoạt động; không lấy
  `workspaces[0]` như lựa chọn ngầm. Session/run giữ scope đã pin; chuyển workspace
  không chuyển quyền hoặc sửa nghĩa lịch sử đang chạy.
- Chief hỏi dữ liệu còn thiếu, lập kế hoạch có mục tiêu/KPI/ngân sách/lịch,
  phân công agent cùng task service hiện có; sản phẩm đầu ra có version/nguồn.
- Duyệt kế hoạch chỉ cho phép công việc nội bộ trong phạm vi được duyệt.
  Đăng bài/bật Ads/chi tiền/gửi ra ngoài cần execution approval cụ thể; thay đổi
  vượt phạm vi cần duyệt lại. Approval pin doanh nghiệp/nhãn hàng/tài khoản,
  phiên bản nội dung/kế hoạch, hành động, ngân sách, thời hạn và người duyệt.
- Worker kiểm lại quyền/credential/policy/budget khi thực thi, không chỉ lúc
  enqueue. Có idempotency, cancel, giới hạn retry và đối soát kết quả không rõ;
  không gửi lại mù nếu provider timeout sau khi đã nhận hành động.
- Báo cáo ghi thời điểm dữ liệu, timezone/currency, dữ liệu thiếu/trễ và tách
  số liệu xác định với nhận định AI. Báo cáo theo giờ không đồng nghĩa dữ liệu
  thời gian thực; dùng lịch durable hiện có, không phụ thuộc tab đang mở.
- Tình huống MVP: nhãn hàng A lập kế hoạch tháng 10/2026 bằng fixture có nguồn,
  tạo brief/nội dung nháp, trình duyệt, mô phỏng thực thi và báo cáo. Không
  tuyên bố agent đã sản xuất video thật hoặc đã vận hành Ads thật từ fixture.

### Kết nối riêng: không chỉ thêm form token

Audit source ngày 10/10: model/MCP và token Meta/Google đã có workspace scope
một phần; Meta app settings ghi `.env`, giới hạn một owner/một workspace;
Google app/developer config toàn hệ thống; Telegram bot/bridge/webhook và một
số khóa dedup chưa tách theo bot. TikTok chưa có native backend connector.
Đây là gap thiết kế, chưa phải bằng chứng xảy ra rò rỉ dữ liệu.

- Phân biệt platform credentials với tenant credentials. DB/Redis/JWT/master
  encryption key và emergency kill switch thuộc quản trị máy chủ, không SME.
- Đã chốt hai chế độ: OAuth qua ứng dụng PAO là mặc định khi provider hỗ trợ;
  BYO app credentials cho SME nâng cao. Một hệ thống dùng chung phục vụ nhiều SME.
  Provider token-based có luồng riêng, không ép OAuth không được hỗ trợ.
- Trước mỗi connector, đọc tài liệu API chính thức hiện hành và ghi ngày/version,
  auth/scopes/review/callback/refresh/revoke/rate limits. Settings có hướng dẫn,
  form required/optional, kiểm tra, chọn tài khoản/đích, gán brand/quyền và trạng
  thái thật theo [ADR-S02](ADR-S02-SAAS-TENANT-AND-CONNECTIONS.vi.md); không nhập secret qua chat.
- Connection có workspace, phạm vi nhãn hàng/tài khoản, provider, quyền team,
  credential mã hóa, version, health/scopes/expiry/revocation và audit không secret.
  Không trả secret rõ về UI; không ghi tenant credential vào `.env`.
- Telegram: nhận token an toàn trong Settings, xác minh bot identity; chat ID
  là đích nhận tin riêng. Dedup/update/peer/binding/outbox/lease/offset/webhook
  phải có connection identity. Scheduler/report sender cũng phải resolve đúng bot.
- Meta: App ID/App Secret khác token được cấp quyền và ad account ID.
  OAuth state pin workspace/connection/config version; không bỏ guard local cũ
  trước khi có tenant-aware replacement và kiểm thử cách ly.
- Google: OAuth client, developer token, token người dùng, Customer ID và optional
  MCC/login-customer context phải resolve đúng chế độ sở hữu kết nối.
- TikTok và các connector chưa có: triển khai adapter/auth/account selection
  riêng rồi nghiệm thu read-only; trường token hoặc catalog không là connector.
- Model/MCP: giữ encryption/SSRF guards, thêm quyền chia sẻ trong SME và quota;
  không fallback credential của SME khác. Local LLM cho cloud SaaS cần secure
  local bridge riêng, không coi localhost máy chủ là máy của khách hàng.

### Thứ tự S và gate nghiệm thu

| Checkpoint | Phạm vi | Gate trước khi chuyển bước |
|---|---|---|
| S0 — local foundation đã đạt | Shared SaaS đã chốt; ADR mapping/quyền; S0.3 verified baseline/restore | S1.1–S1.3/S2.1A/S2.1B1/B2a đạt local; không suy ra production, Git commit hoặc offsite DR đã đạt |
| S1.1 — local_accepted11/10 | Membership context,active SME/role,selector và scoped consumers | S1.2 đã đạt; không suy ra toàn S1/SaaS isolation đã đạt |
| S1.2 — local_accepted11/10 | Client cache/raw body/SSE/download/storage/focus refresh; không cancel/repin run | S1.3 corpus local đã đạt; poll không phải instant revocation; không suy ra provider isolation/production |
| S1.3 — local_accepted11/10 | Hai SME/private Brain/parent IDs, worker/outbox revoke và bounded SSE cleanup |26corpus/factory+65affected tests,3browser,25pure/runtime/build21; restore exact114business tables; không phải mọi endpoint/provider đã secure |
| S1 — tenant context | Chọn SME rõ ràng, RBAC/team, UI cache/SSE/session và worker scopes | Hai SME: truy cập chéo API/job/artifact/history bị từ chối; đổi workspace không giữ dữ liệu trái quyền |
| S2.1B1 — local_accepted11/10 | Identity/grants/audit staged bền vững; eligibility, migration0049 |172focused/32affected/full1240/25Node/build21; không cấp quyền thực thi; seal/restore xem evidence |
| S2.1B2a — local_accepted11/10 | Model registration-denial, legacy immutable scope pin, fresh checks/publication/memory |190+81backend/29fence/25Node/build21/3browser/live317/replay/restore; staged vẫn non-executable |
| S2.1B2b — local_accepted11/10 | Model consent/pins/Settings/chooser, migration0050 | Full1298/25Node/build21/browser/live321/exact restore; không cấp tool/Ads từ model grant |
| S2.1B2c — local_accepted11/10 | MCP explicit consent/pins, giữ native bounded tool/review/Brain gates |234affected/25Node/build21/browser/live323/0051/exact restore; fixture không xác nhận server thật |
| S2.1B2d — local_accepted12/10 | Meta/Google read authority |186affected/66focused/real ARQ/browser4/build/live327/0052/restore; không live Ads hoặc writes |
| S2.1B2 — local_accepted từng checkpoint | B2a/B2b model, B2c MCP, B2d Ads read đạt | Không suy ra model grant là quyền mọi connector; staged vẫn data-only; final S2 gate riêng |
| S2.2A — local_accepted12/10 | Lifecycle/vault/version, append-only reapply |247affected/browser4/build/live328/0053/restore; populated history downgrade refuse; [thiết kế](ADR-S22-LIFECYCLE-AND-RESOURCE-ISOLATION.vi.md) |
| S2.2B — local_accepted14/10 | Quota/resource isolation theo SME |B1/B2a/B2b/B3 native scoped coverage đạt local; không billing/global host fairness claim |
| S2.2B1 — local_accepted13/10 | Model policy/admission/unknown/expiry/probe |171affected/browser4/build21/live330/0054/exact restore121business; [Evidence](S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md) |
| S2.2B2 — local_accepted13/10 | Native reads/metadata/legacy/embeddings coverage |B2a/B2b scoped native coverage đạt; global host scheduling/production chưa đạt |
| S2.2B2a — local_accepted13/10 | MCP/Meta/Google read jobs |238affected/33focused/browser5/build21/0055/live332; [Evidence](S22B2A-LOCAL-ACCEPTANCE-2026-10-13.vi.md) |
| S2.2B2b — local_accepted13/10 | Metadata/probes/legacy/embedding coverage |Native model/MCP/local metadata, legacy denial, Memory+Knowledge embeddings đạt0058/live334/565integrated/backend/browser2+1/build21/restore theo [evidence](S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md); không global host fairness hoặc provider thật |
| S2.2B3 — local_accepted14/10 | Quota Settings/integration |128affected/35Node/typecheck/contracts/build21/browserHTTP1/0058/live334/exact restore; [Evidence](S22B3-QUOTA-SETTINGS-2026-10-14.vi.md) |
| S2.3 — local_accepted14/10 | Settings hợp nhất |A/B/C/D/E/F và cổng tích hợp đạt; [Evidence cuối](S2-FINAL-INTEGRATION-2026-10-14.vi.md) |
| S2.3A — local_accepted14/10 |Reliable GET observations/unknown/no stale state |76affected gồm browser2/49Node/typecheck/build21/9installed snapshots/0058/live334/exact restore; [Evidence](S23A-SETTINGS-OBSERVATIONS-2026-10-14.vi.md) |
| S2.3B — local_accepted14/10 |Cloud Model Settings lifecycle/help |147affected trước console audit/57Node/typecheck/build21/finalbrowser3/0058/live334/exact restore; [Evidence](S23B-CLOUD-SETTINGS-2026-10-14.vi.md); không live provider |
| S2.3C — local_accepted14/10 |MCP Settings lifecycle/help |157affected backend/64Node/typecheck/build21/finalbrowser5/0058/live334/exact restore; [Evidence](S23C-MCP-SETTINGS-2026-10-14.vi.md); không live server |
| S2.3D — local_accepted14/10 |Ads Settings lifecycle/help |100native backend+5browser qua affected/focused recovery,71Node/typecheck/build21/0058/live334/exact restore; [Evidence](S23D-ADS-SETTINGS-2026-10-14.vi.md); không live provider, Meta docs429 |
| S2.3E — local_accepted14/10 |Host-config Settings lifecycle/scope |26affected gồm4browser/77Node/finalTypeScript/build21/0058/live334/exact restore; [Evidence](S23E-HOST-CONFIG-SETTINGS-2026-10-14.vi.md); không .env thật/restart |
| S2.3F — local_accepted14/10 |Team/account & mobile consolidation |63native backend/8browser/80Node/typecheck/build21/0058/live334/exact restore; [Evidence](S23F-TEAM-ACCOUNT-MOBILE-2026-10-14.vi.md); không tự invite/grant/revoke hoặc tenant App S4 |
| S2 — connection nền tảng, local_accepted14/10 | S2.1/S2.2/S2.3 và final integration đạt local |1684backend/21browser/80Node/build21/0058/live334/exact restore; preview/staged không là authority; provider/production gates riêng |
| S3 — local_accepted15/10 | Toàn S3.1–S3.3: runtime/webhook/report, Settings/pairing/team/hướng dẫn tiếng Việt | [S3 register](S3-COMPLETION-REGISTER.vi.md); [tích hợp](S3-INTEGRATION-2026-10-15.vi.md);2078ca kết quả cuối đạt sau sửa script phục hồi/27retry,109Node/build21/browser;0064/live349/current binding/replay3/3; external_pending |
| S4 — local_accepted16/10 | OAuth/config/account/worker và Settings theo SME | [Báo cáo S4](S4-INTEGRATION-2026-10-16.vi.md)/[sổ S4](S4-COMPLETION-REGISTER.vi.md);2099ca kết quả cuối đạt sau sửa fixture/52+82kiểm lại,114Node/build21/browser;0065/live353/current binding/replay3/3/exact restore135business; external_pending |
| S5 — local_accepted16/10 | Profile → plan → delegation → approval → báo cáo |0070/live382, xem sổ S5; text jobs/ngân sách mô phỏng/internal reports không là media/live campaign |
| S6 — in_progress | Lifecycle tài khoản/dữ liệu, CI/production, nghiệp vụ thật và pilot | S6.2 lời mời là việc tiếp theo; implementation_pending khác external_pending, xem điều hướng17/10 và sổ S6 |

**Ba quyết định đã chốt ngày11/10/2026:** (1) một hệ thống phục vụ nhiều SME;
(2) OAuth ứng dụng PAO mặc định + optional BYO theo provider;
(3) một workspace = một doanh nghiệp có nhiều brand/thành viên/kết nối, một người
có thể thuộc nhiều workspace. Không hỏi lại; thay đổi vượt quyết định này hoặc
external writes cần authority riêng. Không yêu cầu secret trong chat.

Giữ modular monolith/PostgreSQL/ARQ/Temporal hiện có. SaaS không bắt buộc mỗi SME
một database hoặc Kubernetes. RLS là phương án cần đánh giá cùng role/context/
pooling/bypass tests; chưa có bằng chứng DB-wide RLS hiện tại. Không tuyên bố
SaaS-ready chỉ vì thêm workspace_id hoặc đạt tests của một module.

## Trạng thái hiện tại — P7.1–P7.4 đóng LOCAL; P7.5 thực tế còn mở

P7.1–P7.4 có code cho shared Run admission, ChannelBinding/Inbox/Outbox/audit,
customer grounded-only profile và consented scoped voice turns. Không fork chat
core và không thêm scheduler/poller Telegram thứ hai. UI thêm `/channels` và
voice turn lifecycle desktop/mobile; giữ Orb và các module hiện có.

Gate focused channel/voice/contract, browser P7 HTTP thật với microphone tổng
hợp, dispatcher ARQ thật, populated restore và clone0046→0048→0046→0048 đã đạt.
Production build21/21 và runtime/SSE8/8 đạt. Full regression cuối1156passed,
0failed/0skipped và8browser gates P6/P7 HTTP thật đạt. Shell UI12module cũ đạt.
Main đã lên0048 sau verified checkpoint/restore;109business tables cũ giữ hash,
5bảng P7 mới rỗng. API/ready/Web200,workerhealthy,live contract308operations và
source binding khớp; M2archive replay3/3. Các flags channel/voice/Telegram/Meta,
Goal/workflow vẫn tắt. Không sửa secret/.env hoặc gửi ra ngoài.

**Chưa đóng P7 toàn bộ:** P7.5 mic tiếng Việt thật/độ ồn/latency/cancel cần
bằng chứng thực tế; fixture WebAudio/STT không thay nghiệm thu mic. Telegram
live/private destination chưa nghiệm thu, các adapter Zalo/Slack/WhatsApp chưa
triển khai và không nằm trong local rollout. Không tự kết nối hoặc gửi ra ngoài.
Xem [sổ gate P7](P7-COMPLETION-REGISTER.vi.md).
Bộ20câu và cách nghiệm thu mic: [P7.5 tiếng Việt](P7-VI-VOICE-ACCEPTANCE.vi.md).

## Baseline P6 đã nghiệm thu — giữ nguyên, không triển khai lại

**P6.1–P6.7 hoàn tất code và nghiệm thu local.** P6.5 có Studio/Goal inbox,
delivery UI và recoverable in-app outbox; P6.6 có artifact/derived extractive
learning với provenance, human review và revert; P6.7 có immutable pinned
outcome observations24h/72h/7d và history/stale/insufficient UI.

Full regression1136passed/0failed/0skipped;7browser gatesHTTP thật đạt;
runtime/SSE8/8,lint/typecheck/build20 đạt (Hooks warnings còn ghi nhận).
Clone migration/rollback và populated restore109business tables/hash/pins,
immutable triggers và pending delivery exactly-once ở clone đạt.
Main0046 sau verified backup;104business tables cũ giữ hash,5 bảng mới rỗng;
API/ready/Web200,workerhealthy,contract291/binding khớp,M2replay3/3.
**Các gates runtime chính vẫnfalse**, không bật Meta/write/Telegram/model/tool thật.

Đóng LOCAL không đồng nghĩa đạt production hoặc business: Meta OAuth/M3/live
data, real-model/tool Goal, external delivery và production reboot/failover
vẫn là gate riêng chưa đạt. Outcome synthetic không thay nghiệm thu quảng cáo
thật; causal effect chưa chứng minh. UX catalogs/pending after reload, đầy đủ
attempt history và Hooks warnings còn là backlog, không bắt đầu lại P6 đã đạt.

**Baseline này đã được dùng để triển khai P7**, local-first, không tự kết nối
hoặc gửi qua kênh thật. Xem [báo cáo hoàn tất P6.5–P6.7](P65-P67-LOCAL-ACCEPTANCE-2026-10-10.vi.md)
và [sổ đóng P6](P6-COMPLETION-REGISTER.vi.md).

## Các checkpoint lịch sử — đọc theo thời điểm, không phải việc còn thiếu hiện tại

**Triển khai tổng thể P6 — trạng thái phải đọc trước các checkpoint lịch sử:**
đã chuyển từ bổ sung grant tests sang code mới cho schedules, result inbox,
learning review và action outcomes. Các module mới chưa được coi là toàn bộ
P6.4–P6.7 hoàn tất. **Backend runner P6.3 fixed Echo đã nghiệm thu end-to-end:**
hai vòng/replan/approval/receipt, claimed ARQ cancel, cold worker, restore;
**Goal UI dry-run đã nghiệm thu** tại `/automation/goals`: admission có pins,
hai vòng/approval/child review/replan, mất ACK/retry, hủy và reload/mobile.
Model/tool thật và production vẫn chưa nghiệm thu; không bật gates chính. Xem
[hướng dẫn runner](GOAL-RUNNER.vi.md). Theo dõi tiêu chí đóng
tại [sổ hoàn thiện P6](P6-COMPLETION-REGISTER.vi.md); không chạy lại checkpoint
grant không thay đổi hoặc dùng số tests để thay nghiệm thu chức năng.

**P6.4 persisted Studio schedules LOCAL đã nghiệm thu 10/10:** CRUD/control,
plan/source pins, UTC slot/dedup qua restart interpreter, atomic native admission,
Temporal/ARQ fixed Echo chờ từng approval, UI lifecycle và populated restore.
Full backend1070passed/2skipped, build20pages/runtime8/8/browser thật đạt.
Main0042 sau verified checkpoint;100 bảng cũ giữ hash, schedule/Studio/Goal
executions chính đều0. API/ready/Web200,workerhealthy, gates chính vẫn tắt.
**Backend bounded Goal schedules đã đạt:** shared owner/pins/budgets, atomic
fresh-plan/admission/runner-bound/UTC slot; parent-child/ARQ thật, receipt,
cancel khi gates tắt, concurrency/restart/restore.134focused tests + cron1pass
riêng; không coi full1070 cũ là nghiệm thu adapter mới. Main hiện0043,103 bảng
cũ giữ hash, API/ready/Web200,workerhealthy, M2replay3/3; gates vẫn tắt.
**UI lịch Goal đã nghiệm thu — P6.4 LOCAL đóng cho Studio và bounded Goal:**
preview/pins/budgets/confirmation, create/enable/disable/edit/archive, slot →
parent, reload/retry cùng khóa và gate rollback/mobile390px; browser Goal và
Studio đạt2/2. Không auto approval/model hoặc bật gates chính. Catalog plan
và pending recovery sau reload còn là UX tiếp theo. Bước tiếp theo **P6.5:
nguồn kết quả Goal, delivery UI và outbox recovery**; không làm lại runner/
grant/backend adapter. Chưa đóng toàn P6. Xem
[Studio schedules](P64-PERSISTED-SCHEDULES.vi.md) và
[Goal schedules backend và UI](P64-GOAL-SCHEDULES.vi.md).

**Checkpoint worker replacement của grant trial LOCAL:** Worker instance mới
replay đúng child cũ, nhận cancel đã lưu khi worker tắt; hủy/drain đạt cả khi
gates hoặc quyền đã thu hồi.29 grant/trial tests/runtime8/8 đạt, không consume
lần hai hoặc release ceiling. Đây là shutdown có kiểm soát, không OS crash/
Temporal server restart; chưa Goal kernel end-to-end hoặc restore consumed
grant. **P6 chưa hoàn tất.** Xem
[báo cáo phục hồi worker](P63-GRANT-WORKER-RECOVERY-2026-10-09.vi.md).

**Checkpoint grant → child thử nghiệm LOCAL:** consumption bất biến một lần,
reauthorization tại consume; cha thử nghiệm Temporal tạo child thật bằng ID cố
định, chờ approval rồi hủy/drain.26 grant/trial tests,54 hồi quy (tổng80focused
tests), runtime8/8 và replay đạt; API/ready/Web200, worker healthy. Mất consume
ACK không start. Không phải Goal kernel end-to-end; chưa
live registration, crash/restore hoặc full regression. **P6 chưa hoàn tất.**
Xem [báo cáo thử nghiệm child](P63-GRANT-CHILD-TRIAL-2026-10-09.vi.md).

**Checkpoint first-iteration grant LOCAL:** immutable grant pin approval/claim/
projection/child/deadline/ceiling/backend source; revalidate current authority,
gates và child history, concurrent/retry chỉ một record.73focused tests/runtime8/8
và populated grant restore đạt. Chưa launch/consume, không đổi allow_iteration
cũ hoặc bật live Goal; transport trong ca grant vẫn fixture. **P6 chưa hoàn tất.**
Xem [báo cáo grant](P63-FIRST-GRANT-2026-10-09.vi.md).

**Checkpoint 09/10 — parent Goal dispatcher LOCAL:** leased/ordered/bounded
transport, immutable command/admission checks, current authority, cancel khi
rollback, verify Temporal input/type/queue chống collision và lost-ACK retry.
62focused tests/runtime8/8 đạt; real HTTP/outbox/Temporal/pre-child DB cancel và
replay đạt, không ACK fixture trong ca đó. Chưa mở iteration, đăng ký live
dispatcher/worker hoặc nghiệm thu active-child drain toàn tuyến. **P6 chưa hoàn tất.**
Xem [báo cáo parent dispatcher](P63-PARENT-DISPATCH-2026-10-09.vi.md).

**Checkpoint 09/10 — Temporal child drain LOCAL:** đã nối opt-in bridge với
ARQ ACK thật; kiểm HTTP/outbox→Temporal→activity→ARQ abort→immutable outcome/ACK
và replay, worker absent không tạo ACK giả.51focused tests/runtime8/8 đạt.
Không sửa kernel/history hoặc bật live Goal. Parent Goal end-to-end, full
regression, crash/restart và UI vẫn chưa đạt; **P6 chưa hoàn tất**.
Xem [báo cáo child drain](P63-TEMPORAL-CHILD-DRAIN-2026-10-09.vi.md).

**Checkpoint Goal queue reconciliation LOCAL:** đã nối immutable ARQ cancel ACK
vào entry point đối soát Goal riêng; mọi reserved step cần ACK đúng scope,
native evidence và cancel command. Release một lần, không resume/complete M1;
UNKNOWN/mất quyền vẫn giữ khoản dự phòng.43focused tests/runtime8/8 và hai
populated queue-ACK restore profiles đạt. Parent/Temporal ACK vẫn fixture;
chưa live registration/full regression/end-to-end. **P6 chưa hoàn tất.**
Xem [báo cáo đối soát Goal](P63-GOAL-QUEUE-RECONCILIATION-2026-10-08.vi.md).

**Checkpoint real ARQ cancel LOCAL (fixed Echo):** helper abort/wait và immutable
queue ACK đã được kiểm tra trên pao_test/Redis15; 41 focused tests đạt, gồm 5 case
mới running/queued/absent/mismatched/unserved. Chưa nối live dispatcher, Temporal
cancel hay Goal budget reconciliation; chưa full regression/reload/restore ACK.
Không thay kết quả baseline trước, **P6 chưa hoàn tất**.
Xem [báo cáo queue cancel](P63-QUEUE-CANCEL-LOCAL-2026-10-08.vi.md).

**P6.3B2b2g LOCAL native claimed-cancel fence đã đạt:** verify immutable native
Echo cancellation và bound attempt, release ceiling một lần, không resume/
complete M1.951backend tests không skip/runtime8/8/bốn populated restore profiles
đạt; real ARQ late-finish không đổi cancellation. **Chưa phải real Goal parent/
queue ACK/drain**: proof luôn queue_ack_verified:false, UNKNOWN/partial completed
children vẫn giữ reservation, live Goal worker/UI chưa nối. **P6 chưa hoàn tất.**
Xem [tiến độ B2b2g](P63B2B2G-PROGRESS-2026-10-08.vi.md).

Checkpoint trước:
**P6.3B2b2f LOCAL immutable claim fence đã đạt:** mất TaskAttempt không được
xóa sự thật “đã nhận chạy”, tạo no-effect outcome hoặc mint replacement claim.
931backend cases đã chạy/đạt qua full929 +2real-clock ARQ opt-in, runtime8/8,
populated claim-fence và hai Goal recovery restores đạt. Không thay real
claimed-child ACK/drain hoặc Goal worker/UI. **P6 vẫn chưa hoàn tất.** Xem
[tiến độ B2b2f](P63B2B2F-PROGRESS-2026-10-08.vi.md).

Checkpoint trước:
**P6.3B2b2e LOCAL no-claim cancellation proof đã đạt:** immutable cancel
commands/audits, terminal child và no-claim fence; release reservation một lần,
không resume/complete Goal M1.925backend tests/runtime8/8 và hai populated
recovery restores đạt. Chưa phải real queue drain, cancellation sau claim hoặc
real goal dispatcher/worker/UI. **Toàn bộ P6 chưa hoàn tất.** Xem
[tiến độ B2b2e](P63B2B2E-PROGRESS-2026-10-08.vi.md).

Checkpoint trước:
**P6.3B2b2d LOCAL late-completion recovery đã đạt:** atomic receipt/authority
revalidation và release reservation một lần sau manual-review/deadline; không
resume/complete Goal M1.914backend tests/runtime8/8/populated recovery restore/
live contract254 đạt. Chưa có cancelled-child/absence drain proof hoặc real
goal dispatcher/worker/UI; **toàn bộ P6 chưa hoàn tất**. Xem
[tiến độ B2b2d](P63B2B2D-PROGRESS-2026-10-08.vi.md).

Các checkpoint trước giữ lại làm lịch sử nghiệm thu:
**P6.3B2b2c LOCAL projection iteration1 đã đạt:** running/verified completion/
unmet/budget stop, atomic receipt revalidation +reservation release once;
deadline/unknown giữ ceiling, không tự complete Goal M1.898backend tests,
runtime8/8, populated completion restore và live contract254 đạt. Wrapper vẫn
allow_iteration:false; real goal dispatcher/worker/drain/replan/UI chưa đạt.
**P6.3 và P6 chưa hoàn tất.** Xem [tiến độ B2b2c](P63B2B2C-PROGRESS-2026-10-08.vi.md).

**P6.3B2b2b LOCAL claim/receipt đã đạt:** first-iteration plan ownership,
inert child/reservation và reader kiểm immutable P6.2 outcomes/approval/authority;
871backend tests/runtime8/8, populated receipt restore, Temporal pre-child1/1
và live contract254 đạt. **Chưa phải goal executor**: parent/dispatch ACK vẫn
fixture, projection luôn từ chối iteration, chưa nối live worker/UI; reservation
chưa được giải phóng. **P6.3 và toàn bộ P6 chưa hoàn tất.** Xem
[tiến độ B2b2b và gate tiếp theo](P63B2B2B-PROGRESS-2026-10-08.vi.md).

**P6.3B2b2a LOCAL pre-child đã đạt:** closed/strict DB projection, sequence/
retry/cancel/dispatch provenance;852backend +1Temporal→DB acceptance,
runtime8/8, populated projection restore và live contract254 đạt. Projection
luôn từ chối chạy iteration; chưa đăng ký live worker và chưa có child claims/
trusted receipts/dispatcher. **P6.3 và P6 chưa hoàn tất**. Xem
[tiến độ B2b2a](P63B2B2A-PROGRESS-2026-10-08.vi.md).
**P6.3B2b1 LOCAL đã đạt:** trusted admission provenance và kiểm tra source
Goal/actor/immutable Plan trước decision;827backend tests/runtime8/8,
populated ledger restore và live contract254 đạt. PAO đã khởi động lại sau
phục hồi Docker socket; API/ready/Web200, DB0039. Đây chưa phải goal executor;
**P6.3 và toàn bộ P6 vẫn chưa hoàn tất**. Xem
[tiến độ B2b1](P63B2B1-PROGRESS-2026-10-08.vi.md).
**P6.3B2a LOCAL đã đạt:** admission/command/audit ledger, primary DB0039,
6API gated và Goal/Task guards;808backend tests, runtime8/8, build18pages,
populated ledger restore và live contract254 đạt. Chưa nối goal executor;
**P6.3 và P6 chưa hoàn tất**. Xem
[tiến độ B2a](P63B2A-PROGRESS-2026-10-07.vi.md).
**P6.3B1 kernel LOCAL đã đạt:** Temporal riêng,56focused/full backend786 không
skip, runtime8/8 và source contract248; restart worker/child approval/cancel/
deadline/history replay đạt. Chưa có trusted DB adapters/API/live worker/UI cho goal;
**P6.3 và toàn bộ P6 chưa hoàn tất**. Xem
[tiến độ B1](P63B1-PROGRESS-2026-10-07.vi.md) và
[checkpoint A](P63A-CHECKPOINT-2026-10-07.vi.md).
Baseline hiện tại sau B2b2g reload: API/ready/Web200, worker healthy,
live contract254/source binding khớp, M2archive replay3/3, DB0039;
951backend tests không skip, runtime8/8, bốn populated restore profiles,
P6.2 replay7/7,253synthetic Goal/child histories và idle0 đạt.
Goal admission/execution và live durable flags vẫn tắt.
**P6.2 LOCAL dry-run đã đạt:** DB0038,731tests không skip
(730backend +1HTTP browser),runtime8/8,history replay7/7,build18pages,
bridge fixture restore93business tables,live contract248/M2replay3/3.
Đã có dispatcher, worker opt-in, crash/restarted-ARQ receipt reconciliation,
actual TCP loss/recovery và UI start/approval/reject/cancel qua API thật.
Durable/dispatch/worker/Temporal trên dữ liệu đang dùng vẫn tắt mặc định.
**Không phải model/business execution hoặc production đã đạt.** Echo không gọi
model/Ads/MCP; gate M3realdata, MCP thật và VPS/reboot vẫn chưa đạt.
Xem [nghiệm thu P6.2 cuối](P62-LOCAL-ACCEPTANCE-2026-10-07.vi.md) và
[runbook/drain](P62-RUNBOOK.vi.md). Các báo cáo C1–C3 giữ nguyên như lịch sử checkpoint.
Đây là kế hoạch kèm trạng thái checkpoint, không phải mọi tính năng đã triển khai.
Lượt lập kế hoạch ban đầu chỉ sửa tài liệu; các thay đổi code sau đó được ghi
riêng trong báo cáo nghiệm thu từng checkpoint. P1 có migration additive0025–0028;
không bật connector ghi dữ liệu thật.
**M4.1–M4.5 đã đạt LOCAL ngày07/10/2026:** ledger/outbox cùng transaction,
lease/retry/dedup/receipt, Unified Approval Center, decision/revoke/guardrails và
diagnostics. Migration0037,636backend không skip, runtime8/8, build18pages,
browser/API/ARQ/restore91bảng và live contract/replay3/3 đạt. Ba flags M4 live
vẫn tắt; không mở business writes/P6 runner. M3 dữ liệu thật và production chưa đạt.
Xem [nghiệm thu M4](M4-LOCAL-ACCEPTANCE-2026-10-07.vi.md),
[ADR M4](ADR-M4-DELIVERY-AND-APPROVALS.vi.md) và
[runbook](M4-OPERATIONS.vi.md).
P0.1 đã hoàn tất bản đồ tĩnh và
tài liệu ngày 05/10/2026: [báo cáo P0.1](P01-STRUCTURE-AUDIT-2026-10-05.vi.md),
[snapshot](P01-STRUCTURE-SNAPSHOT-2026-10-05.json) và
[ADR boundaries](ADR-P01-MODULE-BOUNDARIES.vi.md). Chưa refactor code hoặc chạy lại
regression tại P0.1. **P0.2A đã đạt local:**
[extraction reconciliation](P02A-RECONCILIATION-EXTRACTION-2026-10-05.vi.md),
320 backend tests không skip, runtime 8/8, browser 12 routes mock và replay 3/3
artifact M2 cũ. **P0.2B đã đạt local:**
[app factory](P02B-APP-FACTORY-2026-10-05.vi.md), 326 backend tests không skip,
runtime 8/8, browser 12 routes mock, full contract và replay 3/3 đạt sau restart.
**P0.3A.1 đã đạt local:**
[warehouse scheduler](P03A1-WAREHOUSE-SCHEDULER-2026-10-05.vi.md), 329 backend
tests không skip, runtime 8/8, browser 12 routes mock, full contract và replay
3/3 đạt sau restart. **P0.3A.2 đã đạt local:**
[report scheduler](P03A2-REPORT-SCHEDULER-2026-10-05.vi.md), 332 backend tests
không skip, runtime 8/8, browser 12 routes mock, full contract và replay 3/3 đạt.
**P0.3A.3 đã đạt local:**
[Telegram helpers](P03A3-TELEGRAM-HELPERS-2026-10-05.vi.md), 336 backend tests
không skip, runtime 8/8, browser 12 routes mock, full contract/replay 3/3 đạt.
P0.3A đạt phạm vi scheduler/helper boundary; tại checkpoint đó P0 còn dở. Telegram
ingest/collect/deliver/router vẫn chung module, không tuyên bố sạch HTTP toàn stack.
**P0.3B.1 đã đạt local (khảo sát/tests, chưa extraction Task):**
[Task characterization](P03B1-TASK-CHARACTERIZATION-2026-10-05.vi.md), 345 backend
tests không skip, runtime 8/8, contract/replay 3/3 đạt; backend source không đổi.
Ghi nhận progress khi tạo completed chưa normalize, ORM default cũ và lock-order
risk; chưa sửa lỗi trong checkpoint khảo sát.
**P0 LOCAL đã đạt theo lát cắt/gate hiện hành ngày05/10/2026:**
[nghiệm thu P0](P0-LOCAL-ACCEPTANCE-2026-10-05.vi.md). P0.3B.2 Task values,
P0.3C run state/tool audit, P0.4 evidence catalog/UI và P0.5 local operations/CI/
backup đã kiểm. Kết quả cuối:366 backend không skip, runtime8/8, browser12routes
mock, TypeScript/build18pages và live contract/replay3/3 đạt.
**P0 PRODUCTION chưa đạt:** chưa VM/VPS reboot drill, service/24-7 và cold restore;
GitHub CI chưa remote run. Người dùng chọn ghi pending, không reboot host đang dùng.
**P1 LOCAL MVP đã đạt ngày06/10/2026:** P1.1–P1.5 Brain scopes/CRUD/session pin,
Files text/Markdown, Notes/version/trash và portable snapshot import/export.
424 backend tests không skip, runtime8/8/TypeScript, build18pages, real browser
với test API và byte-exact backup/restore đạt. Local revision0028/Brain flag bật,
live contract160operations/replay3/3 đạt. PDF/images và RAG chưa triển khai;
không coi đây là Brain production đầy đủ. P2 đã được người dùng cho phép ngày06/10:
**P2.1 Sources/ingestion đã đạt LOCAL**:446backend không skip, runtime8/8,
build18pages, real API/ARQ/browser/fixture restore, local0029/live contract171/
old replay3/3 đạt. **P2.2–P2.6 đã đạt text/Markdown LOCAL MVP**:464backend không
skip, runtime8/8/TypeScript, production build18pages, browser/API/ARQ/SSE và
fixture restore80tables đạt; local0030/Knowledge flag bật, full contract195 và
replay3/3 đạt sau restart. P3–P8 chưa mở. Chat có opt-in grounded excerpts, không
LLM synthesis. Model embedding thật chưa cài; full-text fallback đã kiểm.
Xem [P2 nghiệm thu](P2-LOCAL-ACCEPTANCE-2026-10-06.vi.md) và
[ADR P2](ADR-P2-KNOWLEDGE-WORKSPACE.vi.md).
Xem [P2.1 tiến độ](P21-SOURCE-INGESTION-2026-10-06.vi.md).

**P3.1 đã đạt LOCAL MVP ngày06/10/2026:** engine adapter contract/capabilities,
session model pin và immutable run snapshot, no implicit fallback, bộ chọn model
chat; migration0031/engine flag local bật sau489backend không skip, runtime8/8,
production build18pages, browser/API/ARQ/SSE và fixture restore. Live API/Web200,
worker healthy, old M2 replay3/3; actual Ollama text smoke đạt (chậm khoảng29–35s,
không phải benchmark tối ưu). Đây là gate lịch sử trước khi làm P3.2–P3.7.
**P3.1–P3.7 hiện đã đạt LOCAL MVP ngày06/10/2026:** context compiler/privacy,
extractive compaction/trace, commands, search/pin/group/export/retry và usage
ledger/local concurrency cap. Full514backend không skip +74focused mới nhất,
runtime8/8/TypeScript/build18pages, real browser/restore, paired Ollama corpus
và actual planner/final tổng hợp đạt. Local0032/chat flag bật; live200/worker
healthy/old replay3/3 đạt. Xem [nghiệm thu P3](P3-LOCAL-ACCEPTANCE-2026-10-06.vi.md)
và [ADR P3](ADR-P3-CONTEXT-CHAT-USAGE.vi.md). M4/production vẫn chưa mở.
Xem [P3.1 nghiệm thu](P31-LOCAL-ACCEPTANCE-2026-10-06.vi.md) và
[ADR P3.1](ADR-P31-ENGINE-CONTRACT.vi.md).
Xem [nghiệm thu P1](P1-LOCAL-ACCEPTANCE-2026-10-06.vi.md).
Xem [P1 progress](P1-PROGRESS-2026-10-06.vi.md) và [Brain ADR](ADR-P11-BRAIN-SCOPES.vi.md).
Các lần move toàn models/graph/Attempts/bridge và lỗi Task chưa được đánh dấu xong.

Ngày lập: 23/09/2026; hoàn thiện 24/09/2026. Nội dung đối chiếu ban đầu là lịch sử.
Trạng thái hiện hành: M0 và M1 đã đạt local ngày 29/09; môi trường PAO-ACOS
độc lập đạt ngày 05/10/2026. **M2 đạt local theo gate roadmap ngày 05/10/2026**;
M3–M8 business/production chưa nghiệm thu; M4 foundation LOCAL đã đạt như trên. Xem
[baseline hiện hành](ACOS-INDEPENDENT-BASELINE-2026-10-05.vi.md).
Checkpoint mới: [Skill Registry foundation](STAGE-4-SKILL-REGISTRY-FOUNDATION-2026-10-05.vi.md).
Checkpoint kế tiếp: [Business brief chỉ đọc](STAGE-4-BUSINESS-BRIEF-PREVIEW-2026-10-05.vi.md).
Checkpoint hiện hành: [Chief routing và Gateway](STAGE-4-CHIEF-SKILL-ROUTING-2026-10-05.vi.md).
Checkpoint mới nhất: [Ads/creative read tools](STAGE-4-ADS-CREATIVE-READ-TOOLS-2026-10-05.vi.md).
Checkpoint tiếp theo đã đạt: [Ba Chief command workflows](STAGE-4-THREE-SKILL-COMMANDS-2026-10-05.vi.md).
Nghiệm thu hiện hành: [M2 local có điều kiện](M2-LOCAL-ACCEPTANCE-2026-10-05.vi.md).
Checkpoint recovery: [OS-process kill với clock lease test](M2-PROCESS-RECOVERY-2026-10-05.vi.md).
Checkpoint mới nhất: [Guard tương thích executable](M2-VERSION-GUARD-2026-10-05.vi.md).
Checkpoint attribution: [Wrapper và API preview chỉ đọc](M2-ATTRIBUTION-READ-2026-10-05.vi.md).
Checkpoint UI hiện hành: [Attribution preview trên Skills](M2-ATTRIBUTION-UI-2026-10-05.vi.md).
Checkpoint recovery thực: [ARQ/Redis với real lease clock](M2-ARQ-REDIS-RECOVERY-2026-10-05.vi.md).
Nghiệm thu M2 cuối: [M2 local hoàn tất](M2-FINAL-ACCEPTANCE-2026-10-05.vi.md).

## 1. Nguồn và giới hạn

- Cuộc trò chuyện [Tổng hợp dự án PAO](https://chatgpt.com/g/g-p-6aa9537fa7388191a3fd99a6bd6031df-pao-ai-chief-of-staff/c/6ab28e0e-6884-83ec-8176-4dc63da25d3e), Master Project Summary cập nhật 22/09/2026. Công cụ đọc được các mục I–XXIV; phần cuối bị cắt từ bảng mục XXV. Không suy đoán các quyết định chưa đọc được.
- Đối chiếu trực tiếp `models.py`, `agents.py`, `tool_registry.py`, `automation.py`, `automation_api.py`, `automation_workflows.py`, `ads_actions.py`, `ads_policy.py`, cấu hình agent và `PaoConsole.tsx`.
- [Checklist hệ thống](SYSTEM-CHECKLIST-2026-09-23.vi.md) và bằng chứng nghiệm thu local đã tạo trong lượt trước. Các số 156 backend tests, 8 runtime tests, 83 OpenAPI paths là kết quả của lượt kiểm tra trước; lượt lập kế hoạch này không chạy lại hệ thống.
- Các nhận định trong bản ChatGPT về license, bảo mật, tính năng hoặc tình trạng repository bên ngoài chưa được xác minh lại. Chúng là đầu mối nghiên cứu, không phải căn cứ để cài đặt hoặc chọn dependency.

## 2. Kết luận kiến trúc

PAO hiện có backend riêng dựa trên FastAPI, PostgreSQL/pgvector, Redis/ARQ, Temporal và Ollama. Đây là tài sản cần tiếp tục phát triển. Chưa có lý do kỹ thuật đủ mạnh để thay runtime bằng Javis hoặc OpenJarvis. Nếu sau này cần một capability từ các dự án đó, đánh giá một adapter nhỏ trên checkout/commit xác định, kiểm tra license và quyền truy cập trước; không đưa hai hệ thống điều phối cùng sở hữu task.

Master Summary là tầm nhìn rộng hơn Phase 0–18 đã làm. Hoàn thành các phase local không đồng nghĩa hoàn thành Business OS. Giữ nguyên lịch sử Phase 0–18; dùng các mốc M0–M8 bên dưới để không nhầm với roadmap Phase 0–6 trong Master Summary.

Ưu tiên tự host và local theo yêu cầu trực tiếp của người dùng. Cloud reasoning chỉ là lựa chọn tương lai, tắt mặc định và cần cấu hình/chấp thuận riêng. Nhiều vai trò agent có thể dùng chung một model local tuần tự; phân quyền và chất lượng đánh giá quan trọng hơn số lượng model.

## 3. Đã có, có một phần và chưa có

Bảng dưới là inventory lịch sử sau M1/M2, trước các acceptance P0–P7; không
dùng những mục “chưa có” ở đây để bắt đầu lại module đã đạt. Ma trận audit hiện
hành có nguồn/evidence/gate trong [kế hoạch đồng bộ 11/10](PAO-UNIFIED-DEVELOPMENT-PLAN-2026-10-11.vi.md).
“Có code” không đồng nghĩa “đã bật local” hoặc “đã nghiệm thu dữ liệu thật”.

| Nhu cầu trong Master Summary | Hiện trạng có bằng chứng | Phần cần bổ sung |
|---|---|---|
| PAO Chief và delegation | Năm vai trò, planner có giới hạn; M1 có goal/task/dependency/attempt; M2 có ba command skill | Chief tự theo đuổi goal dài hạn, replanning có giới hạn và UI tự tạo agent |
| Task engine | M1 đạt local: task độc lập hội thoại, dependency, attempt, evidence, retry/state machine | Workflow authoring và lịch chạy dùng cùng task service, không tạo engine task thứ hai |
| Business-agent taxonomy | Có năm cấu hình agent; không phải mọi node Orb đều thực thi | CRM/BI/Engineering chỉ bổ sung khi có dữ liệu, tools và evaluation tương ứng; Sales/Finance/Operations chưa có |
| Skill Router | M2 đạt local: ba manifest được duyệt, command router, schema/quyền/budget, version/hash và result replay | Skill Studio draft/review/publish, slash commands, lazy context; LLM skill chưa được mở |
| Tool Gateway | Có schema/agent allowlist, durable call/audit và business SELECT-only tools; email/calendar mô phỏng | MCP adapter read-only và connector catalog/connection health thật; coding executor có scope riêng |
| Memory | Scoped semantic facts, embeddings, extraction, conflict, opt-out; working context có giới hạn | Knowledge/SOP/document ingestion có nguồn/version; episodic decision/outcome và business profile |
| Operational state | Các bảng có cấu trúc cho run, sync, Ads, approval, policy, automation | API tổng hợp context nghiệp vụ; không sao chép trạng thái quan trọng sang vector DB làm nguồn chính |
| Telegram | Có implementation/tests whitelist, task/result, cancel/approval; ACOS hiện không bật bridge thật | Channel adapter chung, kiểm kết nối/delivery thực trên ACOS; không lấy nghiệm thu bot ở môi trường cũ làm bằng chứng hiện tại |
| Meta/Google Ads | Connector, normalized warehouse và reporting đã có code/API/UI | OAuth và đối chiếu account thật, dữ liệu thiếu/trễ, currency/timezone, quota |
| TikTok Ads | Chưa có connector | Một integration read-only riêng, chỉ sau khi Meta và Google ổn định |
| Creative Intelligence | Metadata, fatigue đa tín hiệu, learnings/brief | Đối chiếu dữ liệu thật; chưa có sản xuất creative hoặc launch tự động |
| CRM/Attribution | Nguồn normalized, lead/stage/order và deterministic attribution | CRM làm việc đầy đủ, adapter vendor, hoạt động sales, repeat purchase/LTV/profit |
| Approval/Policy/Audit | Tool, Ads và Temporal có cơ chế riêng; Ads có worker recheck | Contract và timeline dùng chung; không vội hợp nhất mọi bảng hoặc thay enforcement domain |
| Event-driven OS | RunEvent/SSE, ARQ dispatch, các outbox theo module | Business event envelope, transactional outbox, consumer dedup/retry/dead letter |
| Temporal | Approval signal, timer và projection cơ bản | Chuỗi task nghiệp vụ, thực thi thật sau wait, recovery và fault/replay tests |
| Learning loop | Creative learnings và business metrics riêng | Action → outcome 24h/72h/7d → evaluation → lesson có nguồn; đề xuất thay đổi cần review |
| Executive UI | Next.js có routes theo module, shell/task board/Skills preview và replay; M2 browser 12 routes đạt | UX files/brains/studio/inbox/usage, accessibility và consolidated approval timeline; không xây lại shell đã có |
| Voice | VAD, local STT/TTS, interruption | Microphone thật, độ chính xác tiếng Việt, latency và voice phù hợp |
| Vận hành | ACOS riêng, idle/PID gate, health, backup/restore 65 bảng và skill artifacts; recovery test DB/Redis riêng | Supervisor/reboot, CI, retention, metrics, load/network-loss/production acceptance |
| Brain và documents | Memory facts theo user/workspace/brand, semantic retrieval; chưa phải kho tài liệu đầy đủ | Brain metadata, sources/wiki/notes, source version/citations và quản lý files |
| Engines/context/usage | Ollama và bốn API provider trong code, gateway theo workspace; fast path shadow | Session model pin, capability matrix, context compiler, usage thật/ước tính/quota tách riêng |
| MCP/plugins/channels/coding | Không có bằng chứng nghiệm thu hệ plugin/MCP/coding tương đương Javis | P5, P7, P8; API key có mặt không đủ để đánh dấu adapter đã hoạt động |

## 4. Những kết luận cũ cần thu hẹp

1. Nhận định Phase 17 là lịch sử trước M0; không dùng smoke ID không tồn tại làm bằng chứng business workflow. M0 local có báo cáo riêng; nghiệm thu Ads/CRM end-to-end trên dữ liệu thật vẫn thuộc M3.
2. Các rủi ro Temporal start/commit, approval/version, request fingerprint và cancel/timer được nhận diện trước M0. Khi refactor cần giữ regression M0, không mô tả tất cả là lỗi hiện hành chưa sửa; production recovery vẫn cần bằng chứng mới.
3. Multi-agent acceptance chứng minh orchestration, chưa chứng minh câu trả lời đúng. Artifact Phase 4 nói không tính được tỷ lệ chuyển đổi vì thiếu doanh thu, là giải thích sai. Với 100 lượt xem/5 đơn chỉ có thể nêu tỷ lệ đơn/lượt xem 5% nếu cùng phạm vi và có quan hệ phù hợp; không gọi đó là click-to-conversion CVR khi thiếu số click. Cần evaluation theo định nghĩa metric, không chỉ kiểm output có chữ/số.
4. Các bảng CRM ingestion chưa tương đương CRM vận hành đầy đủ. Creative learnings chưa tương đương learning loop sau hành động. Daily Ads report chưa tương đương Daily Chief Brief tổng hợp doanh nghiệp.
5. Database/volume `apex` thuộc môi trường nguồn lịch sử. Target hiện hành là PAO-ACOS riêng, database pao_acos_local, revision 0024; không rename/drop/copy secret từ môi trường nguồn.

## 5. Kiến trúc đích kế thừa PAO

```text
Web / Telegram / Voice
          ↓
Chief + Goal/Task service
          ↓
Skill Router → Specialist registry
          ↓
Policy check → Approval khi cần → Execution Gateway
          ↓
Business services / MCP adapters / isolated Engineering executor
          ↓
Result + evidence + domain audit + business events
          ↓
Outcome evaluation → proposed lesson → curated business memory
```

- PostgreSQL sở hữu goal/task, quyền, quyết định và business records. Temporal sở hữu lịch sử thực thi dài hạn; bảng projection phục vụ UI, có reconciliation.
- ARQ tiếp tục job ngắn đang có. Temporal điều phối wait/dependency dài hạn; không tạo thêm một scheduler cạnh tranh cho cùng job.
- Các phép tính KPI dùng code xác định; LLM diễn giải và lập đề xuất trên dữ liệu có nguồn.
- Áp dụng policy trước tool call và kiểm lại tại worker. Skill hoặc MCP tool không tự cấp quyền.
- Một `correlation_id` xuyên suốt goal/task/run/action/audit/event; không ghi secrets hoặc private chain-of-thought vào audit.
- Trước mắt dùng PostgreSQL outbox + worker hiện có, chưa cần Kafka hay microservice mới. Chỉ tách dịch vụ khi có đo lường và nhu cầu cụ thể.

## 6. Lộ trình triển khai tuần tự

Mỗi mốc có migration/rollback phù hợp, contract, UI tối thiểu và acceptance riêng.
M0–M8 giữ ID để không mất lịch sử. P0–P8 ở mục 11 là checkpoint nền tảng mới,
không renumber M. Không khởi công mốc phụ thuộc khi gate trước chưa đạt; không
triển khai nhiều bước cùng lúc. Phần Brain/UX không phụ thuộc account Meta có thể
được chọn trong lúc M3 chờ credentials, nhưng không coi đó là vượt gate M3/M4.

### M0 — Ổn định nền tảng và chốt contract

Phụ thuộc: code Phase 0–18. Đây là bước nền tảng trong lộ trình lịch sử; trạng thái nghiệm thu hiện tại được ghi ở đầu tài liệu.

**Trạng thái 29/09/2026: Đạt local.** Bằng chứng, giới hạn và bộ test nằm tại
[STAGE-2-STABILITY-RESULT-2026-09-29.vi.md](STAGE-2-STABILITY-RESULT-2026-09-29.vi.md).

- Ghi ADR về quyền sở hữu DB/Temporal/ARQ, cấu trúc task, event và permission; lưu baseline source có thể phục hồi.
- Tái hiện các tình huống race của Temporal ở mục 4 trên DB/namespace test; sửa atomic dispatch bằng outbox và idempotent reconciliation, approval locking, full request fingerprint, interruptible timer và failure projection.
- Nghiệm thu workflow có row thật: API create → waiting → UI/Telegram decision nếu được hỗ trợ → completion → audit; kill/restart worker và server giữa wait, không mất hoặc nhân đôi việc.
- Restore backup vào DB tách biệt; kiểm tra cả dữ liệu PAO và chiến lược backup Temporal; thêm health worker/bridge, phục hồi lock và hướng dẫn khởi động sau reboot.
- Tạo evaluation fixtures cho metric, thiếu dữ liệu, mâu thuẫn và từ chối tool không được phép. Tách điểm correctness khỏi completion.

Điều kiện đạt: test crash/race/replay/restore có bằng chứng; không báo task hoàn tất khi kết quả nghiệp vụ chưa tồn tại; không làm mất các kiểm thử Phase 0–18. Khi lỗi, có thể tắt Temporal bằng gate và tiếp tục chat/ARQ hiện tại.

### M1 — Goal và Task nghiệp vụ

Phụ thuộc: M0.

**Trạng thái 29/09/2026: Đạt local.** Bằng chứng và giới hạn nằm tại
[STAGE-3-GOALS-TASKS-RESULT-2026-09-29.vi.md](STAGE-3-GOALS-TASKS-RESULT-2026-09-29.vi.md).

- Bổ sung tối thiểu `goals`, `tasks`, `task_dependencies`, `task_attempts`; liên kết Run/AgentRun thay vì nhân bản lịch sử output.
- Goal: mục tiêu, owner/workspace, deadline, success criteria, status. Task: parent/goal, agent/skill, input references, budget, dependency, trạng thái, evidence/result reference.
- State machine: draft → ready → running → waiting_approval/blocked → completed/failed/cancelled; quy định rõ người được chuyển trạng thái. Retry tạo attempt mới.
- API `/v1/goals`, `/v1/tasks` và UI task board đã có sau M1; mở rộng phải dùng lại contract hiện hành. Telegram status/task cần gate channel thực trên ACOS.
- Goal completion dựa trên tiêu chí và kết quả của task bắt buộc, không chỉ lời khẳng định của Chief.

Điều kiện đạt: tạo mục tiêu có ba task phụ thuộc, resume sau restart, hủy không khởi chạy task con, retry không tạo side effect trùng, workspace isolation, xem được evidence từng bước.

### M2 — Skill Registry và business tools

Phụ thuộc: M1.

**Trạng thái: Đạt local 05/10/2026.** Backend 298/298, runtime 8/8,
frontend build 18/18, live commands/Skills/replay và browser 12 routes đạt.
Migration 0024 và restore 65 bảng/3 archives đạt; không credential thật.
Replay là đọc kết quả lịch sử đúng snapshot/version, không rerun executable
hoặc tool cũ; xem [ADR replay](ADR-M2-RESULT-REPLAY.vi.md) và
[nghiệm thu cuối](M2-FINAL-ACCEPTANCE-2026-10-05.vi.md).
Các checkpoint dưới đây là lịch sử triển khai, không thay kết luận hiện hành.

Checkpoint 05/10/2026: đã có ba manifest, catalog/preflight có kiểm quyền,
pin version/hash/schema vào TaskAttempt và evaluator cấu trúc đầu ra.
Đã nối hai wrapper SELECT-only cho task và báo cáo Meta đã lưu qua endpoint
preview có RBAC, transaction chỉ đọc và giới hạn thời gian. Hai wrapper này
đã vào durable Tool Gateway và Chief command router v1 (chỉ câu lệnh rõ ràng,
không phải hiểu ngôn ngữ tự do). Đã bổ sung intelligence/creative read tools
và analysis-preview theo account/kỳ. Chief command router v1.1 đã phối hợp
hai tool cho từng skill trong cả ba skill đầu; KPI Ads giữ account scope.
Nghiệm thu local 05/10: routing/input/allowlist/scope, nguồn và giá trị unknown,
hủy/mất quyền giữa hai tools, lỗi provider và quan sát dispatcher đều đạt.
Resource guard command đã đạt checkpoint: timeout lấy từ snapshot và không
vượt run timeout; tối đa hai tools, response tối đa 32000 ký tự. Hết budget
phải failed, không cắt đầu ra rồi báo success. Backend 243/243, runtime 8/8;
xem [báo cáo resource guard](M2-RESOURCE-GUARD-2026-10-05.vi.md).
Đã kiểm OS-process kill/fresh-process recovery trên pao_test: sau tool đầu
hoặc khi đang đọc, run failed, không thêm/retry call và không success giả.
Clock lease được mô phỏng, không phải nghiệm thu toàn stack ARQ/Redis hoặc
recovery latency thật. Backend checkpoint này 245/245.
Đã pin exact-backend-source binding vào snapshot/business tool calls; chặn
khác/thiếu binding ở execution/evaluator và không tự resume pinned run. Backend
checkpoint version guard 254/254; đây không phải archive/replay executable cũ.
Đã kiểm ARQ/Redis thật với pao_test/Redis15/queue riêng, timeout test 10s:
ngắt giữa tools recovery 72.69s, ngắt trong read 96.83s; không clock mock hoặc
DB timestamp sửa tay. Regression opt-in 267/267. Đây là fail-closed recovery,
không resume job; không nghiệm thu mất Redis server/mạng hoặc latency cấu hình
production. Checkpoint tiếp theo đã dùng effective timeout trong pinned plan
cho cleanup; restart worker với global timeout 120s vẫn dùng pin 10s của job cũ.
ARQ thực: 75.89s giữa tools, 96.92s trong read; backend 284/284, runtime 8/8,
live ba commands và browser Skills đạt. Xem
[báo cáo pinned recovery](M2-PINNED-RECOVERY-DEADLINE-2026-10-05.vi.md).
Checkpoint cuối đã lưu artifact và replay kết quả versioned, có hash/scope/source
guard. Recovery production/HA và executable resume không được khẳng định đã đạt.
Wrapper attribution đã nối Gateway và explicit skill API preview (manifest
Ads 1.1.0); chỉ đọc snapshot, luôn insufficient_data. UI Skills đã có explicit
attribution preview, bảng nguồn/unknown/currency và bảo vệ response muộn.
Chưa tự ghép vào command plan hai tools; chưa kiểm chứng doanh thu doanh nghiệp.
Command khóa mode deterministic_read_only, 0 generated tokens; LLM skill mode
không được nạp/thực thi. Token metering cho LLM skill tương lai cần gate riêng,
không phải tính năng M2 hiện tại. Preview vẫn dùng timeout riêng 10 giây và SQL
statement timeout 8 giây.

- Manifest versioned gồm ID/version, intent, schemas, allowed agents/tools, permission, approval class, timeout/token budget và evaluator. Nội dung workflow lưu theo skill; không nhét toàn bộ vào system prompt.
- Chỉ nạp skill được quản trị duyệt; version/hash được ghi trong attempt. Không tự tải/chạy code từ SKILL.md bên ngoài.
- Bổ sung wrapper read-only quanh các service PAO hiện có cho intelligence/report/creative/attribution; cùng RBAC và giới hạn dữ liệu, tránh Chief gọi DB tùy ý.
- Ba skill đầu: `daily-business-brief`, `investigate-ads-drop`, `creative-fatigue-review`.

Điều kiện đạt: Chief chọn đúng skill cho bộ câu hỏi chuẩn; từ chối input/tool không hợp lệ; thiếu connector/dữ liệu phải trả trạng thái thiếu và hướng dẫn cụ thể; replay giữ đúng skill version.

### M3 — Nghiệm thu dữ liệu thật và Chief Brief

Phụ thuộc: M2; cần Meta account/OAuth trên máy. Nếu chưa có credential, chỉ hoàn thiện fixture/adapter và đánh dấu blocked ở nghiệm thu ngoài.

**Đã bắt đầu M3.1 local:** [công cụ đối soát read-only](M3-RECONCILIATION-FOUNDATION-2026-10-05.vi.md)
so totals nhập với saved report có scope, không sync hoặc xác thực file export.
Readiness ban đầu M3.1: Meta disabled, chưa có App/OAuth/connection/report local.
Ngày07/10 owner đã cấu hình App local bằng khóa mới ngoài chat; Meta read enabled,
write/Autopilot tắt, chưa có connection/report. [Cấu hình App trong Settings](META-APP-SETTINGS-2026-10-07.vi.md)
đã đạt local:655backend, focused40, runtime8/8, build18, browser temp-config và
live contract/replay3/3. Chỉ thêm hai API, không migration; revision0037 giữ nguyên.
M3 thật vẫn chưa đạt; cần OAuth và chọn account/kỳ/export. Cấu hình UI còn giới hạn
owner của bản cài local một workspace, không tuyên bố đã đạt quản trị remote/multi-tenant.

- Meta read-only một account trước, khoảng 7 ngày rồi 30 ngày; đối chiếu spend/click/conversion theo timezone/currency/attribution với export chính thức.
- Nhập CRM/orders đã chuẩn hóa và kiểm tra dedup/unattributed/freshness. Google account riêng chỉ triển khai nghiệm thu sau Meta đạt.
- Brief tổng hợp KPI, coverage, bất thường, task quá hạn và approval đang chờ; số liệu đọc từ business services, có source và timestamp.
- Luồng đầu tiên: “kiểm tra doanh thu Meta Ads tuần này giảm” → goal/tasks → metrics/creative/CRM → evidence → đề xuất → tạo draft action ở dry-run. Không tự bật live write.
- Telegram scheduled delivery chỉ bật theo lịch/người nhận do người dùng cấu hình rõ ràng; có dedup, timezone và opt-out.

Điều kiện đạt: đối chiếu số liệu cùng phạm vi, mọi nhận định định lượng truy về nguồn, không suy luận doanh thu thiếu thành 0, retry không gửi brief trùng. Trạng thái thiếu dữ liệu là kết quả hợp lệ; không bịa nguyên nhân.

### M4 — Business events và phê duyệt xuyên module

**User đã cho phép tiếp tục M4 ngày07/10/2026; M4.1–M4.5 đạt LOCAL.**
Ledger/outbox/receipt, producer3profiles, lease/fencing/retry/dedup, inbox có
snapshot ký, decision/revoke/domain executor guards và diagnostic/UI đã kiểm.
636backend không skip, runtime8/8, build18pages, browser/API/ARQ/restore91bảng,
clone0035→0037→0035→0037/hash90bảng cũ và live contract/replay3/3 đạt sau restart.
Local0037; cả3flags producer/delivery/unified approvals vẫn false trên vận hành.
Xem [nghiệm thu M4](M4-LOCAL-ACCEPTANCE-2026-10-07.vi.md),
[ADR](ADR-M4-DELIVERY-AND-APPROVALS.vi.md), [runbook](M4-OPERATIONS.vi.md)
và [nghiệm thu M4.1](M41-LOCAL-ACCEPTANCE-2026-10-07.vi.md).
M3 dữ liệu thật chưa đạt: chỉ chuẩn bị nền tảng local/fixture, chưa nghiệm thu
business, không mở writes/P6 runner hoặc bỏ qua dependency.

Phụ thuộc: M3.

- Event envelope: event_id/type/schema_version/workspace/aggregate/version/correlation/causation/time/payload reference; ghi outbox cùng transaction business state.
- Worker delivery at-least-once, consumer dedup, bounded retry và dead letter; tenant filter, ordering theo aggregate khi cần. SSE là giao diện hiển thị, không thay event ledger.
- Unified Approval Center đọc qua adapter Tool/Ads/Task; giữ domain guardrails hiện có. Approval gắn actor, immutable input hash, version, expiry và scope; permission recheck ở executor.
- Bắt đầu với `task.completed`, `approval.requested`, `ads.analysis.completed`; tránh mọi event đều gọi LLM.

Điều kiện đạt: event lặp không tạo task/action/delivery trùng; concurrent approve/reject chỉ một quyết định có hiệu lực; policy đổi hoặc mất quyền trước execute bị chặn.

### M5 — Business memory và Outcome Learning

Tách phụ thuộc để không chặn kho tri thức khi chưa có Ads: **M5A = Brain/SOP/
documents (P1–P2), phụ thuộc P0 và M1/M2**; **M5B = Outcome Learning (P6), phụ
thuộc M3, M4 và M5A**. M5A đạt không đồng nghĩa M5 toàn bộ đã đạt.

- Business profile/SOP/source documents có provenance/version, access scope và retention; index vector là bản dẫn xuất.
- Decision/outcome records liên kết action + before/after + cửa sổ đánh giá 24h/72h/7d + freshness + confounders; timer do Temporal quản lý.
- Tách status thực thi kỹ thuật khỏi kết quả kinh doanh. Hiệu suất tăng sau action không tự chứng minh quan hệ nhân quả.
- Lessons được đề xuất, review rồi mới dùng làm knowledge. Không tự sửa policy/prompt/code production.

Điều kiện đạt: scheduled evaluation sống qua restart, thiếu dữ liệu trả insufficient_data, bài học truy về nguồn; người dùng sửa/xóa được knowledge theo scope.

### M6 — Executive UI

UI tối thiểu triển khai cùng từng checkpoint P/M, dùng shell hiện có. M6 là đợt
hợp nhất Executive UI sau khi các contract cần dùng ổn định, không chặn mọi cải
tiến chat/knowledge đến khi M5 hoàn tất. Không thay Next.js bằng dashboard Javis.

Đề xuất 12 mục: Overview; Chief; Goals & Tasks; Agents & Skills; Meta Ads; Google Ads; TikTok Ads; CRM & Revenue; Creative; Approvals; Automation; Knowledge. Settings, Voice và Integrations là mục tiện ích riêng. Live Events nằm trong timeline task và trang vận hành. Đây là đề xuất, không coi danh sách trong Master Summary đã được chốt.

- Tái sử dụng các panel/API hiện có; route theo domain và tải dữ liệu khi mở module, không fetch tất cả trên một màn hình.
- TikTok hiển thị chưa kết nối/chưa triển khai, không dựng dữ liệu giả làm tính năng thật.
- Dashboard hiển thị coverage, stale data và pending work; Orb là thành phần hỗ trợ.

Điều kiện đạt: navigation/bookmark hoạt động, session/task state không mất khi đổi tab, mobile/RBAC/empty/error state đạt; không buộc thay toàn bộ thư viện frontend chỉ để giống stack đề xuất.

### M7 — MCP và Engineering executor

Tách **M7A = MCP read-only (P5)**, phụ thuộc P0/P3/P4 và gateway/RBAC M2;
**M7B = Engineering executor (P8)**, phụ thuộc M4, P5 và sandbox/restore/evaluation.
M7A không được mở tool write, shell hoặc tự triển khai M4. M7B cần xác nhận riêng.

- MCP adapter đầu tiên chỉ cho một server/tool read-only được cấu hình, schema allowlist, timeout, result cap và audit; permission PAO vẫn là authority.
- Engineering execution request có repo/path scope, task, acceptance, runtime/model choice, network policy và budget. Đánh giá Codex adapter bằng tài liệu chính thức tại thời điểm triển khai; không giả định gói ChatGPT đồng nghĩa quyền sử dụng API/cloud miễn phí.
- Chạy trong checkout/workspace tách biệt, credential tối thiểu; đầu ra là diff, test evidence và review artifact. Merge/deploy tách khỏi coding attempt và cần policy/approval riêng.
- Không nhập unrestricted shell hoặc runtime Javis/OpenJarvis nguyên khối. Cloud executor là tùy chọn, không bắt buộc cho PAO local.

Điều kiện đạt: task thử chỉ sửa repo được cấp, không đọc secret ngoài scope, cancel/timeout hoạt động, retry không nhân đôi thao tác; review trước merge/deploy.

### M8 — Mở rộng có điều kiện

Phụ thuộc: M3–M5 đã dùng ổn định; mỗi nhánh là một dự án nhỏ nghiệm thu riêng.

- TikTok read-only dùng warehouse chung sau kiểm tra quyền/API/license hiện hành.
- CRM/Sales nghiệp vụ, LTV/profit cần dữ liệu khách hàng/order/refund/cost và định nghĩa metric trước.
- Email/calendar thật, competitor research, content production có skill và approval riêng.
- Limited Autopilot chỉ mở sau dữ liệu thật, dry-run, outcome evaluation, fault tests và emergency controls đạt; phải có phê duyệt cụ thể cho account/phạm vi hành động.

## 7. Phạm vi triển khai đầu tiên đề xuất

M0/M1/M2 đã đạt local. M3.1 đã có preview đối soát, M3 thật chờ account/OAuth/
export. **P0.1 inventory và module boundaries đã hoàn tất về tài liệu**, chưa
move file trong P0.1. P0.2A extraction reconciliation có shim đã đạt local.
Bước vừa đạt là **P4.1–P4.6 Agent/Skill/Workflow Studio LOCAL MVP**: xem
[acceptance P4](P4-LOCAL-ACCEPTANCE-2026-10-06.vi.md); full backend549 và final
focused62 đạt, Studio đã bật local. **Bước kế tiếp đề xuất: P5 Connector/MCP
read-only**, cần xác nhận riêng; không tự mở M4 hoặc workflow execution P6.
P2.2–P2.6 chunks/citations, scoped retrieval, Wiki review và graph/attachments
đã đạt local text/Markdown. Knowledge/Engine flags đã bật sau gate local;
P1 local MVP đã đạt ngày06/10.
P0.3B.2 đã tách Task pure helpers; P0.3C tách state/audit; P0.4/P0.5 local đã đạt.
Không mở RAG khi Source/ACL gate chưa đạt; không sửa lỗi Task ngoài checkpoint.
P0.3A.1/A.2/A.3 đã bỏ runtime → scheduler API và report → Telegram router qua
queue/permitted. P0 đạt local theo lát cắt và acceptance mới, không production24/7.
Đính chính: khác biệt encoding ghi trước đây do công cụ đọc file bằng code page
Windows; artifact UTF-8 đúng và không cần sửa/generated types lại.
Không bật M4, không thêm hàng chục agent hoặc thay runtime để đạt feature parity.

Mỗi mốc ghi rõ: migration/contract → service → UI tối thiểu → unit/integration → failure test → acceptance report. Nếu gate chưa đạt thì giữ tính năng tắt, ghi blocker cụ thể thay vì đánh dấu hoàn thành.

### Backlog M0 lịch sử theo thứ tự thực hiện

| Bước | Công việc | Đầu ra nghiệm thu |
|---|---|---|
| M0.1 | Chốt ADR và baseline; kiểm tra không có công việc đang chạy trước thao tác vận hành | Danh sách trạng thái, contract ownership, backup và quy trình phục hồi |
| M0.2 | Viết regression tái hiện start trước commit, duplicate request khác tham số, concurrent decision và cancel giữa timer | Test chứng minh từng lỗi/rủi ro, chạy trên DB/namespace riêng |
| M0.3 | Thêm dispatch outbox, reconciliation, khóa/version và fingerprint đầy đủ | Workflow có row DB thật; start/signal được giao lại an toàn sau gián đoạn |
| M0.4 | Timer hủy được, projection failed/timeout và recovery | Cancel kết thúc thực thi; UI không giữ running khi workflow đã failed |
| M0.5 | Restart worker/server giữa approval/timer; restore vào môi trường riêng | Bằng chứng không mất tiến độ, không nhân đôi hành động và phục hồi dữ liệu |
| M0.6 | Bộ đánh giá metric/nguồn/thiếu dữ liệu và chất lượng trả lời | Phát hiện câu giải thích CVR sai; output không có bằng chứng bị đánh dấu chưa đạt |
| M0.7 | Chạy regression và cập nhật checklist | Báo cáo pass/fail/blocker; chỉ chuyển M1 khi các điều kiện bắt buộc đạt |

Không gán số ngày cố định trước M0.2 vì mức sửa transaction và recovery phụ thuộc lỗi tái hiện. Mỗi bước là một thay đổi có thể review và rollback riêng; không triển khai đồng thời M1–M8 để rút ngắn lịch.

## 8. Nguồn tham khảo bên ngoài được xử lý thế nào

Javis đã được đọc chọn lọc ở commit cố định theo mục 9; dùng ý tưởng module và
contract, không chọn làm core thay PAO. Các repo OpenJarvis/BOS-AI/FusionClaw/
BusinessOS/codex-with-chatgpt/agent-skills vẫn là đầu mối chưa audit trong lượt này.
Không cài đặt chúng hoặc lấy tuyên bố bảo mật/tính năng làm bằng chứng nghiệm thu.

Không áp dụng nhận định chưa xác minh về một repo bị deprecated để loại công nghệ. Khi lựa chọn dependency cụ thể phải đọc nguồn chính thức, cố định version/commit, kiểm tra license và test adapter với PAO.

## 9. Tham chiếu Javis: pin nguồn và chọn lọc thiết kế

Đọc ngày 05/10/2026 tại [repository chính](https://github.com/blogminhquy/javis-os).
HEAD được GitHub API xác nhận: **3bf9edeac2a23827fe355433a362ba3576a21d84**;
VERSION tại commit này là **0.78.0**. Đây là code reference, không phải kết quả
chạy test Javis hoặc chứng nhận bảo mật. F:\Javis OS hiện chỉ thấy .git ở top-level;
không dùng nó như checkout source đầy đủ. Không sửa golden tree hoặc source Apex.

Web reader đọc được ARCHITECTURE/main và LICENSE/main; một số URL commit cố định
bị cache miss, sau đó đã đọc public source qua HTTP read-only, không clone/install/
chạy code. Tài liệu architecture mô tả một số paths còn shadow/canary; không
đánh đồng chúng với tính năng production. Các nguồn đã đối chiếu chọn lọc:

| Nguồn Javis ở commit cố định | Ý tưởng áp dụng cho PAO | Không suy diễn |
|---|---|---|
| [ARCHITECTURE](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/ARCHITECTURE.md) | Tách engine, vault, tools, channels và runtime state | Không port main/router/dashboard nguyên khối |
| [chat_runtime.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/chat_runtime.py) | Browser là subscriber của job | Registry in-memory không thay DB/ARQ bền của PAO |
| [session_brain.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/session_brain.py) | Ghi association session/brain rõ ràng | Mapping phục vụ nhãn usage không tự là RBAC |
| [lazy_skill_runtime.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/lazy_skill_runtime.py) | Chọn manifest rồi nạp body có giới hạn | Skill text không được cấp thêm tool/quyền |
| [mcp_hub.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/mcp_hub.py) | Tool gateway dùng chung, kiểm quyền bằng code | Không nhập hub thứ hai hoặc tin mode header do client tự gửi |
| [workflow_runs.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/workflow_runs.py) | Lưu lịch sử một lần tại điểm thực thi chung | Không tạo queue/task store song song với M1 |
| [learn.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/learn.py) | Model đề xuất, trusted service promote knowledge | Docstring guard không tự chứng minh toàn bộ module an toàn |
| [usage_store.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/usage_store.py) | Usage đo được tách khỏi quota/gói thuê bao | Không biến giá API quy đổi thành tiền đã trừ |
| [routes/coding.py](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/server/routes/coding.py) | Bind session với repo, quyền và checkpoint | Không port rollback destructive/reset hard mặc định |
| [LICENSE](https://github.com/blogminhquy/javis-os/blob/3bf9edeac2a23827fe355433a362ba3576a21d84/LICENSE) | File root là MIT; nếu reuse code phải giữ notice và provenance | Không mặc định dependency, service, model hoặc credential dùng cùng license |

Các phần chưa đọc sâu như voice_live, plugin host, channels/customer bot chỉ là
đầu mối thiết kế; phải audit module cụ thể khi triển khai, không khẳng định parity.

## 10. Cấu trúc PAO đích: modular monolith, không thay lõi

**Bổ sung17/10:** cây dưới là gợi ý ranh giới, không phải checklist di chuyển
thư mục. Các module đã tồn tại như business_planning/goals/schedules/results/
learning/channels/connections/connectors/engines được giữ và lập ownership map;
không tạo bản sao chỉ vì tên trong cây khác. `apps/worker` hiện không chứng minh
mọi worker đã chuyển khỏi API/scripts. Xem mapping và lộ trình extract tại
[kế hoạch17/10](PAO-TARGET-ARCHITECTURE-AND-DELIVERY-2026-10-17.vi.md).

Đây là **cây đề xuất, chưa tồn tại đầy đủ**. Một ứng dụng backend với worker roles,
không microservices/Kubernetes. Giữ Python backend trong apps/api, không tạo thêm
server/ chạy Javis cạnh PAO. Next.js vẫn là frontend. ORM/migrations của PAO là
nguồn schema duy nhất; API version hiện hành phải giữ tương thích.

```text
F:\PAO-ACOS\
├── apps/
│   ├── api/
│   │   ├── pao/
│   │   │   ├── app.py                 app factory/router registration
│   │   │   ├── core/                  config, identity, access, crypto, errors
│   │   │   ├── db/                    Base/session/metadata, không DB thứ hai
│   │   │   ├── modules/
│   │   │   │   ├── conversations/     sessions, messages, SSE, search/export
│   │   │   │   ├── tasks/             goals, tasks, dependencies, attempts
│   │   │   │   ├── brains/            brain metadata và scope
│   │   │   │   ├── knowledge/         documents, versions, citations, memory
│   │   │   │   ├── studio/            agents/skills/workflow definitions
│   │   │   │   ├── tools/             Gateway, policy, calls, audit
│   │   │   │   ├── business/          ads, warehouse, reports, CRM, creative
│   │   │   │   ├── approvals/         read adapters; M4 enforcement giữ domain
│   │   │   │   ├── operations/        schedules, result inbox, usage, health
│   │   │   │   └── voice/             STT/TTS và turn/session binding
│   │   │   ├── runtime/               orchestration, context compiler, budgets
│   │   │   ├── engines/               gateway interface + API/Ollama adapters
│   │   │   ├── integrations/          Meta/Google, MCP transport, channel adapters
│   │   │   └── workers/               ARQ/Temporal/bridge entrypoints
│   │   ├── migrations/               lịch sử hiện có, không squash baseline
│   │   └── tests/                    unit/integration/contract/fault/security
│   └── web/
│       ├── app/                      giữ route URLs hiện hành
│       ├── features/                 chat, knowledge, studio, tasks, integrations
│       ├── components/               shared shell và primitives
│       └── lib/                      API client, auth/runtime state
├── packages/
│   ├── contracts/                    OpenAPI và TypeScript sinh tự động
│   ├── agent-config/                 seed manifests được review
│   └── skill-config/                 seed manifests versioned, không user state
├── infra/                            compose, deploy profiles, backup policies
├── scripts/                          entrypoint ổn định; nhóm dev/test/ops dần
├── docs/                             roadmap, ADR, runbooks, acceptance history
├── data/                             private storage, ignored Git
│   └── workspaces/<uuid>/brains/<uuid>/
│       ├── sources/                  original source versions, không sửa ngầm
│       ├── wiki/                     published knowledge projections
│       ├── notes/                    user notes/journal
│       ├── skills/                   reviewed content projections
│       ├── agents/                   portable definition projections
│       ├── workflows/                portable definitions, không run state
│       └── attachments/              validated file objects
└── .runtime/                         process/log/cache/temporary backup riêng
```

Mỗi domain module chỉ thêm files khi cần: api.py, schemas.py, service.py,
repository.py/models.py và policy.py. Không tạo hàng loạt file rỗng. Route chỉ
parse/auth và gọi service; service giữ transaction/state machine; repository
không gọi LLM/network; adapters không tự đổi task status. `main.py` là shim
entrypoint ổn định sau app factory, không nhận logic nghiệp vụ mới.

### 10.1. Nguồn dữ liệu chính và quy tắc chống hai hệ điều phối

| Dữ liệu | Authority | Bản dẫn xuất/portable |
|---|---|---|
| User/workspace/brain ACL, connector secrets | PostgreSQL + crypto service | Không export secrets vào vault hoặc Git |
| Goal/task/attempt/run, approval, business records | PostgreSQL hiện có | UI/SSE/Markdown summary là projection |
| Workflow execution dài hạn | Temporal history + DB projection theo contract M0 | Workflow YAML/Markdown chỉ là definition |
| Job ngắn và dispatch | DB outbox, ARQ/Redis delivery | Redis không là nguồn lịch sử hoặc evidence |
| Source documents/files | Validated immutable bytes + DB version/hash/ACL | Text chunks, vector index và graph có thể rebuild |
| Published Wiki/Memory/Skill/Agent | DB version + content hash được publish | Markdown là export/projection có import revision check |
| User notes | Notes service transaction + revisioned file object | Edit qua Obsidian cần explicit import/conflict review |
| Usage | Append-only scoped usage ledger | Daily chart/cost estimate là aggregate, không quota thật |

Brain là kho tri thức bên trong workspace, **không thay thế workspace/brand**.
Migration phải xác định rõ legacy memory user/brand được ánh xạ vào default brain
như thế nào; không mặc định tất cả members được đọc memory riêng. Brain IDs dùng
UUID, slug chỉ hiển thị; filenames không được quyết định quyền.

### 10.2. Quy trình refactor từng module

1. Inventory route/import/schema/job ownership và test fixtures, ghi dependency map.
2. Chọn một module ít side effects để thí điểm; baseline API/behavior/performance.
3. Extract service/schema trước; giữ shim import/route cũ. Không move files đại trà.
4. `models.py` giữ facade/metadata registration đến khi Alembic nhận đủ tables;
   không tạo `db.py` và `db/` trùng import hoặc `runtime.py` và `runtime/` cùng lúc.
5. Đổi sang package chỉ trong checkpoint riêng; shim và entrypoints có tests.
6. Run full regression + contract diff, browser liên quan, migration check nếu có.
7. Idle/drain API+worker trước restart. Backend source digest thay đổi sẽ chặn
   execute pin cũ; giữ snapshot/hash lịch sử, result replay vẫn đọc được. Không
   sửa digest/history để “tương thích”, không tự resume công việc dở.
8. Commit riêng và rollback source có kiểm soát; rollback schema/data cần backup.

Không đổi port 8100/3200, database pao_acos_local, migration IDs, API URLs hoặc
config key chỉ để đẹp cấu trúc. Không lấy giảm số dòng code làm điều kiện đạt.

## 11. Kế hoạch bổ sung năng lực P0–P8

Mỗi P là nhóm checkpoint, không phải một lần làm tất cả. APIs/bảng/flags dưới
đây là **đề xuất chưa triển khai**, tên cuối chốt trong ADR trước migration.
Không đặt ngày hoàn thành giả khi chưa đo workload hoặc chưa có credential.

### P0 — Module boundaries, capability status và vận hành cơ bản

Phụ thuộc M0/M1/M2; không cần Meta/OAuth. Đề xuất thực hiện đầu tiên sau xác nhận.

- P0.1: vẽ dependency/ownership map, route table snapshot và phân loại scripts
  source-history/ACOS-current. Không xóa script lịch sử hoặc move code ở bước này.
  **Đã hoàn tất khảo sát tĩnh:** 62 Python files, 133 HTTP operations khớp
  METHOD/PATH với contract đã lưu, 64 ORM tables. Không phải runtime acceptance.
  P0.2A extraction reconciliation và P0.2B app factory đã đạt local.
  Chi tiết và gate source digest M2 trong ADR-P01/acceptance P0.2A/P0.2B.
- P0.2: app factory và route registration contract, extract một service nhỏ;
  giữ compatibility imports. **Đã đạt local theo lát cắt P0.2A/P0.2B**: import
  factory module không tạo app/config/DB/runtime; composition không mở network/
  pool hoặc tạo DB/job/provider call. Router cũ vẫn initialize config/ORM engine
  object/registry; chưa phải chuyển toàn bộ stack sang dependency injection.
- P0.3: nhóm tasks, conversation, runtime, business và tools từng lượt; frontend
  feature folder từng domain, không rewrite toàn bộ PaoConsole/shell.
  P0.3A.1/A.2/A.3 warehouse/report scheduler và Telegram helpers đã đạt local.
  Telegram ingest/collect/deliver/router vẫn chung module; chưa sạch HTTP toàn
  stack. P0.3B.1 call-map/9 tests và P0.3B.2 pure helpers đã đạt; P0.3C đã tách
  conversation/run state và tool audit, core API không import runtime worker.
  Frontend platform feature tách ở P0.4. Không phải move toàn graph/Attempts/
  models/bridge/frontend domains; lỗi progress chưa sửa, ghi nợ kỹ thuật riêng.
- P0.4: trạng thái `implemented/configured/healthy/accepted` tách riêng trong
  platform catalog; bỏ suy luận “token có mặt = connector hoạt động”. Giữ wire
  contract cũ bằng additive fields nếu cần. Capability shadow không là active.
  **Đã đạt local:** evidence catalog + workspace UI; provider health/accepted
  không tự suy từ credentials. Xem P04-CAPABILITY-EVIDENCE-2026-10-05.vi.md.
- P0.5: health worker/bridge, correlation logs có redaction, CI unit/contract,
  process supervisor/reboot drill, backup source+DB+file manifest cùng checkpoint.
  **Local đạt:**366tests/contract/runtime/typecheck/build/browser/replay,
  worker/bridge lease, safe request log, bounded worker repair drill và verified
  source+DB manifest. Production supervisor/reboot/cold-restore chưa đạt; remote
  CI chưa chạy. Không coi subprocess restart là reboot. Xem báo cáo P0.5.

Gate cho P1 là ownership/boundaries cần thiết, RBAC, contract tests và backup
local đã kiểm chứng; không bắt buộc hoàn tất mọi lần di chuyển module P0.3.
Reboot drill và supervisor production trong P0.5 là gate riêng trước chạy 24/7
hoặc remote production, không chặn MVP tri thức chỉ đọc trên local.

Nghiệm thu: route/OpenAPI tương thích, metadata Alembic không mất table, source
chưa phát sinh import cycle, jobs ownership không đổi, terminal replay M2 qua
refactor vẫn đọc được, tests chỉ pao_test/Redis15. Reboot cần thử ở môi trường
được cấp riêng, không coi subprocess smoke là reboot thật. Rollback từng commit;
không đổi schema cùng lúc với first extraction. Rủi ro lớn: source digest pin,
circular imports, tests phụ thuộc patch path và launcher gọi entrypoint cũ.

### P1 — Brain Manager và file service an toàn (M5A phần 1)

**Đạt LOCAL MVP ngày06/10/2026**, phạm vi text/Markdown; xem acceptance riêng.
Quarantine hiện là validation trong memory trước transaction, chưa antivirus hay
pipeline quarantine lâu dài. PDF/image không được nhận/preview trong P1 này.

Phụ thuộc P0 và RBAC hiện hành. Ví dụ: brain “Marketing” chứa tài liệu/notes,
không được tự thấy memory riêng của brain cá nhân hoặc brand khác.

- P1.1: ADR workspace/user/brand/brain scopes; default brain ánh xạ legacy facts,
  không nhân đôi dữ liệu hoặc mở ACL. Đã có brains/brain_members/version.
- P1.2: create/list/rename/archive brain; session chọn brain và pin brain_id,
  brain revision trên run. Chuyển brain không retroactively đổi history/usage.
- P1.3: file object metadata, safe upload/download/preview, MIME/size/quota limits,
  path traversal/symlink/ZIP bomb guards, quarantine; không URL fetch tùy ý.
- P1.4: Notes CRUD với version/ETag, trash/restore, edit conflict; source original
  immutable. P1 chỉ text/Markdown plain preview, không render HTML untrusted;
  PDF/image là phạm vi mở rộng chưa triển khai.
- P1.5: export portable ZIP manifest/hash, import dry-run diff và confirmation;
  chưa tự sync GitHub. Import không chạy Python/shell/skill từ tệp.

API đã có `/v1/brains`, `/v1/brains/{id}/files`, `/notes`, `/export`,
`/imports/preview`, `/imports/{plan_id}/confirm`; bảng brains/brain_members/
brain_files/brain_notes/brain_note_versions/brain_import_plans và session association.
UI Knowledge thêm chọn brain và Files/Notes, không mất tab Memory/Brands hiện có.

Nghiệm thu: hai users/brains/brands không đọc chéo; filename độc hại bị chặn,
upload quá quota không để orphan file, edit version conflict, archive không
launch job mới, delete có recovery; export/import roundtrip không tự mang theo
credentials/config. Nội dung người dùng upload có thể nhạy cảm, không có DLP.
ZIP là active files/current notes snapshot, không gồm version history/trash/grants;
full DB backup giữ cả versions/trash. Files/notes chưa tự được chat truy xuất (P2).
Rollback additive columns/flags trước, không drop legacy memories; restore cả
bytes và DB mapping. Gate đầu `brain_manager_enabled=false` khi chưa đạt.

### P2 — Sources → Wiki, RAG có nguồn và graph (M5A phần 2)

P2.1 đã đạt local theo [báo cáo](P21-SOURCE-INGESTION-2026-10-06.vi.md) và
[ADR](ADR-P21-SOURCE-INGESTION.vi.md), migration0029/Sources flag local bật.
P2.2–P2.6 đã triển khai local text/Markdown theo [ADR P2](ADR-P2-KNOWLEDGE-WORKSPACE.vi.md);
18tests P2, toàn464backend không skip và browser/API/ARQ/SSE/fixture restore đã
đạt. Regression/restart/live contract/replay/idle đạt trong
[báo cáo P2](P2-LOCAL-ACCEPTANCE-2026-10-06.vi.md).
Chat opt-in trích nguồn có citation, không LLM synthesis; PDF/OCR chưa mở.
Ollama thiếu embeddinggemma:300m: semantic path test fixture, local fallback FTS.

Phụ thuộc P1. Ví dụ: tải SOP sản phẩm, hỏi “chính sách đổi trả” phải dẫn source
version/page/section; tài liệu chứa lệnh “bỏ qua policy” chỉ là dữ liệu.

- P2.1: bắt đầu text/Markdown; source/version/hash, parse status và job idempotency
  theo content hash+parser version. PDF parsing là bước riêng; OCR sau khi cần.
- P2.2: chunking/chunk citations, embeddings local queue, index rebuild, full-text
  fallback khi embeddings offline. Xóa/đổi ACL phải lọc retrieval ngay.
- P2.3: retrieval API có brain/user/brand filter trước ranking; cap docs/chunks/
  bytes, source citations; prompt không được truy cập source ngoài scope.
- P2.4: Wiki draft từ source, review/diff/publish/revert; trusted service ghi.
  Không promote assistant assertion không nguồn; sửa source làm Wiki stale.
- P2.5: wikilink graph là derived view của notes/wiki đã có quyền; missing link
  hiển thị unresolved, không tự bịa node hoặc expose tên private document.
- P2.6: conversation attachments dùng file service; artifact download, preview
  và source provenance, không đưa toàn bộ PDF/raw archive vào mỗi prompt.

API đề xuất `/sources`, `/ingestion-jobs`, `/retrieval`, `/wiki`, `/graph` theo
brain. DB document_versions/chunks/citations/publish_events; bytes ở validated
file store, vector là index. UI Sources/Wiki/Graph trong Knowledge.

Nghiệm thu: source update/retry không duplicate chunks; RAG fixture factual,
missing/conflicting evidence trả thiếu; citation truy lại đúng version; injection,
cross-scope, MIME/parser lỗi và index-offline đạt; graph rebuild không mất nội dung.
Git-brain sync chỉ mở sau secret scan và repo riêng owner chọn, không commit
raw CRM/PII/secrets tự động. Rollback parser/index version không sửa source bytes.

### P3 — Engine contract, context compiler, chat UX và usage

**P3.1–P3.7 đã đạt LOCAL MVP**, xem [acceptance P3](P3-LOCAL-ACCEPTANCE-2026-10-06.vi.md)
và [ADR P3](ADR-P3-CONTEXT-CHAT-USAGE.vi.md). [Acceptance P3.1](P31-LOCAL-ACCEPTANCE-2026-10-06.vi.md)
là gate lịch sử. Matrix mô tả adapter PAO, không bảo đảm mọi model có native
tools/vision. Ledger P3.7 tách reported/estimated/unknown; không có giá/usage
thì không giả0/invoice/quota. Compaction là extractive cache giữ original, không
LLM semantic summary. Model chưa hỗ trợ planner trả lỗi, không tự đổi provider.
Knowledge excerpts có engine local riêng, không gọi chat model đã chọn.

Phụ thuộc P0; Brain context dùng sau P1/P2. Không cài CLI hoặc cloud provider mới
chỉ vì Javis liệt kê nhiều engines. Chưa bật fast-path shadow hiện có thành active.

- P3.1: engine interface có capability matrix (text/tools/vision/stream/cancel/
  usage), chuẩn hóa errors/events; provider/model pin theo session rồi snapshot
  run. Global default không đổi model của job đang chạy.
- P3.2: tách context builder: system policy, user message, history, retrieved
  sources, memory, selected skill; dự toán token/bytes trước provider call,
  chỉ nạp body của skill đã chọn. Skill/docs/tools là untrusted references.
- P3.3: compaction có nguồn message IDs và version, giữ original history; không
  để summary nâng quyền hoặc xóa evidence/approval identity. Trace chỉ lưu IDs,
  budgets và policy decisions, không private chain-of-thought/raw secrets.
- P3.4: route engine theo explicit preference/privacy/capability/budget trước;
  không tự fallback private local prompt sang cloud. Local offline trả cần chọn
  phương án nếu cloud chưa được cấp phép. Mock providers trước cloud smoke thật.
- P3.5: `/help`, `/status`, `/brain`, `/tasks`, `/memory`, `/model`, `/usage`,
  `/compact`, `/export`, `/stop`; share command parser cho web/Telegram sau P7.
  `/goal` chỉ mở khi goal runner P6 đã đạt, không dựng lệnh có UI mà không job.
- P3.6: session full-text search, pin/group, Markdown export, safe attachment
  renderer; retry tạo run mới có parent reference, không xóa lịch sử cũ.
- P3.7: usage ledger per user/workspace/brain/run/attempt/provider/model/source;
  provider-reported/estimated/unknown tách riêng, dedup theo event/request ID.
  Missing usage không đổi thành zero; cost estimate ghi pricing version/time,
  không gọi đó là invoice/quota thuê bao. Local resource concurrency cap.

Nghiệm thu: đổi model không mất history/brain; tool thiếu capability bị chặn;
no-cloud policy không có network egress cloud; cancel dừng stream và process được
quản lý; budget-exhausted không success; usage replay không double count, unknown
hiển thị đúng. Benchmark trước/sau cùng model/input: TTFT, latency, context size,
tokens, queue wait và quality corpus; giảm token không được làm giảm correctness.
CLI provider là nhánh sau P8/permission và official vendor docs tại thời điểm làm.

### P4 — Agent/Skill/Workflow Studio có review, không arbitrary code

**P4.1–P4.6 đã đạt LOCAL MVP ngày06/10/2026, Studio đã bật local.**
Đã có Studio definitions/API/UI, explicit LLM skill và workflow definition lint;
xem [báo cáo nghiệm thu P4](P4-LOCAL-ACCEPTANCE-2026-10-06.vi.md) và
[ADR P4](ADR-P4-STUDIO.vi.md). Backend549/549, focused62, browser P4/P3/P2,
Ollama synthetic, migration up/down/up và live M2 replay đã đạt. Workflow runner,
semantic canary và production/reboot chưa được mở, đúng ranh giới P4.

Phụ thuộc P0/P1/P3 và M2 contracts. Ví dụ tạo skill “soạn FAQ từ SOP” ở draft,
test fixture, review rồi publish; skill không tự được thêm quyền gửi email.

- P4.1: immutable definition_versions, draft → validated → reviewed → published
  → deprecated; agents/skills/workflow definitions liên kết content hashes.
  M2 seed files import một lần bằng migration/service có idempotency, không hai
  writable registries cạnh tranh giữa file và database.
- P4.2: UI CRUD agent prompt/model preference/brain scope; clone defaults thay
  vì sửa seed đang dùng. Agent instruction không override permission service.
- P4.3: Skill editor input/output schemas, tool allowlist, timeout/token budgets,
  exit criteria; template/lint/preflight. Import/export definition dry-run.
- P4.4: explicit `/skill-name` router trước, ambiguity phải hỏi; semantic routing
  chạy shadow với corpus, false-positive side-effect bằng 0 trước canary.
- P4.5: LLM skill là mode mới: usage accounting + generation cap + hard deadline,
  unknown token usage fail-closed theo policy, không dùng metadata `0 tokens`
  của deterministic M2 để bypass token gate.
- P4.6: Workflow editor chỉ definition DAG có version, inputs/outputs/dependencies,
  không thực thi riêng. Preflight cycle/missing agent/tool/mismatched schema;
  execution được mở ở P6 và map vào Task/Attempt/Temporal hiện hành.

APIs `/v1/studio/agents|skills|workflows` đề xuất; giữ M2 catalog/replay compatible.
UI Agents & Skills thêm Editor/Test/Versions; hiển thị chưa chạy nếu runner chưa
đạt. Nghiệm thu: publication revision conflict, tool escalation/injection/code
import bị từ chối, archive/delete definition không phá pinned runs/history,
import-export không chứa keys, reviewer audit và rollback published version đạt.

### P5 — Connector catalog và MCP read-only (M7A)

**P5 LOCAL MVP đã đạt ngày06/10/2026**, theo lựa chọn user nghiệm thu fixture
trước. Xem [báo cáo P5](P5-LOCAL-ACCEPTANCE-2026-10-06.vi.md) và
[ADR P5](ADR-P5-CONNECTORS.vi.md): 583 backend không skip, focused70 sau thay đổi
cuối, runtime8/8, build18pages, browser P5/P4/P3/P2 và restore88bảng đạt.
Migration0034 giữ nguyên dữ liệu85bảng cũ/hợp đồng222API cũ; local adapter bật,
không actual connection. **External smoke chưa đạt**: chưa server/credential/key.
Auth refresh hiện là bearer rotation thủ công serialized, không OAuth tự refresh;
chỉ MCP2025-11-25/HTTPS/schema đóng. Stdio/code plugins/SSE resume chưa mở.
Không đánh dấu P5 production/full interoperability đã hoàn tất. M4/P6 execution
vẫn tắt; bước tiếp theo phải chọn lại gate M4 trước các phần P6 cần execution.

Phụ thuộc P0/P3/P4 và Gateway M2. Không cần M4 để thử một tool đọc; write vẫn tắt.

- P5.1: phân biệt connector template, actual connection và secret reference;
  owner chọn một server read-only, chưa onboarding hàng loạt dịch vụ.
- P5.2: adapter trong Gateway, namespaced tool IDs, schema/capability pin, reject
  schema drift; discovery không tự cấp quyền hoặc tự gọi tool.
- P5.3: effective permission là giao của membership, brain ACL, published skill,
  connection scope, policy, approval (nếu write). Không tin mode/tenant do model
  hoặc client header tự chọn; worker recheck trước gọi.
- P5.4: HTTPS transport/auth, strict endpoints/SSRF/DNS-rebinding/redirect guards,
  connect/read timeout, pagination/result caps, cancellation and circuit breaker.
  Local stdio server chỉ sau executable/path/env allowlist, không arbitrary shell.
- P5.5: health probe và auth refresh serialized, secret encryption/redaction,
  audit chỉ metadata và references; revocation cancels queued work.
- P5.6: UI Integrations cho connect/test/disconnect/permissions; package manifest
  catalog không import Python. Plugins chạy code và pack auto-install chưa mở.

Nghiệm thu: fake MCP server fixture timeout/malformed/large result/revocation/
cross-tenant/schema drift; denied call không provider side effect; actual server
owner chọn có smoke đọc một resource. Credential chưa có ghi blocked external,
không đánh dấu connected từ catalog. Retention/credential purge giữ audit policy.
Rollback disable adapter, giữ historical calls; không auto retry call unknown.

### P6 — Durable workflows, schedules, inbox và learning

Phụ thuộc P4/P5; execution/approval/event-driven và business learning **cần M4
được người dùng cho phép, M3 đạt cho các outcome nghiệp vụ**. Có thể thiết kế
definition trước, không mở runner hoặc biến P6 thành cách triển khai M4 ngầm.

- P6.1: compile definition DAG vào task nháp; ghim workflow/agent/skill payload,
  model name/config, input và evidence expectations; dự trữ execution ID từng
  step nhưng **chưa tạo attempt hoặc chạy workflow**. Model weights và evidence
  kết quả chỉ được xác minh khi có runner ở checkpoint sau.
  **Đã đạt planning-only LOCAL ngày 07/10/2026:** 662 backend passed,
  runtime8/8, build18pages, browser real HTTP/restore91bảng,
  API/Web200, live contract243/replay3/3. Không có migration mới (0037).
  Xem [nghiệm thu P6.1](P61-LOCAL-ACCEPTANCE-2026-10-07.vi.md) và
  [ADR P6.1](ADR-P61-WORKFLOW-PLANNING.vi.md). Meta đang pause, giữ cấu hình
  App/key; không coi P6.1 là hoàn thành P6 hoặc vượt gate M3.
- P6.2: human wait/dependency/timer do Temporal sở hữu, job ngắn ARQ; unified
  projection ở DB. Idempotency keys và cancellation propagate, bounded retries
  chỉ khi safe; unknown side effects cần reconcile/manual review.
  **Đã bắt đầu P6.2A ngày07/10/2026:** deterministic dry-run kernel riêng,
  Temporal histories/replay7/7, restart worker ở approval/timer và cancellation
  acknowledgment đạt. **P6.2B foundation LOCAL đã đạt:** admission/outbox/
  DB projection,5APIadditive,migration0038,full688passed,restore93bảng,
  live health/contract248/replay3/3. Gates durable/dispatch/Temporal vẫn tắt;
  P6.2C checkpoint1–3 đạt: schema/exit criteria, job ledger và echo bridge qua
  real Temporal/ARQ/Redis/API/DB; full720passed, bridge restore93bảng.
  **C4/D LOCAL dry-run đã đạt:** ARQ process chết sau claim/receipt,
  receipt redelivery qua process mới không claim lần hai; dispatcher/worker
  opt-in, readiness leases và UI real-HTTP complete/reject/cancel đạt.
  Actual TCP loss DB/Redis/Temporal không tạo thêm attempt hoặc mất command;
  không coi đây là production service reboot. Regression731 không skip,
  restore93business tables và live health/contract/replay đạt.
  **P6.2 đóng ở mức LOCAL dry-run**, không gọi model/business tool; flags live
  vẫn tắt, production/real-model là gate riêng chưa đạt. Xem
  [nghiệm thu cuối](P62-LOCAL-ACCEPTANCE-2026-10-07.vi.md),
  [runbook](P62-RUNBOOK.vi.md), [nghiệm thu B](P62B-LOCAL-ACCEPTANCE-2026-10-07.vi.md),
  [tiến độ](P62-PROGRESS-2026-10-07.vi.md) và
  [ADR/checkpoint B–D](ADR-P62-DURABLE-WORKFLOWS.vi.md).
- P6.3: goal runner có max iterations/cost/time/deadline, success criteria và
  replan proposal; không tiếp tục vô hạn, đóng browser không làm mất ownership.
  **Trạng thái hiện tại09/10: runner backend + UI fixed Echo LOCAL đã đạt.**
  Xem runbook và sổ hoàn thiện P6; phần dưới là checkpoint lịch sử, không phải
  hàng đợi phải làm lại. Model/tool thật và production vẫn chưa nghiệm thu.
  **Đã bắt đầu checkpoint A ngày07/10/2026:** module goals riêng, pure policy/
  reducer,37unit tests/full backend767 không skip đạt; live health/contract/replay
  đạt. B1 đã thêm kernel Temporal, focused56/full backend786 không skip và
  replay đạt. B2a đã có DB goal ledger và guarded APIs; chưa có trusted adapters/live worker/UI. Cost là reservation
  dự trù, receipt chỉ echo0cost, không chứng minh billing hay thành công nghiệp vụ.
  P6.3 chưa hoàn tất; B2 cần admission/ledger/auth receipts và DB/ARQ acceptance,
  B2a admission/command/audit +guards đã nghiệm thu LOCAL808tests; trusted activity
  adapters/iteration claims/dispatch/worker vẫn chưa có. Xem
  [tiến độ B2a](P63B2A-PROGRESS-2026-10-07.vi.md).
  B2b1 đã thêm trusted admission provenance/source pins/actor reauthorization,
  full827tests/restore/live gates đạt; chưa phải activity projection/child prepare/
  read receipt hoặc goal dispatcher. Xem
  [tiến độ B2b1](P63B2B1-PROGRESS-2026-10-08.vi.md).
  B2b2a đã thêm pre-child projection;852backend +1Temporal→DB acceptance và
  projection restore đạt. Chưa cho iteration>=1/child/success; live worker
  chưa đăng ký. Xem [tiến độ B2b2a](P63B2B2A-PROGRESS-2026-10-08.vi.md).
  B2b2b đã thêm first-iteration ownership/child inert/reserved ceiling và trusted
  immutable receipt reader;871backend/runtime8/8/restore/pre-childTemporal đạt.
  Chưa có running/success/cancel-drain/replan projection, ordered goal dispatcher,
  iteration2+, registered goal worker và UI/process acceptance. Không đổi
  allow_iteration thành true chỉ vì đã có claim/reader. Xem
  [tiến độ B2b2b](P63B2B2B-PROGRESS-2026-10-08.vi.md).
  B2b2c đã thêm first-iteration running/success/unmet/budget projection và
  atomic trusted receipt revalidation;898backend/restore/runtime8/8/live gates
  đạt. Chưa mở allow_iteration hoặc live worker; cancel/unknown drain proof,
  terminal reconciliation, iteration2+/replan/reject và actual dispatcher/
  process/UI acceptance vẫn cần hoàn thiện. Xem
  [tiến độ B2b2c](P63B2B2C-PROGRESS-2026-10-08.vi.md).
  B2b2d đã có late-completed receipt reconciliation, giữ stopped status và release
  ceiling đúng một lần;914backend/runtime8/8/restore/live gates đạt. Chưa phải
  cancelled-child/absence drain, không đăng ký worker/poller/endpoint mới; real
  goal execution và P6.3C/P6.4–P6.7 vẫn chưa hoàn tất. Xem
  [tiến độ B2b2d](P63B2B2D-PROGRESS-2026-10-08.vi.md).
  B2b2e đã kiểm no-claim cancellation proof. B2b2f bổ sung native immutable
  claim fence khi mất mutable projection;931backend cases/runtime8/8/restore
  đạt. Không coi missing attempt là chưa chạy; UNKNOWN vẫn cần manual review
  và giữ reservation. Claimed-child ACK/drain, authority-loss reconciliation,
  iteration2+/replan, real dispatcher/worker/process và C UI còn cần triển khai.
  Xem [tiến độ B2b2f](P63B2B2F-PROGRESS-2026-10-08.vi.md).
  B2b2g thêm native claimed-cancellation fence cho fixed Echo:951backend/runtime8/8,
  bốn populated restores và real ARQ delayed finish đạt; không coi là real Goal
  parent/queue ACK/drain, không release UNKNOWN hoặc partial-completed children.
  Xem [tiến độ B2b2g](P63B2B2G-PROGRESS-2026-10-08.vi.md).
  C mới UI/browser acceptance. Xem [ADR](ADR-P63-BOUNDED-GOALS.vi.md) và
  [checkpoint A](P63A-CHECKPOINT-2026-10-07.vi.md) và
  [tiến độ B1](P63B1-PROGRESS-2026-10-07.vi.md).
- P6.4: schedule service một lần/cron/timezone/DST/misfire/coalescing; dùng lại
  existing automation/report schedules, xác định owner scheduler cho mỗi kind.
  Không tạo scheduler thứ hai polling cùng records. Schedule tắt mặc định.
  Persisted Studio fixed Echo đã đạt local10/10, migration0042, UI/DB/restart/
  slot/native Temporal/ARQ/restore. Backend bounded Goal hiện đã đạt0043 với
  parent admission/approval/child/receipt thực; còn UI Goal schedules/browser.
  Không lấy scheduled standalone workflow thay chứng minh parent Goal runner.
- P6.5: result inbox scoped, delivery outbox/dedup, read/ack và lỗi gửi có status;
  không hứa “sẽ báo” khi chưa có job/destination được phép.
- P6.6: learning proposal từ sourced conversation/artifact, trusted promotion
  service, review/diff/revert/audit, provenance/injection/secret checks, daily
  budgets/locks. Không auto sửa policy/code hoặc publish skill từ output model.
- P6.7: outcome 24h/72h/7d liên kết action/baseline/coverage/confounders; tăng KPI
  sau action không tự chứng minh causal effect. Missing outcome là insufficient.

Nghiệm thu: kill/restart giữa step/wait/approval, duplicate delivery/event không
nhân đôi action, permission loss, goal budget stop, DST và overdue jobs, learning
poisoning/revert. First live write không nằm trong gate này; dry-run trước.

### P7 — Shared channels, customer inbox và voice

Phụ thuộc P3/P5; outbound automation cần M4/P6 và owner xác nhận destination.

- P7.1: ChannelAdapter contract inbound envelope/dedup/identity/workspace/brain/
  session mapping; Telegram hiện có adapter đầu tiên, không copy chat core.
- P7.2: channel allowlist, command parser chung, reconnect/backoff, delivery
  reconciliation; khách ngoài không trở thành owner/admin hoặc được dùng coding.
- P7.3: customer inbox + human takeover/quiet policy, scoped knowledge grounding,
  retention/PII and rate limits. Zalo/Slack/WhatsApp mỗi channel audit terms/auth
  và connector cụ thể trước; không dùng tài khoản cá nhân ngầm hoặc bypass access.
- P7.4: voice local transcript → cùng Run service → scoped TTS; session/turn IDs,
  VAD, barge-in, mute/cancel, browser reconnect. Voice không được auto approve.
- P7.5: acceptance tiếng Việt bằng mic thật, môi trường ồn, cancel giữa TTS/
  tool, đo latency/STT error; raw audio retention/consent explicit. Live cloud
  voice là optional, riêng privacy/budget, không suy từ API code thành dùng được.

UI giữ Chief/Voice, thêm Inbox/Channels khi contracts đạt; không redesign Orb làm
điều kiện nền. Nghiệm thu shared state đúng web/channel, delivery không duplicate,
takeover dừng bot, channel/user isolation, microphone/browser permissions đạt.

### P8 — Engineering executor, media và extensions có sandbox (M7B/M8)

Phụ thuộc M4/P5/P0 security+restore; owner chọn repo/tool/provider, không tự bật.

- P8.1: repo bindings realpath allowlist, read-only inspection trước; explicit
  execution request gồm branch/workspace, acceptance, network/secret/time budget.
- P8.2: isolated worker/checkout, minimal env, command/network policies, file cap,
  process tree cancel, quota/concurrency. Không mount cả ổ đĩa hoặc home của owner.
- P8.3: diff/test/evidence artifact, human review; merge/deploy/push là approval
  tách biệt. Checkpoint source snapshot; rollback không reset hard/untracked-delete
  mặc định. Failed test không được trình bày như code hoàn tất.
- P8.4: generic engine adapters và optional vendor CLI sau official docs/auth/
  license review; không dùng token thuê bao làm API key hoặc suy miễn phí/quota.
- P8.5: media generation và web/video research qua tool cụ thể, result provenance,
  budget/retention/copyright safeguards. Credential thiếu thì unavailable rõ ràng.
- P8.6: extension definition packs được review/signed/versioned; arbitrary Python
  plugins là nhánh riêng cần threat model/process isolation, disabled mặc định.

Nghiệm thu: không đọc/sửa source/golden ngoài binding, secrets không vào output,
cancel/timeout dừng children, deny dangerous path/network, diff rollback bằng
snapshot trên checkout thử, retry không duplicate external publish/deploy.

## 12. Thứ tự, phụ thuộc và checkpoint hiện hành

**Thứ tự cập nhật17/10/2026**, kế thừa S0–S6, không đặt lại ID:

```text
S0–S5 local đã nghiệm thu (giữ nguyên bằng chứng)
 → S6.2: bảo vệ source → lời mời/thành viên → phiên → dữ liệu
 → M6 lát cắt UX/ownership phục vụ S6 → S6.2 CI + private production
 → S6.1 dữ liệu/action thật được cấp riêng → S6.3 owner pilot + M5B
 → P7.5/M8 nghiệp vụ được chọn → P8/M7B và M8 thương mại hóa có điều kiện
```

Chi tiết scope, files affected, điều kiện vào/ra trong
[kế hoạch17/10](PAO-TARGET-ARCHITECTURE-AND-DELIVERY-2026-10-17.vi.md); audit/checkpoint
cũ ở [kế hoạch11/10](PAO-UNIFIED-DEVELOPMENT-PLAN-2026-10-11.vi.md).
M6 trước pilot chỉ là lát cắt UX bắt buộc; polish toàn bộ sau nhu cầu rõ.
S6.1 read-only có thể nghiệm thu trước production trên môi trường được cấp;
pilot remote chỉ sau gate production phù hợp. Nếu thiếu host/data, thực hiện
local độc lập theo dependency rồi dừng đúng gate, không làm lại core/giả PASS.
Không tự bật external writes hoặc biến kế hoạch thành quyền deploy/chi tiền.

### Luồng và 10 checkpoint lịch sử trước SaaS — không dispatch lại

Đề xuất trước đây (giữ lịch sử, bị thứ tự S bên trên thay thế):

```text
M0/M1/M2 local đã đạt
        ↓
P0 → P1 → P2 → P3 → P4 → P5 read-only
        (M3 dữ liệu thật được chọn khi có account/export và P0 ổn định)
        ↓
M3 đạt + người dùng cho phép M4 → M4
        ↓
P6 / M5B → P7 → M6 hợp nhất UX → P8 / M7B → M8 nhánh cần thiết
```

P1/P2 là M5A không cần dữ liệu Ads; P5 là M7A không mở writes. Thứ tự có thể
chọn lại sau đo đạc, nhưng dependency và permission gate không được bỏ. Tại
thời điểm hiện tại: P0–P5 đạt LOCAL theo các lát cắt nghiệm thu, không phải đầy đủ
production/connector thật. M4.1–M4.5 local đạt, các flags vẫn tắt. M3 dữ liệu
thật và production reboot drill vẫn pending; chưa có lịch business tự chạy.

| Checkpoint | Một đầu việc trong lượt triển khai | Bằng chứng đạt rồi mới tiếp |
|---|---|---|
| 1 / P0.1 — đã đạt tĩnh | Inventory modules/routes/jobs và ADR ownership | Snapshot exact files/imports/routes/jobs/tables; METHOD/PATH khớp contract đã lưu; full schema/runtime gate còn ở P0.2; chưa move code |
| 2 / P0.2A — đã đạt local | Extract reconciliation với import shim | 320 tests không skip, full live contract không đổi, pure import/type identity và replay đạt |
| 3 / P0.2B — đã đạt local | App factory/registration và workers entrypoints | 326 tests không skip; contract UTF-8 khớp; launch/restart/replay đạt |
| 4 / P0 local đạt; production pending | Scheduler/Task values/state/audit/catalog/UI/operations theo lát cắt | 366tests/contract/runtime8/browser12/build/replay3/backup/repair đạt; reboot/remote CI/cold restore chưa đạt, lỗi Task còn riêng |
| 5 / P1.1 | Brain ACL + legacy mapping ADR/migration | Test isolation, private memory giữ nguyên quyền, DB rollback trên test |
| 6 / P1.2 | Brain CRUD + session association + UI chọn brain | Change/archive không đổi run snapshot/history, optimistic locking đạt |
| 7 / P1.3 | Files/notes tối thiểu, text/Markdown trước | Traversal/symlink/quota/conflict/trash-restore và upload-delete consistency |
| 8 / P2.1 | Source versions + ingestion text job | Retry/hash idempotency, parse lỗi rõ, không duplicate chunks |
| 9 / P2.2–3 | Retrieval có nguồn và FTS fallback | Citation/version/scope/injection corpus, embeddings-offline không bịa |
| 10 / P2.4 | Wiki draft/review/publish và diff/revert | Source stale/revision conflict, trusted promotion, không tự ghi knowledge |

Graph, token optimization, Studio/MCP và coding là checkpoint sau, không dồn vào
10 bước đầu. P0.4 capability status vẫn trong backlog; không gộp vào extraction
scheduler hoặc Brain ACL. Khi chọn thực thi, chỉ giao **một checkpoint** với scope/acceptance;
không tự move toàn bộ thư mục dựa trên cây đề xuất. M3 live cần account/kỳ/export
được cấp riêng; credentials đi qua local settings/secret store, không qua chat.

## 13. Definition of Done, kiểm thử và tối ưu có đo lường

Một tính năng chỉ “accepted local” khi có đủ:

1. ADR/contract/state ownership và scope threat model rõ; UI trạng thái thật.
2. Additive migration + roundtrip test nếu đổi DB; private backup/restore nếu
   đổi local data. Không dùng runtime folder/brain ZIP như bản backup DB đầy đủ.
3. Unit + integration trên pao_test/Redis15; RBAC/tenant/brand/brain isolation,
   invalid input, concurrent edit, idempotency, cancellation và recovery.
4. Generated OpenAPI/TypeScript khớp; browser desktop/mobile/empty/error/reconnect/
   stale response/accessibility, không chỉ screenshot giao diện đẹp.
5. Source/byte/hash/provenance và user-visible missing data; archived history
   không bị config/prompt/model/skill mới đổi nghĩa hoặc sửa ngầm.
6. External feature có real smoke đúng account/destination được owner cấp; nếu
   chưa có credential ghi fixture-only/blocked external, không tăng phần trăm giả.
7. Feature gate/disable/rollback và retention/delete/export policy; logs không
   secrets/PII/audio/raw private prompts. Một capability disable phải chặn worker.
8. Acceptance report ghi command/config test, pass/fail/skip, fixture vs live,
   baseline trước/sau và git checkpoint; không gọi skip là pass.

Baseline ghi nhận trước lần refactor đầu: M2 298 passed có real-clock opt-in;
M3.1 315 passed/2 skipped, runtime 8/8, migration 0024. Đây là số lịch sử trong
báo cáo, **không chạy lại tests ở lượt sửa roadmap**. Số test tăng không chứng
minh quality tăng; cần corpus/bug cases và measured outcomes.

Chỉ đặt mục tiêu performance sau baseline: TTFT/P95 latency, throughput của
worker tuần tự trên máy local, context bytes/tokens, vector/FTS query time,
ingestion peak RAM, queue lag, provider timeout và tỷ lệ câu có nguồn. So cùng
input/model/hardware; report cả quality regressions. Không bật nhiều agent song
song hoặc cache cross-user để giảm latency. Cache key phải có scope/version và
invalidation/revocation; dependency mới cần đo lợi ích và license review.

Remote deploy/24-7 là một gate riêng: HTTPS/auth hardening, secrets rotation,
supervisor/reboot, PostgreSQL+file restore drill, Temporal history backup policy,
metrics/alerts, resource quotas và incident runbook. Local tests không là production
SLA. Hybrid local/cloud không được tự xuất private context khi PC offline.

## 14. Rủi ro, điều không làm và quyết định kế tiếp

| Rủi ro | Quy tắc giảm rủi ro |
|---|---|
| Cây thư mục đẹp nhưng phá imports/pinned execution | Extract từng module, shim/metadata tests, idle deploy, không sửa history hash |
| DB/Markdown/Git cùng writable gây split-brain | Versioned service authority, explicit import diff, projections có thể rebuild |
| Source/skill/MCP prompt injection | Untrusted data boundary, least privilege, capability pin và worker recheck |
| Upload/export lộ dữ liệu hoặc đọc toàn ổ đĩa | UUID/file-object scopes, validation/quarantine/quota, no arbitrary path mounts |
| Studio import biến thành code execution | Definition-only drafts, review/publish, no Python/shell/plugin auto-load |
| Over-engineering/ba scheduler cạnh tranh | Modular monolith; giữ DB/ARQ/Temporal ownership, không thêm scheduler trùng |
| LLM cost/usage được trình bày sai | Measured/estimated/unknown, pricing version, usage không là quota/invoice |
| Học sai/tự poison memory | Proposal-only, nguồn/review/diff/revert, không promote tự nhận định của assistant |
| Nhiều channels mở quyền owner cho khách | Explicit identity/brain mapping, takeover, no coding/approval từ channel ngoài |
| Port feature Javis không đúng license/runtime | Pin commit, audit specific files/dependencies, notices và tests; không vendor cả repo |

Không thay PAO core bằng Javis, không copy SQLite/JSON operational state vào làm
authority, không đưa .env/brain riêng/credentials/Javis Git history vào target,
không đổi frontend stack, không auto-install packs hoặc chạy shell unrestricted.
Không sửa F:\Apex\apex hoặc F:\Javis OS. Không bật Ads writes/email/public
deploy/Telegram schedules trong refactor hoặc Brain MVP.

**Ghi chú lịch sử sau P2, không phải bước kế tiếp hiện tại (xem S0 ở đầu tài liệu):**
P2 LOCAL text/Markdown đã đạt. Khi đó đầu việc đề xuất kế tiếp là P3, chỉ triển khai
khi người dùng cho phép; chưa tự khởi công P3 hoặc M4. Trước semantic search trên
model thật, cần người dùng cho phép cài model embedding và benchmark,
theo [ADR-P01](ADR-P01-MODULE-BOUNDARIES.vi.md). P0.1 đạt khảo sát tĩnh, P0.2A/B
đã extraction/restart/regression local; các checkpoint P0 local đã nghiệm thu
theo [P0 acceptance](P0-LOCAL-ACCEPTANCE-2026-10-05.vi.md). Production vẫn pending;
Telegram ingest/delivery/router còn trộn, graph/Attempts/models và lỗi Task chưa
hoàn tất. P1 additive schema0025–0028 đã nghiệm thu local; không tự đổi schema
cho checkpoint tiếp theo. Giữ gate
source digest/idle/backup và full contract trước refactor tiếp. Saved OpenAPI đọc
đúng UTF-8 khớp live/source; khác biệt encoding trước là lỗi công cụ kiểm tra,
đã đính chính trong báo cáo, không cần sửa artifact hoặc dependency.
Nếu ưu tiên sản phẩm khác, người dùng có thể chọn checkpoint thay thế, nhưng chưa
có quyền tự khởi công các P/M từ việc cập nhật roadmap này.
