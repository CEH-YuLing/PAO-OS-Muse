# S2.1B2a — Model execution-denial fence

Ngày11/10/2026. Target `F:\PAO-ACOS`. Trạng thái **local_accepted** cho B2a;
browser/rollout/pre-deploy exact restore đạt; seal cuối ở phụ lục. [ADR](ADR-S21B2A-MODEL-EXECUTION-FENCE.vi.md)
ghi thiết kế/lock/rủi ro; [master](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu thứ tự.
Không sửa protected Apex/Javis, không commit/push hoặc mở MCP/Ads cùng checkpoint.

## Kết quả triển khai

- Kết nối model đã đăng ký ở B1 bị deny trên default/choose/admission/resolve/
  queued worker và publication; staged, revoked và native tombstone không trả
  lại legacy permission hay ngầm fallback Ollama. Grant của owner cũng không
  tự được activate. Explicit local/knowledge selection vẫn hợp lệ.
- Run cloud mới pin version/mode legacy_unregistered/workspace/actor/brand/source
  trong immutable engine snapshot; không trả pins/credential/hash ra public DTO.
  Snapshot cũ thiếu pin không bị repin, nhưng không được bỏ qua registry recheck.
- Guard wrapper fresh trước/sau planner/extraction/stream; ciphertext hash/status
  query trong DB, member active/nonviewer của pinned cloud Run kiểm lại. Kết quả
  muộn không thành plan/delta/completed hoặc memory facts; stream bị đóng.
- Publication runtime/specialist/Studio và memory transaction được fence bằng
  Workspace KEY SHARE, serialize với B1 mapping/revoke FOR UPDATE. Memory lock
  order Workspace→owner/job; lỗi authority/source change terminal, không retry
  với credential mới. Không giữ DB lock qua network hoặc hứa native cancellation.
- Schema0049,117business/118physical tables và317operations/42routers giữ nguyên;
  không migration mới, credential copy, API DTO/UI/transport/provider-auth thay đổi.

## Gate đã thực hiện trong lượt này

| Gate | Kết quả |
|---|---|
| `check_s21b2a_tests.py` engine/model/grants/inventory/memory/chat/factory/Studio/fresh recovery |190passed/0failed/0skip,168.37s; lúc collect có27fence cases |
| Corpus cuối29fence + S13/private Brain/skill version/fresh-process/channel/voice/P7restore |81passed/0failed/0skip,113.01s |
| Node runtime/SSE/tenant + TypeScript |25/25 và noEmit đạt |
| Isolated frontend production build |Đạt21/21static pages; live Web cache không đổi |
| AST mới/ảnh hưởng |8files đạt |
| Existing OpenAPI/schema.d.ts vs pre-checkpoint |File hashes khớp;317operations, không generate DTO mới |
| Git whitespace Windows CRLF |Đạt |
| Real ARQ/Redis15 model |2cases, mỗi case2actual admission-created payload/IDs; A registered deny, B same provider/model completed; factory/stream chỉ1 |
| Real queue của S13 và P7 |2source membership-revoke và1shared channel/voice dispatcher đạt |
| Browser S12/S11/P7 |1+1+1passed,43.03s/36.33s/28.40s; HTTP/DB thật, voice synthetic |
| Live reload/contract/replay |Đạt317/source binding khớp/M2replay3/3,0049 |
| API health/ready/Web và worker |200/200/200,workerhealthy;Telegram bridge disabled |
| Live inventory/staged/auth/validation |1manager scope,rows0,401/redacted422/no-store; không tạo main mapping |
| Checkpoint/pre-deploy exact restore |872source/118physical/117business/3archives/0049; hash/schema tương đương,primary unchanged |
| Final checkpoint/restore |Phụ lục niêm phong cuối bên dưới |

Các nhóm có test trùng, không cộng thành tổng unique. Hai ca bổ sung sau
190-case collect (memory resolver rotation terminal, historical missing pin)
đã chạy trong81-case group. Harness focused hiện tại có192cases nếu chạy lại
nguyên10files; không gọi con số192 là kết quả invocation190. Final corpus29
có2ARQ modelcases; queue entries/payload do admission thật sinh, chuyển đúng hai
entry của test sang queue riêng rồi cleanup chỉ queue/keys của invocation.

**Không chạy lại full backend trong B2a.** Full1240 của B1 là lịch sử trước thay
engine/runtime này, không đại diện full suite bản mới. Không gate Settings/active
grant mới hoặc mic/Meta/Google/Telegram thật. Warnings vẫn React Hooks và ARQ
deprecated.close; không bỏ assertion hoặc tắt gate để pass.

Lượt đầu174pass/6fail: test mới dùng sai ARQ import/MemoryJob.id và giả định
execution_plan trống (Javis shadow metadata vốn tồn tại); test router cũ đòi raw
gateway/api_key thay vì guarded wrapper. Đã sửa assertions theo contract thật,
vẫn kiểm late-sentinel không xuất/không plan/delta và factory dùng đúng key fixture.
Lượt thứ hai181pass/3fail: deleted source chooser đúng deny với unavailable
nhưng test đòi error khác; ARQ enqueue jobID đã tồn tại từ HTTP admission nên queue
riêng chưa nhận job. Đã giữ nguyên payload/ID và chỉ chuyển hai owned queue entries,
assert cả hai worker jobs thực chạy. Thêm missing-default guard chống fallback
sau native deletion, thêm source/member/brand fresh checks và memory lock order.
Code cuối190+81 đạt; không sửa backend source trong lúc fresh-process test chạy.

## Rollout và checkpoint

Baseline trước sửa API/ready/Web200,workerhealthy,Docker/PG/Redis healthy,idle0.
Không cần Docker recovery. Pre-change backup0049 giữ tại:
`.runtime/checkpoints/p0-20261011T140749-c8993b8f/manifest.json`
(867source/118physical/3M2archives,verified). Pre-deploy/final exact restore ghi
ở đây và phụ lục; không dùng startup/backup creation làm restore đạt.

Pre-deploy checkpoint current source/docs:
`.runtime/checkpoints/p0-20261011T143538-b3df851a/manifest.json`,872sourcefiles,
118physical/3M2archives/0049. Exact restore117business row hashes/schema/archive
khớp; chỉ clone `pao_s03_restore_f0e7333bf6c24cb183e5668b50a61d8c` đã dọn.
Không delete nguồn/DB chính; source/dump/manifest giữ nguyên cho recovery.
`restart_acos_backend.ps1` kiểm executable/start-time cả hai processes và idle,
thay chỉ API PID22548/worker18580. Docker/Web/schema không đổi; idle0 trước/sau.

Source binding cuối trước rollout:
`2de9d3460d5191edcca2e282de030642ff8b859812c520cee66c6abfeeeada68`.
Không sửa .env/flags/credentials/schema hoặc rows/history/archives bằng tay.
SHA256.env trước/sau không đổi:
`5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
Không network model/provider, Ads/spend/post/email/Telegram thật/public deploy.

## Ranh giới và checkpoint kế tiếp duy nhất

B2a là **negative fence**, chưa là grant-to-run authority. Manager vẫn chưa có
activation endpoint, không grant employee thực thi dù B1 eligibility trảtrue.
Model calling permission không thành tools/Ads/Brain authority. Native chưa đăng
ký giữ legacy behavior; không tuyên bố toàn provider isolation/SaaS/production đạt.
Prompt/bytes đã gửi hợp lệ trước đổi quyền không thể thu hồi; kết quả muộn bị bỏ,
phần response đã xuất trước đó được giữ với statusfailed, không xuất completed.

**Tiếp theo B2-model activation và immutable grant pins:** manager đồng ý rõ,
định nghĩa state transition/migration/rollback; pin đúng SME/brand/source/grantee/
grant/version/expiry/capability vào admission và recheck từng call/publication.
Không activate staged tự động, không rewrite completed pins/archives. Sau model
authority mới nối lần lượt MCP/Ads workers. Toàn S2.1B2/S2.1B vẫn in_progress.

## Checkpoint niêm phong cuối — đạt

`.runtime/checkpoints/p0-20261011T143911-06b88c85/manifest.json`

Verified872source/118physicaltables/3M2archives/revision0049. Exact restore
117business tables khớp row hashes/schema definitions/archive evidence và source
binding2de9d346…; primary unchanged, external_calls=false. Chỉ clone do invocation
tạo `pao_s03_restore_19b180d310a54678acb24fbaf84c5e7d` đã dọn; DB chính/source
ZIP/dump/manifest và recovery baseline giữ nguyên.

Sau seal API/ready/Web200,workerhealthy,full live contract317/binding/M2replay3/3,
staged API/auth/redaction/no-store/rows0 và idle0 đều đạt; SHA256.env không đổi,
diff whitespace đạt. Snapshot gồm code và README/master/unified/ADR/register/
acceptance đồng bộ B2a local_accepted → model activation/grant pins kế tiếp.
Không đổi code/config sau seal; chỉ bổ sung self-reference này vào báo cáo.
Không mở real model/tool/MCP/Ads/Telegram hoặc production gate.
