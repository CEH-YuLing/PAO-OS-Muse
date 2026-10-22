# P8.4-C — Candidate Codex dùng quyền và ledger PAO

Ngày19/10/2026, Asia/Saigon. **Đã cài nền tảng native0072; chờ owner login và native job thật.**
Không phải nghiệm thu toàn P8.4-C/S6/production hoặc quyền dùng chung thuê bao.

## Kết quả hiện tại14:25 ngày19/10

Full mới **2343/2343,0fail/error/skip**,2614.55s/62ARQ deprecation warnings:
`.runtime/p84-native-tests-0ab1a8a970f04ff8abaad5b983d84a67/receipt.json`.
Source/env/schema chính và frozen candidate không đổi trong lượt đó. Không đo
hash nội dung nghiệp vụ trong toàn lượt full; không dùng nó để đóng drift cũ.

Kế hoạch nguồn có preimage và full/JUnit/build guards:
`.runtime/p84-native-release-7c44dfc0aa9e40ab9698bdb09decd7ea/source-plan.json`.
Đã cài30tệp nguồn có review và tệp TypeScript sinh riêng từ frontend đã build,
không copy toàn candidate. Checkpoint mới restore-clone đạt trước migration:
`.runtime/checkpoints/p0-20261019T071852-c2a2ffc3/manifest.json`.
Installer/checker bổ sung sau checkpoint được giữ trong operator-source của
thư mục cài; source-before, cấu hình riêng và log đều giữ để phục hồi, không push.

Cài đặt và kiểm tra:
`.runtime/p84-native-install-2759acc61ab74bd89217b1ba125cd1bd/installed-check.json`.
Schema0072/155physical,412API, API/ready/Web200, worker healthy. So sánh old
columns/row hashes trước/sau cài và kiểm live giữ nguyên dữ liệu;3archive và
3HTTP replay đọc được, không thực thi lại công cụ. Diagnostic bearer chỉ dùng
GET đọc lịch sử, không phải login/consent của owner và không tạo phiên đăng nhập.

Binding mới `92ed17238d2c443efeee5762f9ba231a1fd99b0fb755fd47e70f184c112451a6`.
Interpreter/requirements pin cũ giữ nguyên. Chỉ thêm
`CLI_CONNECTIONS_ENABLED=true` vào `.env`; registry device v2 pin đúng image/
binary/host-library đã kiểm. Không đổi default model, tool grant, Ads/Telegram.
Tại thời điểm kiểm tra:0CLI connection/dispatch,0provider call, chưa login thật.
Các nhận xét primary0071/flag tắt ở phần lịch sử bên dưới là trạng thái trước
cài, không phải trạng thái đang phục vụ. Không sửa receipt/history cũ thành0072.

Chốt tiếp theo bắt buộc có hành động của người dùng: chạy công cụ thiết lập
trong PowerShell tương tác, tự đăng nhập PAO và OpenAI cho **PAO-Business
Operating Systems**. Cổng setup không phải grant hoặc quyền suy luận. Sau đó
mới nghiệm thu model entitlement, native ledger/usage, cancel/revoke/recovery.
Settings UI tổng thể thuộc E, chưa có nút đăng nhập CLI trên frontend hiện tại.
Đã mở một cửa sổ PowerShell tương tác14:28 cho người dùng tự đăng nhập; agent
không đọc output/mã thiết bị của cửa sổ đó. Model thử `gpt-6.1-sol` lấy riêng từ
trường model hiện cấu hình trên Codex local, không đọc auth store và chưa xác
nhận entitlement qua profile mới. Không biến cấu hình đó thành default PAO.
Sau khi người dùng báo hoàn tất cần kiểm metadata/auth hiện tại trước grant.
Receipt/current-local-release và S6 readiness cũ không được sửa hash hoặc coi là
bằng chứng cho binding mới; dùng receipt cài P8.4 riêng, S6/production vẫn false.

## Phạm vi đã triển khai trong candidate

Candidate: `F:/PAO-ACOS/.runtime/p84-native-candidate-20261018`.
Checkpoint trước schema work:
`.runtime/p84-native-checkpoint-1df83a532cfa412697a10a48393c25d0`.
Có source ZIP kiểm manifest và dump primary; chưa restore primary.

- Schema thử0072 thêm `cli_model_connections` chỉ lưu metadata, không token,
  và `cli_model_dispatches` tham chiếu `LlmAttempt`, không tạo queue/runner mới.
