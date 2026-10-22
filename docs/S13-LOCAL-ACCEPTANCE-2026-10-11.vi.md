# S1.3 — kiểm cách ly server, job/outbox và SSE

Ngày11/10/2026. Target `F:\PAO-ACOS`; không sửa protected source `F:\Apex`.
Trạng thái: **local_accepted** trong corpus S1.3 đã định, không SaaS/production acceptance.
Scope/matrix/threat boundaries: [ADR-S13](ADR-S13-SERVER-ISOLATION.vi.md).

## Thay đổi

- `apps/api/pao/core_api.py`: bounded shield cho DB poll/session cleanup SSE;
  không đổi auth contract, schema hoặc cancel run semantics.
- `apps/api/tests/test_s13_tenant_isolation.py`:17 ca hai SME, parent IDOR,
  private Brain, search/retrieval/export, membership revoke queued/inflight,
  business/result/channel outboxes và hàng đợi Redis/ARQ thật.
- `apps/api/tests/test_s13_stream_cleanup.py`:3 probe PostgreSQL/HTTP thật cho
  disconnect giữa DB query, HTTP abort/revoke và timeout cleanup.
- `scripts/check_s13_tests.py`: repeatable isolated focused/full/browser gates.
- `apps/api/tests/test_app_factory.py`: sửa assertion contract lịch sử308 thành
  309 đúng S1.1, kiểm cả context API mới và chống route trùng; không nới auth.

## Bằng chứng và hai lỗi thực sự được sửa

- Health đầu lượt API/ready/Web200; workerhealthy; bridge disabled.
- Disconnect cleanup ban đầu được tái hiện1failed/1passed; sau shield DB poll,
  17ca mới đầu tiên đạt. Probe timeout bổ sung vẫn phát hiện driver termination
  bị nested AnyIO deadline hủy; có transaction pao_test treo ở SQL ngủ10s.
- **Full regression ban đầu:1177passed/2failed/0skip,2264.51s.** Hai failures là
  assertion308API lịch sử (S1.1 thực tế309) và timeout cleanup SSE. Không giấu
  failure hoặc gọi lần full này là xanh. Chỉ đóng đúng connection của probe treo,
  khớp database/user/PID/backend-start/state/query; backup/DB chính không bị động.
- Bản cuối dùng asyncio timeout (edge cancellation) trong DB-only shield;
  harness pin/cleanup owned SQL probes, kiểm thêm server-side orphan transaction.
- **Recheck bản cuối:26passed** (20S13 +6app-factory),35.62s/0skip; cả2failure
  đã đóng. **Affected regression65passed**,68.61s: knowledge workspace, chat
  management, integration, skill version guard và fresh-process recovery.
  Không chạy lại toàn1179ca sau sửa cuối; không claim một lượt full xanh mới.
-25pure/runtime đạt, gồm8runtime/SSE; TypeScript noEmit đạt.
- Browser S12:1passed51.44s; real HTTP/Next proxy/SSE/export, role/revoke/two tabs:
  `.runtime/s12-browser-a1b829aed11848ae98f3b2eb991cb192/browser.json`.
- Browser S11:1passed26.14s; real HTTP tenant selector/settings/chat/tasks:
  `.runtime/s11-browser-4b15300ea12d4673ae8967d0e07aaca5/browser.json`.
- Browser P7:1passed32.03s; synthetic mic/local voice/channel fixture:
  `.runtime/p7-browser-389b4b9c6d79456d95e6224e79fdb29a/browser.json`.
  Không gọi provider thật; test-owned Web3201 đã dừng, không giữ listener.
- Production build21/21 đạt với PAO_BUILD_CHECK=1, cache tách Web đang chạy.
  React Hook warnings kế thừa và ARQ deprecated close warnings còn nguyên;
  không disable lint, nâng dependency hoặc sửa các module không thuộc S1.3.
