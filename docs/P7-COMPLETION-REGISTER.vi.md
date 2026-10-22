# P7 — Sổ gate và ranh giới nghiệm thu

Chú thích 11/10/2026: thứ tự tiếp theo do [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md)
sở hữu (toàn S2 đạt local14/10 theo [nghiệm thu tích hợp](S2-FINAL-INTEGRATION-2026-10-14.vi.md);
S3.1A+B đã đóng local15/10 theo [evidence](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md);
S3.2A/B đã source_verified; tiếp theo S3.2C — bridge/webhook/report integration).
Các kết quả bên dưới là bằng chứng10/10, không
thay kiểm health hiện tại; P7.5/live channel còn mở, không chặn audit/thiết kế S0.

Ngày10/10/2026. Target `F:\PAO-ACOS`; không sửa protected source `F:\Apex`.
P7 chưa được gọi là nghiệm thu toàn bộ khi thiếu P7.5 mic thật và live channel.
P7.1–P7.4 code và nghiệm thu LOCAL đã đóng; main đang0048. Không bắt đầu lại P6
hoặc lặp các gate local đã đạt chỉ để tăng số test.

| Checkpoint | Code/gate local | Gate thực tế |
|---|---|---|
| P7.1 shared ChannelAdapter | Envelope local/Telegram, HMAC identity, workspace/Brain/session mapping, durable dedup; một Run service | Telegram account/destination thật chưa nghiệm thu |
| P7.2 transport | Existing allowlist, shared parser, exponential reconnect, outbox claim/ACK/unknown/reconcile, revoked actor/peer/key no legacy fallback | Chưa gửi tin thật; no-resend không có nghĩa exactly-once ở provider |
| P7.3 customer inbox | Owner/admin inbox, human/quiet controls, immutable control audit, bound Brain grounded excerpts, tools/CLI/approval denied, rate limits và retention | Zalo/Slack/WhatsApp chưa connector/audit; chưa nhập khách hàng thật |
| P7.4 local voice | Consent, scoped turn ledger, reviewed transcript → shared Run/SSE, TTS chỉ response của Run đó, VAD, mute/cancel, late-result discard, draft reconnect/mobile | Chưa nghiệm thu microphone/echo của thiết bị thực tế |
| P7.5 acceptance | Harness HTTP/browser/WebAudio synthetic + local engine benchmark chuẩn bị; không tự mở mic | Tiếng Việt mic thật/ồn, WER/latency, barge-in và cancel giữa tool: chưa đạt |

## Bằng chứng gate đã chạy

- Shared admission trước channel:69 regression chat/engine/knowledge passed.
- Telegram/chat legacy47 pass; focused channel + helper boundary12pass.
- Voice/channel/legacy voice18pass; latest channel/voice/contract22pass.
- Browser P7: HTTP/DB thật, inbox quiet/human/manual-reply dedup, permission
  denied giả lập, WebAudio synthetic, consent/reload/scoped Run/cancel/mobile.
  Đây không phải trình duyệt đã nhận quyền mic thật hoặc STT audio microphone.
- ARQ/Redis15 thật:2 Run channel/voice hoàn tất qua dispatcher chung; model fixture
  không network. Cleanup Windows theo workaround ARQ hiện có; deprecation warning
  thuộc installed dependency, không bỏ assertion queue.
- Populated restore: hash toàn bộ schema/data khớp clone, identity/audit triggers
  còn hiệu lực; fresh process replay không tạo Run khác và unknown không resend.
- Clone0046→0048→0046→0048:109 business tables cũ giữ hash,5 bảng mới rỗng.
- TypeScript noEmit và runtime/SSE8/8 đạt. Production build21 static entries đạt;
  Hooks warnings ghi nhận, không phải lint sạch warning.
- Full regression bản source cuối: **1156passed/0failed/0skipped**,1382.17s.
  27warnings thuộc ARQ deprecated.close; không loại bỏ wall-clock recovery tests.
- Browser tổng hợp P6/P7: **8/8passed**,177.88s,3ARQ deprecation warnings.
  Goal harness sửa race request/teardown, không bỏ assertions chức năng.
- Production build21/21, runtime/SSE8/8 và shell UI12module cũ đạt. Build vẫn có
  Hooks warnings; không gọi đây là lint sạch hoặc production đã nghiệm thu.
- Rollout0046→0048: phục hồi chính bản backup vào clone và đối chiếu primary
  trước migration;109business tables cũ giữ hash,5bảng P7 mới rỗng. Idle0 trước
  stop API/worker; xác minh executable/creation-time, giữ Web/Ollama/volumes.
- Live gate đã đạt: API/ready/Web200,workerhealthy,41routers/308operations khớp
  OpenAPI source, exact backend binding khớp và M2archive replay3/3.
  `check_p7_live.py` ban đầu thiếu workspace query ở skills; đã sửa đúng contract
  rồi chạy lại toàn bộ checker, không sửa backend hay bỏ assertion.