- Một profile riêng gắn workspace/actor/connection/device; API tạo hồ sơ chỉ nhận
  model và request key. Không nhận command, đường dẫn, token, API key hoặc profile
  do khách tự chỉ định. Tài khoản cá nhân chỉ được cấp cho chính actor đó.
- Tái sử dụng reference/grant/model consent, kiểm membership/Brain/quyền/
  privacy/budget/lease trước dispatch và trước công bố. Namespace CLI không
  được dùng để cấp quyền API kể cả khi source UUID trùng nhau giữa hai bảng.
- Snapshot CLI có version mới, pin model, binary, image, profile, source revision
  và grant. Reader/pin của provider cũ giữ version cũ; không repin lịch sử.
- Native AccountingEngine cung cấp attempt context; dispatch không có attempt
  và lease hợp lệ bị từ chối. Một attempt không gửi lại, kể cả sau thất bại.
  Profile có dispatch chưa đối soát bị khóa; cleanup không chắc chắn giữ unknown.
- API chuẩn bị volume, hướng dẫn login chính thức và kiểm auth không chạy model,
  không tự activate grant. Lưu khác đăng nhập; đăng nhập khác suy luận/permission.
  Ngắt PAO khác logout provider. Thay auth của kết nối đang connected cần ngắt
  trước để giữ rõ ràng phiên bản/quyền; không sửa grant của job đang có.
- Profile setup cũng có fence bền; thu hồi membership/session trong lúc I/O sẽ
  từ chối công bố. Chỉ dọn fence khi xác minh cleanup; không tự hết hạn để retry.
- Các route mới bị tắt mặc định. Chưa đổi `.env`, launcher, UI hoặc default model
  của bản đang chạy. Routing nghiệp vụ S5.3/Settings tổng thể thuộc E, chưa đạt.

## Runtime và giới hạn

Codex Linux0.157.1 nguyên bản, SHA256
`3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970`.
Gói npm SHA512 đã đối chiếu, base Python theo digest; README/metadata upstream
được giữ. Không coi checksum là xác nhận pháp lý hoặc chứng nhận supply-chain.

Docker dùng image hash và named volume có đúng năm nhãn scope. Không mount source
PAO, Windows home, Docker socket, credential Ads/Telegram vào container. Không
pull ngầm, không remote Docker, không lệnh từ HTTP hoặc fallback sang API key.
Container inference nonroot/read-only/cap-drop/no-new-privileges, giới hạn CPU/
RAM/PID/timeout/bytes. `/tmp` là vùng tạm; profile chứa auth do CLI quản lý.
Inference có egress qua Docker bridge cho nhà cung cấp, **chưa có domain-allowlist
proxy production**. Fixture dùng network-none. Không đánh đồng hai chế độ mạng.

Tắt shell chưa đủ: fixture phát hiện tool mặc định như multi-agent, ảnh, goals
và apply_patch. Đã tắt feature theo phiên bản thực tế và dùng catalogue harness
hạn chế, giữ nguyên model ID, loại apply_patch; không giả định model đã có quyền
truy cập. `request_user_input` nội bộ vẫn được Codex quảng bá, không phải công cụ
business. Phản hồi giả lập yêu cầu apply_patch bị từ chối, file đích không tạo.
Không dùng prompt “chỉ đọc” thay cho rào hệ điều hành.

CLI tự đọc auth cache trong profile riêng; PAO không sao chép token từ Codex/Javis
đang dùng. Chưa có profile đăng nhập thật gắn với SME. Operator chưa bật device
registry, feature flag hoặc quyền suy luận cho SME nào. Local auth không chứng
minh quyền commercial/hosted; SaaS và Antigravity gates vẫn giữ theo ADR-P84.

## Bằng chứng hiện có, không cộng gộp thành full pass

- Native CLI28/28 trên candidate đầu: receipt
  `.runtime/p84-native-tests-7f681cc6a7ee41b6a76340d1917dc844`.
- Hồi quy tập trung194/194,0fail/error/skip,101.78s: receipt
  `.runtime/p84-native-tests-b7ccd371d7ea424db06dcb11b113477a`.
- Sau profile setup và immutable dispatch:203/203,0fail/error/skip: receipt
  `.runtime/p84-native-tests-8edc2064d5334d39968dd75d1c1ce03f`.
