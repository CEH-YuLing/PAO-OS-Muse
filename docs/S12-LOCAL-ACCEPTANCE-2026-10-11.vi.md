# S1.2 — Cô lập dữ liệu phía client khi chuyển SME

Ngày 11/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`.
Trạng thái: **local_accepted**. Không triển khai S1.3 trong lượt này.
Thiết kế tại [ADR-S12](ADR-S12-CLIENT-SCOPE.vi.md). Đây là checkpoint client,
không phải toàn S1 hoặc SaaS production.

## Đã triển khai

- Transport dùng ticket/abort theo thế hệ context; JSON/raw Response/clone/body/
  SSE có fence; request authenticated ép no-store. Caller signal/If-Match và
  headers được giữ, Authorization lấy phiên hiện hành.
- Switch/logout/role đổi/mất membership hủy in-flight phía trình duyệt và remount
  draft/subtree. Không cancel, repin hoặc chuyển workspace của server run.
- Download Brain/file/ZIP/chat/attachment dùng helper kiểm body xong mới tạo URL
  và click; switch thu hồi URL. Voice giữ cleanup audio/mic, thêm actor vào hint.
- Pending prompt/voice hint dùng namespace actor/SME/resource, bỏ hint legacy
  không scoped. Logout dọn namespace actor, không xóa namespace user khác.
- Focus/pageshow/visibility và poll 30 giây khi visible kiểm membership bằng
  `/v1/me`, timeout 5 giây, fail closed; có nút refresh thủ công. Revocation
  xóa active context/preference và yêu cầu chọn rõ, không fallback sang SME khác.

## Gate của lượt này

| Gate | Bằng chứng |
|---|---|
| Pure frontend/runtime/SSE | 25passed,0failed,0skipped;13transport/storage +4tenant +8runtime/SSE; source cuối có cleanup/unlock reader và native method detection |
| TypeScript | noEmit đạt trước browser; production build kiểm lại source cuối |
| Backend focused | 35passed,0failed,0skipped; tenant context/chat management/voice turns; lần cuối34.83s |
| Browser S1.2 | 1passed46.65s; rerun source cuối1passed49.05s; Next rewrite/SSE/API/DB thật, pao_test/Redis15 |
| Browser S1.1 hồi quy | 1passed45.91s; scoped tasks/chat/settings,role,reload,tampered preference,mobile |
| Browser P7 hồi quy | 1passed44.55s; HTTP thật, synthetic mic/STT; consent/deny/draft reload/shared run/mobile/channel dedup đạt, không mic/channel thật |
| Production build | Source cuối exit0,21/21static entries; compile7.0s; .pao-build-check riêng; lint/typecheck đạt nhưng vẫn warnings Hooks cũ, không tắt lint |
| UI12modules | PASS all12routes trên Web3200 bằng API fixtures; chỉ UX/layout, không business live acceptance |
| Backup source unit | 2passed; frontend .d.mts được include, .env/.env*.d.mts/runtime bị exclude, không overwrite archive |
| Live runtime/integrity | API/ready/Web200,workerhealthy; contract309/source/saved/live khớp,schema0048,binding không đổi,M2archives3/3replay |

S12 report source cuối: `.runtime/s12-browser-d1645fe861d44c3189e176449bee182b/browser.json`.
Lần trước: `.runtime/s12-browser-355bff87255e4fdc8cbe471543512e3b/browser.json`,
screenshot `s12-mobile.png` đã xem, không overflow ngang ở390px; source cuối
cũng có screenshot và assertion không overflow. S11 hồi quy report tại
`.runtime/s11-browser-48d38f0391294593a6c73dc1c3a53c99/browser.json`;
P7 tại `.runtime/p7-browser-17dfa133587b4499b691cfba7786b446/browser.json`.
HTTP thật nhưng run/events được seed tổng hợp trong pao_test, không worker/LLM
execution thật. Export thật131KiB được pause sau64KiB: browser đã nhận headers200,
switch SME rồi release không sinh download; export SME hiện hành vẫn tải được.
Chuyển SME lúc SSE đang chạy không hiển thị delta A trong B, không gửi cancel
và DB/run vẫn giữ session/workspace A, trạng thái running. Hai tab độc lập;
legacy/wrong-SME prompt bị bỏ; đúng prompt B hoạt động rồi reset khi chọn A.
Focus nhận role viewer; revoke membership xóa context, API sessionA trả404;
chọn B rõ ràng rồi reload vẫn đúng B.

## Các lỗi của test harness đã xử lý

Ba lần thử S12 ban đầu chưa đạt (không ghi như pass): assertion dùng workspace_id
không có trong RunOut (sửa sang session_id và kiểm workspace ở DB); fixture thiếu
engine_contract_enabled cho chat export (bật đủ chỉ trong test, thêm preflight);
Playwright browser.newPage không cho thêm tab cùng context (opt-in multiTab bằng
newContext). Giữ mọi isolation assertion, không nới API/permission để lấy pass.
Hai lượt đầu có chạy lại bộ focused; sau bổ sung `--browser-only`/`--s12-only`,
chỉ rerun browser bị ảnh hưởng, không bắt đầu lại checkpoint đã đạt.
Source cuối còn làm rõ dependencies của prompt effect để không thêm warning
Hooks mới; S12 rerun đạt. Các warnings Hooks kế thừa chưa refactor ngoài scope.
Trong lần thử SSE bị hủy có log asyncpg/SQLAlchemy CancelledError lúc đóng
connection; chưa làm thay đổi backend trong S1.2. S1.3 cần kiểm tra shutdown/
pool cleanup trong corpus cancellation/permission-loss, không gọi chức năng
isolation frontend đã đạt là bằng chứng server cleanup hoàn hảo.

## Safety và giới hạn

Không đổi `.env`, secret, gate thật, backend product source, schema/contract hoặc
execution binding. Không restart API/ARQ/Docker, không gọi provider, microphone
thật, send channel, Ads write/chi tiền/public deploy. `.env` SHA256 giữ
`5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
Binding giữ`e76a4db458aed99d20cbecd002c0a455ded25d6e443e49bdabc1c680de02c5f1`.
Protected Apex/Javis và dirty changes có trước giữ nguyên, không Git commit/push.