- Contract source khớp bản saved:309operations,114ORM tables; schema không sửa.
- `.env` hash giữ `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
- Idle trước reload: tất cả counters0, không tool/Ads unknown hoặc job pending.
- Checkpoint trước rollout verified847source/115physicaltables/3M2archives/0048:
  `.runtime/checkpoints/p0-20261011T094812-e0a44f30/manifest.json`.
- Binding rollout trung gian28541ac… đã được thay bằng bản cuối, không là baseline hiện hành.
- Checkpoint trước rollout cuối849source/115physicaltables/3archives/0048:
  `.runtime/checkpoints/p0-20261011T102744-0614e2f2/manifest.json`.
  Exact restore114business row hashes/schema definitions equivalent đạt;
  primary unchanged; clone riêng `pao_s03_restore_1bee018817a14e53a3e6efaf79eafc37`
  đã dọn, source/dump/manifest giữ nguyên.
- Backend binding cuối:
  `4b7afa9a920a1daee226f940aefef5b40ec90db5a1a025963c6142f81c266b68`.
- Sau reload cuối: API/ready/Web200,workerhealthy; source/saved/live contract309
  và binding khớp, M2archive replay3/3, schema0048; idle counters0.
  Không repin archive/job cũ, không đổi .env/flags hoặc restart Docker/Web khi khỏe.

Source/code final được giữ nguyên sau kiểm thử; checkpoint niêm phong docs và
exact restore cuối được bổ sung dưới đây sau xác minh. Lượt này chỉ triển khai S1.3.

## Lệnh nghiệm thu

Chạy ở `F:\PAO-ACOS`, bằng `.venv\Scripts\python.exe`:

```powershell
.venv\Scripts\python.exe scripts/check_s13_tests.py --full
.venv\Scripts\python.exe scripts/check_s13_tests.py --corpus-only
.venv\Scripts\python.exe scripts/check_s13_tests.py --browser-only
.venv\Scripts\python.exe scripts/check_acos_health.py
.venv\Scripts\python.exe scripts/check_p1_live.py
.venv\Scripts\python.exe scripts/backup_acos_checkpoint.py
.venv\Scripts\python.exe scripts/check_s03_restore.py <owned-manifest.json>
```

`--full` opt-in migration/check chỉ `pao_test` và Redis15, không roundtrip main.
`--corpus-only` kiểm lại20ca mới + app-factory sau cập nhật assertion contract.
`--browser-only` là S12/S11/P7 real HTTP, với owned Web3201/fixture API đã cleanup;
P7 dùng synthetic audio/local STT, không nghiệm thu microphone hay Telegram thật.

## Gate còn mở ngoài S1.3

Connection identity/BYO/managed OAuth và grants, quota/fairness/rotation theo SME
chưa nghiệm thu S2–S4. Không gọi toàn hệ thống đã secure SaaS từ corpus này.
Meta real OAuth, M3 real-data, mic/live channels, offsite Git backup và production
reboot/failover vẫn external/production pending. Không reset Docker/volume,
reboot, đổi secret, gửi tin/Ads, public deploy, commit/push toàn dirty tree.

SSE recheck theo poll0.2s và bounded query, không instant global revocation hoặc
thu hồi bytes đã gửi. Không chứng nhận tất cả309API/SQL clients; RLS chưa bật,
fine-grained brand/connection grants, credential rotation/quota/fairness còn S2–S4.

**Đầu việc tiếp theo duy nhất: S2.1** inventory provider/credential ownership/
connection identity/brand-account grants và explicit legacy mapping. Không đổi
schema/credential hoặc gọi live connector chỉ từ việc đóng S1.3. Hướng AI tùy
biến từng job giữ ở S2 foundation và S5.3 routing, không hardcode theo vendor.

## Checkpoint niêm phong cuối

`.runtime/checkpoints/p0-20261011T103641-e6fc83a3/manifest.json` verified:
849source (gồm4frontend .d.mts declarations),115physicaltables,3M2archives,
revision0048, binding4b7afa9… khớp source/live. Exact restore114business tables:
row hashes exact/schema definitions equivalent, primary unchanged, external calls0.
Chỉ clone do invocation tạo `pao_s03_restore_6a0ee096566d4649aa3d0730b96c7768`
đã được dọn; DB chính và source/dump/manifest được giữ, có thể phục hồi từ backup.
Health/ready/Web200,workerhealthy và M2replay3/3 chạy lại sau niêm phong đều đạt.

Snapshot giữ code và roadmap/ADR/README đã đồng bộ S2.1. Không đổi code/config
sau checkpoint; chỉ bổ sung phần self-reference này vào báo cáo nghiệm thu.