- Unit transport Docker15/15 với daemon/process giả: không phải container thật.
- Container thật: normal fixture, tool injection, profile chưa login bị từ chối,
  scope SME khác bị từ chối, cleanup đạt; named volume fixture riêng đã xóa.
  Receipt `.runtime/p84-docker-acceptance-c322b230bcf54f1481fef36ca4b76e04`.
  Image `sha256:4aea0ca8cf932b399d486c9a9305ad667d8fafb05da5fff22f8c83d5a93aad48`.
  Không login/provider quota thật; không phải native PAO live job.
- Full backend candidate đầu đã kết thúc: **2339pass/1fail/0error/0skip**,2340test,
  2203.44s/62ARQ warnings. Receipt
  `.runtime/p84-native-tests-e9fbc1424f40426c88949039846e30f9` giữ `pass=false`.
  Không gọi các lượt tập trung ở trên là full pass, hosted CI hoặc live provider.
- Primary source/env/schema guards đạt ở các lượt203/194; primary vẫn0071.
  Không đo content hash nghiệp vụ trong các lượt này; sự cố drift cũ chưa đóng.

### Kiểm tra bổ sung trong cùng candidate

- Wheel build và import cả native gateway lẫn `pao_cli_runtime` từ chính wheel
  đạt; không dựa vào editable source. Bản sao đóng gói riêng, candidate không đổi,
  không cài wheel vào Python đang phục vụ. Receipt
  `.runtime/p84-package-00c09cf14b9b4b00bc0401f26e5c942d/receipt.json`.
- Hai lượt import trước thất bại vì bài kiểm tra thiếu JWT giả rồi JWT giả quá
  ngắn; log giữ ở `p84-package-23128f4d54f646049a9c238d53da2327` và
  `p84-package-8194e7cd01d64027be15ed4f3544af6e`. Không nới validation của PAO.
  Lượt sandbox kế tiếp bị ngắt vì event loop Windows bị chặn; lượt có quyền
  kiểm tra local đạt. Không dùng lỗi môi trường để báo candidate đã đạt trước đó.
- Transport offline đạt lại15/15; CI entry có thêm stage này. Chưa phải một lần
  hosted CI mới hoặc bằng chứng Docker daemon thật cho các unit test đó.
- Bản sao frontend đầy đủ với contract412operations:157Node/0fail/skip,
  typegen/TypeScript/production build đạt. Bản đang phục vụ và candidate không
  đổi. Receipt `.runtime/p84-frontend-79a10cd179674f48846483eb222658f3/receipt.json`.
  Bản checkpoint C đầu dùng allowlist cơ sở nên thiếu27tệp `.jsx`/`.d.mts`; log
  và archive cũ giữ nguyên. Build mới đối chiếu từng hash27tệp gốc không đổi,
  ghi rõ supplements; không gọi archive thiếu tệp là đã build. Công cụ chuẩn bị
  candidate đã chuyển sang `source_archive` hiện có; backup thêm chính xác
  `infra/codex-local/Dockerfile`.5unit backup đạt; không mở rộng sang tệp tùy ý.
- Image đã kiểm trước đợt bổ sung host-source pin:
  `sha256:635d7d0442ad1199195425d8bfbebd9c96770e5f5965e9eed43dfe0094d3c25a`,
  manifest `.runtime/p84-codex-image-8d6d7d400a6549f2802a9a57ff2100e8/image.json`.
  Actual Docker fixture/profile/no-auth/cross-SME và cleanup đạt,0subscription
  calls. Receipt `.runtime/p84-docker-acceptance-f0a291a724fd4b42b9a49bf34f27f38f`.
  Volume synthetic đã xóa; không đụng profile thật hoặc xóa image lịch sử.

### Chốt mới và lịch sử bị chặn

Lỗi full duy nhất là `test_p7_restore::test_populated_p7_restore_fresh_process_identity_and_no_resend`:
công cụ cũ từ chối ROOT candidate vì chỉ cho Windows primary `F:/PAO-ACOS`.
Không phải một lượt phục hồi đã thành công. Primary/source/env/schema và frozen
candidate đều không đổi trong lượt full đã thất bại; không đo hash nội dung
nghiệp vụ của primary trong cả lượt này.

Đã chuẩn bị nhánh Windows candidate riêng: đúng thư mục cố định, literal
`pao_test`/127.0.0.1:15432/userpao, containerID64hex, chỉ `--populated`, cấm
manifest/primary rollout và chỉ tạo/restore/drop clone do instance sở hữu.
Nhánh Windows primary cũ giữ nguyên.6unit scope/command với Docker và temp giả
đạt; clone thật sau sửa đã chạy đạt trong lượt207 bên dưới. Unit trước đó5pass/1error do sandbox không
dọn được temp; unit thuần mới giả lập cả temp, không nới quyền runtime.