- Schema primary0048; source binding
  `a298c9003a8ee07db4f164e2786c36f542f814446bf0ed268c9a6013812acdb2`.
  Channel/voice/Telegram/Meta/Goal/workflow/event delivery flags vẫnfalse;
  external send0. Real microphone/live channel/production acceptance vẫnfalse.
- Checkpoint sau rollout verified816source/115physical tables/3artifacts/0048:
  `.runtime/checkpoints/p0-20261010T115820-21e9dc90/manifest.json`. Health/idle
  chạy lại sau checkpoint vẫn đạt; voice_transcribing/channel_sending đều0.
- Các baseline flags `tools_enabled`, `agent_runtime_enabled`,
  `engine_contract_enabled` hiệntrue và được giữ nguyên; không gọi chúng là tắt.
  P7 không đổi `.env`. Customer channel vẫn bị chặn tools/CLI bởi backend guard,
  độc lập các flags baseline; channel/voice mới chưa bật trên primary.

### Rà soát quyền trước rollout

- Thu hồi TelegramPeer hoặc đổi identity key chặn inbound và cả Run đã queued;
  không chỉ chặn delivery. Negative test xác nhận không gọi model hoặc legacy.
- Outbox result đối chiếu Run/session/workspace/binding, quyền nguồn và nội dung
  hiện tại trước send; API mask cached result khi nguồn bị trash/thu hồi. Retention
  purge không cho gửi lại cached answer cũ. Không cam kết thu hồi tin đã gửi.
- Reconcile fingerprint gắn delivery ID; không tái sử dụng cùng khóa owner
  observation để xác nhận nhầm một tin khác. Unknown không tự resend.
- Focused channel/voice/factory24/24 đạt; Goal + P7 browser2/2 đạt sau sửa race
  teardown của harness. Giữ nguyên assertions lost-ACK/replan/cancel/gate-off.
- Checkpoint trước migration verified815source/110physical tables/3artifacts,
  revision0046: `.runtime/checkpoints/p0-20261010T112904-02ee6b6e/manifest.json`.
  Source binding `a298c9003a8ee07db4f164e2786c36f542f814446bf0ed268c9a6013812acdb2`.

## Engine voice đã chạy thật — nhưng tiếng Việt chưa đạt chất lượng

Public model `Systran/faster-whisper-small` pinned revision
`536b0662742c02347bc0e980a01041f333bce120`:4files,486212372bytes, SHA256 kiểm
theo LFS metadata. Nằm riêng `.runtime/models`, không vào source backup. Download
public không dùng token; không đổi `.env`, không mở mic hoặc upload audio.

Synthetic SAPI→Whisper3/3 transcripts không rỗng; STT latency15046/4202/18842ms,
WER1.2727/0.6667/0.875 theo normalize NFC lowercase + whitespace words. WER có thể
>1 do insertion. Không lấy số này làm WER của người nói thực tế. Máy chỉ có SAPI
Microsoft David/Zira `409` (English US), nên synthetic Vietnamese chất lượng
thấp; **không nghiệm thu chất lượng tiếng Việt hoặc realtime latency**. Cần
giọng TTS tiếng Việt local phù hợp và benchmark mic thật; không tự cài language
pack hoặc thay cấu hình Windows toàn máy. Piper đã là provider optional trong
engine, nhưng chưa có executable/model tiếng Việt được nghiệm thu ở đây.

Metadata private: `.runtime/p7-voice-model.json`,
`.runtime/p7-voice-synthetic-smoke.json`. Không lưu raw synthetic audio.

## Cấu trúc và ownership

- `modules/conversations/requests.py`: admission chung cho HTTP/channel/voice;
  `commit=False` ghép Run + receipt/turn trong một transaction. ARQ dispatcher
  hiện có phục hồi queued Run, không tạo engine hay queue owner mới.
- `modules/channels/service.py`: identity/inbound/control/outbox/retention.
  Telegram native chỉ private + allowlisted peer; binding mất gate/identity/key
  không rơi lại vào legacy authority. Không tự tạo tài khoản khách có JWT.
- `modules/channels/api.py`: management API owner/admin, local adapter để nghiệm
  thu không network, human reply chỉ lưu outbox; `queued` chưa chứng minh delivery.
- `modules/channels/voice_turns.py`: consented ledger; `/submit` dùng admission
  chung; `/speech` lấy response từ Run đã hoàn tất, kiểm lại scope sau synthesize.
- `runtime.dispatch`: cùng owner dispatch/collect; retention tiếp tục khi channel
  manager tắt. Chỉ một Telegram bridge/poller đã có với advisory lock.
- `0047` thêm4 channel tables + Run context; `0048` thêm voice_turns. Identity
  bindings/voice turns và control audit được DB triggers bảo vệ.
- UI `/channels`, voice trong PAO AI Activity + mobile panel. Orb12 modules cũ giữ
  nguyên; sidebar thêm Inbox/Channels (15 links tính cả Goal/Review).

## Cấu hình, privacy và hạn chế rõ ràng