Không chạy full1156backend hoặc toàn8browserP6/P7; chỉ focused/browser nêu trên.
Poll không phải instant revocation; server vẫn kiểm từng API/action. Không thể
rút lại file đã tải hợp lệ, memory mà người dùng đã đọc hoặc bản sao do họ tạo.
Worker/job/outbox/export/files negative corpus thuộc S1.3, chưa được nghiệm thu
toàn bộ ở đây. Custom AI per job giữ kế hoạch S2/S5.3, không gán vendor cứng.
M3/live providers,P7.5real mic/channel,reboot/offsite/production vẫn gate mở.

## Checkpoint và việc tiếp theo

Code,25pure/runtime,35focused,3browser gates,UI12 và build21 đã đạt.
Source/DB checkpoint được seal và thử exact restore trước bàn giao; đường dẫn
và kết quả verify ghi bên dưới sau khi hoàn tất. Source backup không chứa secrets.

Khi seal phát hiện policy archive kế thừa bỏ sót `.d.mts`. Sửa riêng script backup
để bổ sung4declarations ở apps/web/lib vào ZIP/manifest, verify hash/entry set và
source không thay đổi; không sửa backend operation module để tránh đổi binding.
Checkpoint839source092141 đã basic/exact DB restore đạt, nhưng không coi là bản
frontend hoàn chỉnh vì thiếu declarations. Giữ các checkpoint trung gian, không
xóa/ghi đè source/dump; bản cuối phải chứa đủ4declarations đã kiểm.

**Việc tiếp theo duy nhất: S1.3 — worker/job/outbox/files/export/API negative corpus.**

## Checkpoint cuối đã verify

`.runtime/checkpoints/p0-20261011T092442-c85ede20/manifest.json`:844source,
đủ4frontend declarations,115physical tables,3M2archives,schema0048. Basic ZIP/
manifest/hash verification đạt; exact restore row hashes114business tables và
schema definitions equivalent đạt,primary unchanged,binding giữ nguyên.
Clone `pao_s03_restore_e22a5373be57411888f5d1444941e032` đã dọn; chỉ xóa clone
do lần thử này tạo,giữ source/dump/checkpoint. Sau seal chỉ thêm đoạn self-reference
này,không đổi code; archive không chứa chính đoạn này.

Probe cuối API/ready/Web200 và workerhealthy,live contract/binding/archives3/3
replay khớp,hash `.env` không đổi. Owned Web3201 không còn listen sau browser
cleanup. Master/README/kế hoạch/ADR-S02/P6/P7 đã cùng next-step S1.3; historical
S11 acceptance giữ nguyên bằng chứng và next-step tại thời điểm của nó.