Đồng thời bổ sung hash toàn thư viện host vào CLI snapshot/grant stamp và device
registry v2 để phát hiện đổi transport dù binary/image không đổi.3unit thư viện
đạt. Ba bài native mới và profile fixture đã kiểm lại trong lượt207 bên dưới.
Launcher candidate có dualPYTHONPATH và0072; ORM preflight154; không đổi launcher
hay interpreter của primary. Candidate đã có đủ27supplement frontend gốc và
Dockerfile đúng hash; archive đầu vẫn giữ nguyên.

Hai lần yêu cầu chạy focused trước đó bằng cơ chế duyệt quyền chính thức không được thực
thi: reviewer báo `Selected model is at capacity`. Đây là lỗi khả dụng của cơ
chế duyệt, không phải kết luận tác vụ nguy hiểm; không vượt chốt bằng đường khác.
Ở chốt bị chặn đó chỉ unit thuần/parse/source preparation được làm tiếp, không có
test runner DB chạy nền. Sau khi người dùng đổi chế độ duyệt và công cụ chạy
được trở lại, các lượt kiểm tra mới bên dưới đã thực thi. Wheel/frontend/
image receipts phía trên chỉ chứng minh đúng input lịch sử của từng lượt, không
tự kế thừa cho backend/host pin mới. Giao diện/contract không đổi trong đợt pin.

### Kết quả tiếp tục19/10 — lịch sử trước cài

- Focused **207/207,0fail/error/skip**,211.21s/2ARQ warnings. Bao gồm40CLI
  tests và populated P7 restore từng thất bại. Primary source/env/schema và
  frozen candidate không đổi. Receipt
  `.runtime/p84-native-tests-e193c3c97e65412aa9d3bc4fd0b4533b/receipt.json`.
- Hai clone riêng:0071→0072→0071→0072 giữ nguyên dữ liệu cũ; downgrade có dữ
  liệu CLI bị từ chối; restore populated giữ constraint/dispatch trigger và đọc
  được ba archive bằng reader cũ lẫn candidate. Primary/database/.env/candidate
  không đổi trong lượt này; hai clone đã xóa, dump riêng được giữ. Receipt
  `.runtime/p84-migration-5568ebdabace49bc813493639c7828b2/receipt.json`.
- Wheel mới501tệp build/import trực tiếp từ wheel và host-library digest đạt;
  không cài vào Python đang phục vụ. Receipt
  `.runtime/p84-package-c1eca0c02dae4b4b92d743726b13986c/receipt.json`.
- Image mới `sha256:8ad12b67515a2f98165c975934b598a714fa7c153ebca64c2e7729171e5a71de`,
  host-library SHA256 `90d5e923b27a3fc500ef4adaec99e8590ffec911956b1471127beccdbefa06ec`.
  Context so khớp hash thư viện host trước/sau build. Manifest
  `.runtime/p84-codex-image-4afe9d6609b84343ac70aa63cc8fc9de/image.json`.
  Container thật đạt normal fixture, tool injection/no-auth/cross-SME denial và
  cleanup. Volume synthetic đã xóa. Receipt
  `.runtime/p84-docker-acceptance-89266164019d4e3aafc1da9eed92c271/receipt.json`.
  Không có cuộc gọi thuê bao thật hoặc native PAO live job trong lượt này.
- Full backend mới bắt đầu11:31 ngày19/10 tại
  `.runtime/p84-native-tests-0ab1a8a970f04ff8abaad5b983d84a67`.
  Lượt này sau đó kết thúc đạt2343/2343 như kết quả hiện tại ở đầu báo cáo;
  không cộng focused với full cũ. Không chạy runner thứ hai chung pao_test/Redis15.
  Tại thời điểm bắt đầu full, primary vẫn0071, chưa đăng ký device hoặc bật CLI.

### Chuẩn bị cài có kiểm soát và đăng nhập của chủ doanh nghiệp