- Default `CHANNELS_ENABLED=false`, `CHANNEL_AUTOREPLY_ENABLED=false`,
  `VOICE_TURNS_ENABLED=false`; không sửa secret/.env hoặc enable delivery thật.
- `CHANNEL_IDENTITY_KEY` tùy chọn >=32 ký tự, ổn định và giữ riêng khỏi source
  backup. Nếu trống dùng JWT_SECRET. Đổi key/JWT phải quiet channels, backup và
  plan rebind có duyệt; peer đã bound sẽ fail-closed thay vì legacy fallback.
  Identity hash là pseudonym, **không phải ẩn danh**; TelegramPeer vẫn chứa ID.
- Customer actor là tài khoản nội bộ role operator, Brain editor theo admission
  hiện có; nên dành actor/Brain riêng. Profile chỉ grounded excerpts; không LLM
  tùy ý, tool/skill/coding hoặc tự approval. Nếu thiếu nguồn thì không bịa câu trả lời.
- Nội dung customer hết hạn1–30 ngày (mặc định7): xóa inbound/outbox body, Run
  prompt/response, Message và RunEvent chứa nội dung; giữ request hashes, identity,
  audit metadata và immutable source references. Không purge Run đang active.
  Backup/log/source documents có policy riêng, **không tuyên bố GDPR erase**.
- Voice raw audio không lưu DB hoặc artifact. File tạm local của engine bị dọn;
  nháp transcript hết hạn24h qua dispatcher; submitted transcript theo lịch sử
  chat, không áp thời hạn24h cho message đã gửi. Audio/transcript không gửi cloud.
  Ephemeral decoder/SAPI files vẫn tồn tại trên disk khi đang xử lý. Nếu process
  bị kill/mất điện trước finally, file tạm có thể còn lại: cần kiểm kê/cleanup
  exact-owned files và crash privacy drill trước production. Không tuyên bố
  zero-disk audio hoặc đảm bảo mọi filesystem backup bên ngoài đều loại trừ.
- Cancel ngăn admit/phát kết quả muộn; computation STT đang chạy có thể hoàn tất
  rồi bị bỏ kết quả. Không hứa rollback hành động tool đã thực hiện trước cancel.
  TTS có timeout60s, owned process bị kill khi coroutine bị cancel; không stop
  process khác theo tên. Turn cancel rechecks/URL abort chặn phát audio muộn.
- TTS local giới hạn2000 ký tự và fail-closed, không âm thầm cắt answer. Telegram
  tin dài chia phần <=3500 UTF16 units, mỗi phần có receipt riêng; nhiều phần
  không có transaction atomic trên provider. `unknown` không tự resend.
- HTTP429 positive rejection có retry hữu hạn; network/lost ACK không chứng minh
  provider chưa gửi. Owner reconciliation là quan sát thủ công, không provider
  query; tuyệt đối không gọi đó là delivery proof tự động.
- Không thêm cloud voice, account cá nhân ngầm, connector Zalo/Slack/WhatsApp hoặc
  Terms bypass. Meta/M3 vẫn hoãn; M5B live outcomes không suy từ synthetic P7.

## Nghiệm thu P7.5 cần thực hiện sau local rollout

Bộ 20 câu và hướng dẫn cho người mới: [P7.5 tiếng Việt](P7-VI-VOICE-ACCEPTANCE.vi.md).

1. Bật voice local có chủ đích, mở PAO AI trên máy thử và chấp thuận microphone;
   thử từ chối quyền rồi cấp quyền lại, không auto reconnect mic sau reload.
2. Đọc tối thiểu20 câu tiếng Việt (câu ngắn/dài, dấu, số, thuật ngữ, tên riêng),
   người nghiệm thu ghi ground truth; đo WER và latency median/p95 từ voice turns.
3. Lặp trong phòng yên tĩnh và môi trường ồn/echo; không lấy SAPI synthetic làm
   ground truth cho giọng người. Đặt threshold sau khi đo baseline thật, không
   nới ngưỡng chỉ để đánh dấu pass.
4. Ngắt lời giữa TTS, mute, cancel giữa STT/Run/tool, đổi session, đóng panel,
   refresh tab và reconnect SSE: không tạo Run trùng hoặc phát TTS khác session.
5. Kiểm tra raw temp audio được dọn, không audio trong logs/backup, draft24h và
   chat retention theo policy; không tự ghi mic để làm dataset.
6. Nếu cần Telegram thật: owner xác nhận private peer/destination, token cấu hình
   riêng tại máy, chỉ một bridge; thử dedup/restart/takeover/lost ACK có quan sát.
   Chỉ gửi tin kiểm thử vô hại đã duyệt; không tự bật kênh hoặc quảng cáo.

Gate chưa đạt sẽ được giữ nguyên trong roadmap, không lặp P6 hoặc gọi P7 hoàn tất
production. Sau P7 local, M6 UX consolidation là nhánh kế tiếp; real-channel/mic
acceptance có thể theo track riêng. M5B live business vẫn cần M3/Meta readiness.