`scripts/prepare_p84_native_release.py` chỉ lập kế hoạch nguồn sau khi full
receipt và JUnit khớp, không fail/error/skip, đúng frozen candidate. Danh sách
30tệp cố định loại `.env`, frontend và tài liệu cũ; đối chiếu preimage với
checkpoint để từ chối sửa chồng lấn. Thư viện host phải đúng bản đã kiểm. Hợp
đồng TypeScript được lấy riêng từ bản sao frontend đã typegen/typecheck/build,
đối chiếu input UI, lockfile, OpenAPI và27supplement; không lấy declaration cũ
trong candidate để đi cùng OpenAPI mới. Đây là tệp sinh tự động trong contracts,
không sửa layout UI. Công cụ không cài, migrate, bật feature, đăng nhập hoặc cấp
quyền.11unit offline đạt;
chưa nằm trong lượt backend full đang chạy, không cộng vào số test backend.

`scripts/setup_p84_codex_profile.py` là công cụ do người dùng chạy trong
PowerShell tương tác **sau khi backend/runtime CLI đã cài và kiểm tra đạt**.
Nền tảng0072 nay đã cài; công cụ vẫn từ chối trước khi hỏi mật khẩu nếu
runtime/contract không khớp. Không phải Settings UI của E.

- Người dùng tự nhập email/mật khẩu PAO tại máy; công cụ dùng login API thực,
  kiểm session và quyền owner hiện tại của đúng SME đã chọn. Receipt lựa chọn
  không cấp quyền. Không tự ký bearer hoặc đọc auth cache Codex/Javis sẵn có.
- Chủ doanh nghiệp xác nhận rõ trước tạo/chuẩn bị profile riêng. ID profile có
  thể dùng lại khi bị ngắt; không tự tạo hồ sơ mới hoặc retry lệnh bị từ chối.
- Chỉ chấp nhận đúng lệnh device-auth cố định, binary/image và volume có scope;
  chạy trong console của người dùng, không capture/lưu mã thiết bị. Không chạy
  công cụ này qua terminal được ghi log tự động của agent.
- Container login có tên/nhãn operation riêng. Timeout/hủy vẫn thử dọn đúng ID,
  image và nhãn đã xác minh; không xóa volume. Không xác minh cleanup thì dừng,
  không tiếp tục check-auth hoặc suy luận. Auth trong profile do Codex quản lý.
- Tắt redirect/proxy cho API loopback; không in response lỗi thô hoặc token.
  Cuối cùng thu hồi riêng phiên PAO vừa tạo, không logout Codex/PAO phiên khác.
- Chỉ check-auth sau login; không cấp grant, gọi model, đổi default, chia thuê
  bao hoặc công nhận entitlement/quota. Những chốt đó vẫn cần nghiệm thu C.

12unit offline của công cụ đạt với API/process/Docker/temp giả; không phải login
thật hoặc kiểm containment login thật. Lượt unit đầu bị giới hạn event loop của
sandbox Windows và được ngắt riêng qua session25933. Lần xin quyền xác định PID
đã bị reviewer capacity từ chối, không thực thi. Unit thuần sau đó không tạo
event loop/socket thật; runtime không bị nới quyền hoặc bỏ cleanup. Lượt full
backend đã được cấp quyền từ trước vẫn tiếp tục, không bị dừng hay chạy lại.

Nguồn candidate sau chuẩn bị được lưu/đối chiếu integrity riêng tại
`.runtime/p84-candidate-source-631b279b017e478ba52737cb5deb37b0`.
Receipt ghi rõ `candidate_qualification_passed=false`; không phải checkpoint
database, không thay thế migration/restore hoặc full regression mới. Tình trạng
tiếp tục ở `.runtime/p84-native-current-status.json`; lựa chọn SME giữ nguyên.

## Lịch sử lỗi giữ nguyên

### Sửa công cụ đăng nhập sau owner thử thật19/10

Log an toàn xác nhận14:34:28 login PAO, `/v1/me` và context đều200;
14:34:39 tạo CLI connection201/prepare200;14:34:41 kiểm lại quyền200 và
thu hồi riêng phiên PAO200. Chưa gọi check-auth hoặc suy luận. Lỗi xảy ra trong
operator `official_login`: pin truyền vào Docker `check_profile` thiếu
binary_sha256/binary_version/runtime_image_id, nên guard đúng đã từ chối trước
khi mở Codex. Không phải lỗi mật khẩu PAO ở lượt này.

Đã tái hiện12pass/1fail ở bài regression mới, sửa builder `login_pin` đủ pin
từ registry đã kiểm.14unit offline đạt sau sửa, có gọi guard thật với Docker
response giả và kiểm cả ba trường thiếu đều bị từ chối trước Docker I/O. Không
nới guard, đổi backend, host library/image pin hoặc chạy lại baseline2343 cũ.

Kiểm tra metadata thật chỉ SELECT trong transaction read-only và Docker inspect
volume/image bằng chính builder đã sửa: đạt. Connection hiện có
`398aa03c-0465-426c-ad95-12d1d1cc475d`, version2/pending, đúng owner/SME đã chọn,
không có setup fence treo. Không đọc auth file, tạo profile mới, login hoặc gọi
provider. Backend binding92ed... và host-library90d5... vẫn nguyên.

Người dùng yêu cầu trải nghiệm bấm Kết nối như Javis, không dùng PowerShell làm
onboarding khách hàng. Chưa mở thêm terminal hoặc tự đổi sang dùng auth host.
Tận dụng auth có sẵn và UX login trong Settings cần thiết kế/kiểm chứng riêng;
không được sao chép token hoặc bỏ chốt cách ly Windows chỉ để bỏ bước nhập liệu.

1. Native test đầu0test vì runtime phục vụ không có pytest; chỉ thư viện test
   được cài vào `.runtime/p84-native-test-deps`, không sửa môi trường phục vụ.
   Guard cũng phát hiện cache Next thay đổi do startup; lượt cũ vẫn fail. Guard
   mới chỉ loại hai cache sinh tự động, vẫn kiểm toàn bộ app/config/lock thực.
2. Lượt28test đầu13pass/15fail: lỗi validation phản chiếu sentinel và các trigger
   cũ chưa biết kind CLI. Đã sửa redaction và migration, không bỏ assertion.
3. Lượt kế16pass/12fail do model activation trigger chỉ nhận kind model cũ.
   Đã mở rộng đúng kind mới, bảo toàn nhánh cũ; các lượt fail không bị ghi đè.
4. Schema draft được tái tạo trên **pao_test** (fixture dùng lại được), không
   drop/restore/migrate primary, không phá database/volume của dự án khác.

## Phục hồi local19/10

Docker/PAO tắt khi quay lại. Khởi động Desktop Hidden một lần; server29.4.3,
chỉ start đúng PG/Redis ACOS có sẵn, cả hai healthy. Idle kiểm0job trước bật API,
ARQ, Web và Ollama theo launcher0071 hiện hành. Telegram/Studio và connector ngoài
vẫn tắt. API/ready/web200, ARQ healthy. Không reset, xóa volume, reboot hoặc sửa
settings Docker. Kiểm tra chỉ đọc installed tiếp theo đạt:407operations/schema0071/
153bảng,3replay và3archive đọc được, API/ready/Web200, business hash và `.env`
không đổi trong đúng lượt kiểm tra. Receipt `.runtime/task-delete-live.json`.
Không dùng kết quả này để đóng sự cố drift lịch sử hoặc nghiệm thu CLI.

## Doanh nghiệp đã chọn

Người dùng chọn **Pao Business Operating Systems**. Đối chiếu chỉ đọc tìm đúng
**PAO-Business Operating Systems**, hiện có một owner đang hoạt động là
`demo@pao.local`. Lựa chọn được lưu riêng tại
`.runtime/p84-selected-enterprise.json`; đây chỉ là lựa chọn, không tạo profile,
không login hay cấp grant. Mọi bước đăng ký/kích hoạt vẫn cần session PAO đã xác
thực và membership hiện tại; không tự tạo bearer để thay cho consent của owner.

## Việc còn lại trước khi kích hoạt

1. Đã đạt full regression, migration/restore, contract/wheel/image pins và cài
   native backend có checkpoint/read-only live proof; không chạy lại baseline đó.
2. SME và actor đã chọn; owner tự đăng nhập profile Codex riêng qua flow chính thức,
   chọn model có quyền, consent/grant, chạy một job native có đối soát usage.
3. Kiểm quota/cancel/revoke/recovery với profile thật có phạm vi. Không báo quota
   thuê bao bằng token estimate, không tự retry hoặc mua thêm credits.
4. Sau C mới tiếp D/E; không tự gỡ Ollama hoặc thay model các job cũ.

Nguồn đối chiếu: [OpenAI Docs — app server](https://learn.chatgpt.com/docs/app-server),
[config](https://learn.chatgpt.com/docs/config-file/config-reference),
[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox).
Các cờ được kiểm bằng binary thực tế; không áp flag mới của tài liệu vào bản cũ
mà bỏ qua strict-config hoặc kiểm tra catalogue công cụ.
