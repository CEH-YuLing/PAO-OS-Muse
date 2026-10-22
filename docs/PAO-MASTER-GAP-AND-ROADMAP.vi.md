# PAO — Roadmap tổng thể và sổ ưu tiên duy nhất

Ngày chốt kế hoạch: **21/10/2026** · Nguồn triển khai: `F:\PAO-ACOS`.
Đây là kế hoạch phát triển, **không phải biên bản nghiệm thu các phần chưa làm**.

**Bổ sung UX trước GD00 —21/10:** đã thêm lựa chọn Tự động06:00–18:00 Sáng,
18:00–06:00 Tối theo giờ thiết bị, giữ nguyên Sáng/Tối cố định và mặc định cũ.
228Node/typecheck/build và browser installed/reload/cross-tab/mobile đạt trong phạm vi này.
Xem [nghiệm thu Auto](LOCAL-THEME-AUTO-2026-10-21.vi.md). Không đổi backend/schema/.env;
GD03 không được đánh dấu hoàn tất từ bổ sung này.

**GD00 —21/10: local_accepted.** Đã đóng source/private baseline, phục hồi clone0075
với hash161bảng/3archive, boot API từ source backup và giải mã2credential;
startup read-only,2lần start giữ process/dữ liệu. 28unit+5archive+6PowerShell guard.
Biên bản [GD00 baseline/phục hồi](GD00-BASELINE-AND-RECOVERY-2026-10-21.vi.md),
receipt hiện hành `.runtime/gd00-current-status.json`. Offsite/portable key,
Git commit/publication và full-hostDR chưa đạt; production=false. **Kế tiếp GD01**,
không cài candidate0076 trong GD00.

**Nơi lưu backup đã chốt21/10:** `F:\PAO-BOS Backup 001`; mỗi bản mới nằm trong
thư mục con riêng, không ghi đè bản cũ. Xem [quy ước lưu backup](BACKUP-STORAGE.vi.md)
và `infra/backup-storage.json`. Đây là cấu hình vận hành cho các lượt sau, chưa chuyển
backup GD00 cũ, không upload GitHub và không phải backup ngoài máy.

**Bổ sung UI PAO AI21/10:** popup chọn mô hình2tab Client/API,4ô nhà cung cấp mỗi
tab, tìm kiếm và model/effort theo resource; nút header lớn hơn hiển thị provider/model.
238Node/typecheck/build và4profile browser fixture dark/light320–1600 đạt;
không thêm backend/CLI adapter hoặc model giả. Xem [biên bản popup](PAO-AI-MODEL-POPUP-2026-10-21.vi.md).
Đây là nghiệm thu UI riêng, không hoàn tất GD01/GD03 hoặc quota/provider thật.

## 1. Cách dùng roadmap này

**Chính sách token22/10 — đã cài local.** Lượt mới theo khả năng model/provider,
không áp trần context/output/tổng token run riêng của PAO; UI bỏ3ô cap. Planner,
specialist, extraction và job Studio đi qua ledger hiện có; old pins/bounded API
giữ nguyên. Muse Spark1.2/High thật planner695/final1369token completed; replay0call.
262Node/build,10focused và installed GET2SME/5Muse/6Codex/3replay đạt. Lượt rộng
552chức năng đạt nhưng receipt false do sessions drift, không coi là regression
sạch. Giữ SME/privacy/tool/approval/loop/timeout và technical byte guards; model
không có context vô hạn. Codex container64KiB envelope chưa mở rộng, cần candidate
riêng. Xem [biên bản token theo mô hình](PROVIDER-TOKEN-POLICY-2026-10-22.vi.md).
Tiếp tục tối ưu context lớn/RAG/compaction và đo usage; không mở GD02 hoặc tuyên bố
toàn GD01/production đạt từ thay đổi này.

**Muse22/10 — trọn luồng job văn bản local đã nghiệm thu bằng thuê bao thật.**
Đã qua profile/plan/review/materialize → hai job phụ thuộc → ARQ thật → duyệt
artifact → Task/Goal/Project completed → báo cáo khớp actual usage → replay0call.
Spark1.3/minimal và Spark1.2/low;134regression không provider và1live test/2call đạt,
primary/source/env/0077 giữ nguyên. Không sửa app hoặc thêm runner; artifact Studio
đọc đúng GET job, không giả archive skill legacy. Xem
[nghiệm thu job Muse](MUSE-BUSINESS-JOB-ACCEPTANCE-2026-10-22.vi.md).
Đây là dữ liệu tổng hợp trong pao_test, chưa chất lượng kinh doanh thực, browser
end-to-end mới, P6 Goal runner/Temporal hoặc production; **toàn GD01 vẫn in_progress**.

**Muse22/10 — adapter văn bản local đã cài và chạy thuê bao thật.** Cập nhật này
thay trạng thái catalog-only của Muse21/10 bên dưới: profile riêng đã đăng nhập,
Settings Connect đã công bố5model vào registry AI bản cài; PAO AI chọn được model/
effort, không thêm grant nhân sự hoặc đổi AI mặc định. 543backend có phạm vi,
31unit native/profile,257Node/typecheck/build, fixture browser và installed GET
haiSME/5Muse/6Codex/3replay đạt;0077/161bảng/435operations, không migrate/.env.
Chat Spark1.3 và Skill Spark1.2 chạy thật bằng dữ liệu tổng hợp. Planner/final
đã completed; pytest gốc lỗi assertion Chief of Staff, review SELECT xác minh
2attempt/0specialist/tool, giữ nguyên receipt failed và lỗi đếm0call cũ.
Chưa whole job/Goal/Temporal bằng Muse, native token streaming hoặc hard token cap
upstream; overhead khoảng14k input/call và codec trace pin1.4.10 cần tối ưu.
Xem [adapter Muse và giới hạn](MUSE-TEXT-ADAPTER-LOCAL-2026-10-22.vi.md).
**GD01 vẫn in_progress**, không suy rộng sang Claude/Antigravity/shared Codex.

**Muse21/10 — kết nối/auth đã cài, tích hợp suy luận chưa hoàn tất.** Đã thêm
card Muse và official device login bằng profile PAO riêng theo xác nhận chủ sở hữu;
không sao chép token/hook từ profile cũ, không thêm grant AI cho từng nhân sự.
535backend/22unit/255Node/typecheck/build, browser fixture và installed GET haiSME/
ba replay đạt; API/ready/Web200, schema0077/161bảng/435operations.
Profile mới cần chủ sở hữu đăng nhập một lần. PAO AI chỉ xem catalog; adapter
Chat/Agent/Job, isolation/usage/cancel và quota thật còn implementation_pending,
không phải chỉ có chốt tài khoản. Toàn GD01 vẫn in_progress.
Xem [Muse profile và kết nối](MUSE-PROFILE-CONNECTION-2026-10-21.vi.md).

**Codex nhiều model21/10:** đọc danh mục native và chọn riêng từng hội thoại đã
triển khai, không đổi profile/default. Client hiện trả sáu model; không hardcode
hoặc coi danh mục là quota. Schema0077/161bảng/429operations; 499backend có phạm vi,
250Node/typecheck/build, browser fixture và installed GET6model/2SME/3replay đạt.
Lượt quota thật Luna trước sửa lỗi `cli_plan_invalid`; sau sửa và đăng nhập lại,
GPT-6-Luna và GPT-5.6-Luna đã trả đúng marker tổng hợp qua UI. Bốn attempt native
planner/final completed, 0tool/specialist/API fallback, default hồ sơ giữ nguyên.
Receipt `.runtime/gd01-codex-live-db28a6f0b08e418091740033e60543ff/receipt.json`;
không coi hai bài thử này là nghiệm thu suy luận cả sáu model.
Xem [biên bản nhiều model Codex](GD01-CODEX-MULTI-MODEL-2026-10-21.vi.md).
Candidate0076 chưa cài, native effort override/shared CLI chưa nghiệm thu;
**toàn GD01 vẫn in_progress**, không suy rộng thành mọi Client đã chạy thật.

**GD01 —21/10: in_progress, chưa đóng giai đoạn.** Đã bổ sung effort Anthropic/Gemini,
usage/thinking filter, evidence catalog/inference/quota, extraction cùng pin của
API resource và circuit/cancel trên ledger sẵn có. OpenAI API đã chạy thật Chat
`gpt-6.1-sol/low` và Studio `gpt-6-luna/medium` bằng dữ liệu tổng hợp, không tool.
Không đổi schema0075/.env hoặc cài candidate0076. Nhánh official Codex/shared CLI,
promotion và capability/migration legacy còn việc; Claude live đã hoãn, Antigravity
consumer wrapper chưa hỗ trợ. Xem [GD01 và giới hạn nghiệm thu](GD01-AI-RESOURCES-2026-10-21.vi.md).
Không đánh dấu GD01/GD02 hoặc ba Client đã xong từ riêng hai lượt OpenAI API này.

**Sửa Client21/10:** Codex local đã nối lại vào popup PAO AI (`gpt-6-astra`),
không bị API dùng chung che mất; nút Kết nối cập nhật thiết lập sau đăng nhập lại,
không thêm màn cấp quyền nhân sự hoặc đổi mặc định. 475backend functional đạt
(lượt có thao tác đăng nhập đồng thời),73focused lượt sạch,249Node/build/browser
và installed GET haiSME/3replay đạt. Không có suy luận/quota Client mới trong lượt
này; Claude còn thiếu adapter, Antigravity catalog-only, Muse chưa triển khai.
Xem [bản sửa kết nối Client](GD01-CLIENT-CONNECTION-REPAIR-2026-10-21.vi.md).
GD01 tiếp tục in_progress, không đánh dấu mọi Client hay shared CLI đã hoàn tất.

- Tài liệu này sở hữu **thứ tự triển khai hiện hành** của toàn PAO.
- Mã **GD00–GD11** là các gói công việc kế tiếp, ánh xạ vào M/P/S/EA cũ; không có nghĩa xóa thành quả hoặc khởi động lại P6/S0–S5.
- Mỗi lần nhận triển khai: hoàn thiện cả giai đoạn được duyệt, làm tuần tự các bước, kiểm thử và bàn giao một lần; cập nhật ngắn trong quá trình làm.
- Chỉ dừng để xin quyết định khi thật sự thiếu quyền, tài khoản, dữ liệu hoặc có tác động bên ngoài. Không hỏi lại những quyết định sản phẩm đã chốt.
- Bản master trước khi quy hoạch lại được giữ **nguyên byte** tại [lịch sử trước 21/10](PAO-MASTER-GAP-AND-ROADMAP.HISTORY-BEFORE-2026-10-21.vi.md). SHA256: `21f57d7d86111e6070521b775b25f997acd7bb0e0e889c6f6bc3bceb86c93ad6`.
- Các sổ nghiệm thu cũ vẫn là bằng chứng theo **đúng ngày/source/schema**, không còn sở hữu chỉ dẫn “triển khai tiếp” nếu khác tài liệu này.
- Khảo sát trực tiếp Javis, mapping mã nguồn và tài liệu nhà cung cấp tại [đối chiếu PAO–Javis](PAO-JAVIS-REVIEW-2026-10-21.vi.md). Không sao chép toàn bộ kiến trúc hoặc nhãn “connected” thành bằng chứng PAO đã hoạt động.
- Bản quy hoạch đầu21/10 chỉ khảo sát/chỉnh tài liệu. Các bổ sung sau ghi riêng ở đầu tài liệu;
  GD00 thay công cụ vận hành, không đổi cấu hình/schema, gọi model, commit/push hay deploy.

**Thứ tự ưu tiên:** bảo vệ phiên bản → AI dùng xuyên ứng dụng → đồng bộ trạng thái → cài đặt/UX → nghiệp vụ local → dữ liệu thật → pilot local → sản xuất khi được yêu cầu lại.

## 2. PAO phải trở thành sản phẩm gì?

PAO là hệ điều hành vận hành cho **một chủ doanh nghiệp hoặc nhóm 1–3 người**:
nhận mục tiêu → hiểu doanh nghiệp/nhãn hàng → lập kế hoạch → giao agent/công việc →
tạo sản phẩm → chủ duyệt → thực hiện trong phạm vi cho phép → đo kết quả → báo cáo và học có kiểm soát.

Một bản cài riêng cho khách hàng có thể quản lý nhiều doanh nghiệp của họ.
Core vẫn hỗ trợ nhiều SME độc lập; một người thuộc nhiều SME không có nghĩa dữ liệu được trộn.
Chưa chuyển sang public signup, marketplace công khai hoặc hosted SaaS đại trà.

### 2.1. Hợp đồng trải nghiệm bắt buộc

1. **Cài PAO → kết nối một nguồn AI hợp lệ → chọn model → dùng ngay.**
2. Tài nguyên AI được quản trị ở cấp bản cài. Thành viên dùng theo quyền ứng dụng; **không wizard cấp grant AI riêng cho từng người/agent/job** trong luồng thường.
3. Kết nối sẵn sàng phải tự xuất hiện ở Chat, Studio, lập kế hoạch, job và tác vụ nền phù hợp; không nhập lại key ở mỗi màn hình.
4. Agent/step/job được chọn provider, model và mức suy luận riêng hoặc kế thừa. Không khóa cứng vendor theo nghề; không ép mọi nhiệm vụ dùng cùng một model.
5. “Dùng ngay” áp dụng cho adapter đã hỗ trợ thật, đúng điều kiện tài khoản. Không hiện “sẵn sàng” chỉ vì tìm thấy binary, đọc được danh mục hoặc lưu được khóa.
6. Không yêu cầu cài Ollama/GPU nếu dùng CLI/API. Tách lựa chọn model hội thoại khỏi dịch vụ embedding/chỉ mục tri thức.
7. Tiếng Việt rõ ràng; dark/light; bàn phím và điện thoại dùng được. Mỗi trang có một việc chính; chức năng nâng cao đặt sau, không dồn một biểu mẫu dài.
8. Phân quyền nghiệp vụ, ranh giới SME/Brain, bảo vệ khóa và duyệt chi tiền/gửi/đăng/xóa vẫn ở backend. **Bớt thao tác không đồng nghĩa bỏ bảo mật.**
9. Hiển thị trạng thái mới nhất xuyên màn hình và nhiều tab, lỗi có cách xử lý, job không mất chỉ vì đóng trình duyệt.
10. Không tự chuyển sang API tính phí, model khác, tài khoản khác hoặc mở thêm công cụ khi nguồn AI lỗi.

### 2.2. Trải nghiệm mẫu phải nghiệm thu

Chủ nhập hồ sơ nhãn hàng, nối một AI → Chat thấy ngay model → yêu cầu kế hoạch tháng →
PAO tạo bản nháp có giả định/nguồn → chủ duyệt → chia việc content/thiết kế/phân tích →
mỗi việc có agent/model riêng → tiến độ hiện trên Chat và bảng việc →
duyệt sản phẩm → báo cáo giờ/ngày từ dữ liệu đã đối soát.
Thiết kế ảnh/video, đăng bài và sửa quảng cáo chỉ có khi adapter/tool tương ứng đã nghiệm thu;
model trả lời văn bản không tự tạo ra những năng lực đó.

## 3. Điểm xuất phát thực tế ngày 21/10

Snapshot từ audit chỉ đọc trước lượt quy hoạch này và source/receipt đối chiếu lại.
Đây **không phải lượt full regression mới** hoặc chứng nhận toàn hệ thống.

| Khu vực | Đã có và bằng chứng | Chưa xong / chưa xác minh |
|---|---|---|
| Web/API/hạ tầng local | Web3200, API8100 health/ready200; PostgreSQL17.11, Redis7.4.11, worker khỏe | Chưa kiểm độ ổn định dài ngày/khởi động máy mới trong lượt này |
| Schema/contract | 0075;161 bảng vật lý;429 operations/55 router specs; contract source/live khớp ở audit | Candidate0076 không nằm trên primary |
| Enterprise/nhãn hàng/tài khoản | Tạo SME độc lập, mời thành viên, roles, hồ sơ/phiên bản, phiên đăng nhập, export/yêu cầu xóa có nghiệm thu local | Chưa public signup; không có executor xóa tự động; pilot thực tế chưa đạt |
| Chat/tri thức | Streaming SSE/replay/cancel, Brain, sources/wiki/RAG/graph, Studio/Skills có code và nghiệm thu local theo lát cắt | Không coi toàn bộ tri thức đã được nghiệm thu với CLI/model thật hiện hành |
| AI dùng chung | UI3Client/4API, registry cấp bản cài, API model/effort và lựa chọn agent/job có phần đã cài | Shared CLI backend còn `installation_ai_cli_adapter_pending`; cần hợp nhất đường chạy |
| Codex | Chat cá nhân từng trả `PAO_CODEX_OK` bằng model thật; candidate đa model/effort220tests +6binary offline | Candidate chưa cài shared; tài khoản/phạm vi chia sẻ và quota thật đa consumer chưa nghiệm thu |
| Claude Code | Chuẩn bị adapter/protocol offline | User chưa có thuê bao, đã hoãn; không tự yêu cầu mua hoặc coi connected |
| Antigravity | Nhận CLI native/danh mục từng đọc6model; MCP chỉ đọc chiều ngược đã chuẩn bị | Inference false; smoke chặn trước prompt vì60tools; còn điều kiện nhà cung cấp độc lập |
| Business planning | S5 local accepted: profile → plan → native task/job → review → report; routing/version/ledger đã có | Primary monthly_plans=0 tại audit; chưa có trọn chiến dịch kinh doanh thật |
| Goal/lịch/kết quả/học | P6 và các dịch vụ native có nghiệm thu local;8cờ nội bộ vừa mở | Goal admission vẫn dry-run/model_calls=false; goal runner/schedule dispatch chưa bật; không phải hệ tự chạy tháng |
| Ads/CRM/sáng tạo | Meta/Google connector code, read warehouse/attribution; CRM tổng hợp; nội dung nháp/review | Meta/Google live đang tắt; TikTok chưa connector; GPT Ads là chỗ chờ; chưa CRM đầy đủ/media/publishing |
| Channels/MCP/voice | Telegram identity/pairing, inbox, takeover, MCP read-only, voice có bằng chứng local/fixture | Chưa bot/MCP thật được chọn; chưa mic tiếng Việt thật; các kênh khác chủ yếu catalog/chỗ chờ |
| Realtime | Run SSE sequence/replay/heartbeat; auth/SME được kiểm; có polling/refresh | Chưa có đồng bộ chung provider/catalog/tasks/approval/report trên toàn app |
| Backup/Git | Checkpoint20/10 nguồn+DB hash đạt; có restore clone lịch sử | 115modified+987untracked tại audit; khóa/private blobs/offsite chưa phục hồi toàn bộ; launcher chưa ép checkpoint trước schema mới |

Binding backend snapshot: `f596abc415cb9e97b18b7da6e5e1d937fe9194ac82896ea73badcc6d3ac1bf3a`.

Bằng chứng chính: [AI/model/effort](AI-RESOURCE-MODEL-EFFORT-REDESIGN-2026-10-20.vi.md),
[Codex candidate](CLI-MULTIMODEL-CANDIDATE-2026-10-20.vi.md),
[Antigravity](ANTIGRAVITY-QUOTA-RECHECK-2026-10-20.vi.md),
[8chức năng nội bộ](LOCAL-FEATURE-ACTIVATION-2026-10-20.vi.md),
[S5](S5-COMPLETION-REGISTER.vi.md), [S6](S6-COMPLETION-REGISTER.vi.md).
25Node SSE/tenant và9operator guards đạt ở audit;148focused chức năng có receipt riêng.
Các số2258/2272/2343 trong lịch sử thuộc source khác; không dùng làm tổng test current0075.

**Không công bố % toàn hệ thống lúc này:** chưa có bộ tiêu chí đầu ra được cân trọng số.
Sau khi duyệt roadmap, cố định checklist DoD; báo cáo riêng % code/local/live/pilot theo
số tiêu chí đã đạt / tổng tiêu chí cùng phạm vi. “Có code” và gate external_pending không tính là live pass.

## 4. Kiến trúc đích: thống nhất các phần đang có

Thuật ngữ ngắn: **Client/CLI** là ứng dụng AI cài trên máy; **provider** là bên cung cấp AI;
**agent** là trợ lý chuyên trách; **skill** là hướng dẫn làm một việc; **workflow** là quy trình nhiều bước;
**quota** là hạn mức tài khoản; **embedding** là biểu diễn tài liệu để tìm kiếm theo ý nghĩa;
**realtime** là cập nhật tự động khi trạng thái đổi; **DoD** là điều kiện chứng minh một phần đã hoàn tất.
**Local** là máy hiện tại; **production** là môi trường phục vụ khách hàng thực tế.

```text
Web / Telegram và kênh được chọn
                ↓
      API + danh tính + phạm vi SME/nhãn hàng/Brain
                ↓
Chat / Business Plan / Studio / Task / Schedule / Review / Report
                ↓
   Ngữ cảnh + bộ chọn AI chung + native Run/Attempt/Dispatcher
       ↓                             ↓
CLI/API/Ollama adapter         Tool Gateway + approval + connector
       └─────────────┬───────────────┘
          PostgreSQL: phiên bản, ledger, outbox, audit
                ↓
      Luồng sự kiện có replay → UI các module
```

- Giữ **modular monolith** FastAPI + Next.js, PostgreSQL/pgvector, Redis/ARQ.
  Temporal chỉ cho workflow dài đã có và khi nhu cầu thực tế yêu cầu. Không chuyển SQLite,
  dựng thêm backend Javis hoặc bắt buộc Kubernetes/microservices.
- PostgreSQL là authority nghiệp vụ; Redis là vận chuyển/cache, không là sổ chứng cứ.
  File immutable + DB hash/version/ACL là authority tài liệu; vector/graph/Markdown là projection có thể dựng lại.
- **Một bộ chọn tài nguyên AI, một contract engine, một cổng công cụ, một hệ task/run.**
  Tận dụng installation_ai/engines/tools/business_planning/runtime/goals hiện có.
- Dùng tài nguyên AI chung không chia sẻ ngữ cảnh giữa các SME. Phiên CLI/resume phải gắn
  SME/actor/Brain và scope hiện hành; không dùng một conversation ID cho mọi khách.
- Mỗi run ghim provider/resource revision, model/effort, capability, prompt/context,
  agent/skill/workflow versions, budget và tool policy. Thay mặc định chỉ áp dụng lượt sau.
- Event nghiệp vụ bền qua outbox; stream delta chỉ là hiển thị. Không tạo outbox/runner thứ hai
  nếu đã có contract phù hợp; mở rộng hoặc làm adapter rõ ownership.
- Thay đổi cấu trúc theo dependency map, giữ route/import shims và migration history.
  Không đổi tên thư mục hàng loạt chỉ để giống Javis.

### 4.1. Ownership và cấu trúc source

| Nơi hiện có | Trách nhiệm cần giữ/hoàn thiện |
|---|---|
| `apps/api/pao/app.py`, auth/access/config/db | Lắp router, quyền và phạm vi; không nhét logic mới vào app factory |
| `modules/installation_ai`, `engines`, `cli_connections`, `connections` | Registry, catalog/capability, auth adapter, routing; một đường chạy chuẩn |
| `core_api.py`, `runtime.py`, `modules/chat`, `conversations`, `tasks` | Run/SSE/dispatcher/task ownership; extract dần sau tests, không song song runner |
| `modules/business_planning`, `business` | Hồ sơ, kế hoạch, phân công, dự toán, kết quả kinh doanh |
| `modules/brains`, `knowledge`, `studio` | Nguồn, wiki, phiên bản skill/agent/workflow, retrieval |
| `modules/events`, `results`, `learning`, `goals`, `schedules` | Sự kiện/kết quả/học/mục tiêu/lịch theo native state machines |
| `modules/tools`, `connectors`, `channels` | Tool Gateway và adapter provider/channel; không tự cấp quyền qua prompt |
| `apps/web/app`, `components`, `lib` | Route mỏng; shared provider/catalog/event/query state; UI tính năng theo ownership |
| `packages/contracts`, `packages/cli-runtime` | OpenAPI/types và protocol adapters; candidate tách installed |
| `scripts`, `infra`, `docs` | Entry ổn định, môi trường local/test/deploy tách, một master + ADR/evidence |

`models.py`, `runtime.py`, task API còn lớn: refactor từng domain sau khi có test.
Không tạo `runtime.py` và `runtime/`, hoặc `db.py` và `db/` trùng import.
Migration model extraction phải giữ đủ metadata, table names, contract và archive replay.

## 5. Bảng lộ trình tổng

Tất cả GD dưới đây là **planned**, trừ nền có sẵn ghi ở mục3; không đánh dấu giai đoạn mới đã hoàn tất.

| Giai đoạn | Kết quả khách hàng nhận được | Phụ thuộc | Ưu tiên / mapping cũ |
|---|---|---|---|
| GD00 | Phiên bản và backup có thể phục hồi trước khi phát triển tiếp | Snapshot hiện tại | Local_accepted21/10; offsite/portable key/Git publication còn chờ |
| GD01 | Kết nối AI một lần, Chat/Agent/Job dùng chung model và effort | GD00 | Cao nhất về tính năng; RAI/EA/P3/S5.3 |
| GD02 | Trạng thái provider/công việc/duyệt/báo cáo tự cập nhật xuyên app | GD01 contract | Cao; P3/M4/M6 |
| GD03 | Bộ cài và UX đơn giản, không cần kỹ thuật để dùng | GD01–02 | Cao; M6/localUX/P0 |
| GD04 | Hồ sơ, tri thức, skills và agent cùng một luồng làm việc | GD01–03 | Local core; P1/P2/P4/S2/S5 |
| GD05 | Một chu trình lập kế hoạch–giao việc–duyệt–báo cáo bằng AI thật | GD04; dữ liệu nhập hoặc fixture tách biệt | Local core; S5/P6/M5B |
| GD06 | Số liệu thật chỉ đọc, đối soát được | GD02–05 và nguồn được chọn | Nghiệm thu thực tế; S6.1/M3/S4/P5 |
| GD07 | Sản phẩm sáng tạo ảnh/video có file thật và quy trình duyệt | GD04–05; provider media phù hợp | Nhánh mở rộng; P8.5/M8 |
| GD08 | Đăng/gửi/sửa Ads có duyệt, ngân sách và đối soát | GD06; GD07 nếu dùng media | Tác động thật cần duyệt riêng; M4/S5 |
| GD09 | Telegram/kênh khách hàng/CRM/voice nhất quán với Web | GD01–06; từng dịch vụ thực tế | Nhánh theo nhu cầu; P7/S3/M8 |
| GD10 | Chủ doanh nghiệp sử dụng local ổn định, có biên bản nghiệm thu | GD00–06; nhánh đã cam kết bán | S6.3/M5B; trước thương mại |
| GD11 | VPS/private production, bảo mật và phát hành sản phẩm | GD10 + yêu cầu mở lại production | **Hoãn theo người dùng**; Phase3/S6/commerce |

Luồng chính: **GD00 → GD01 → GD02 → GD03 → GD04 → GD05 → GD06 → GD10**.
GD07/08/09 chọn theo nhu cầu, không ép nối tất cả nền tảng để nghiệm thu local.
GD11 không được tự mở chỉ vì local đạt. Tính năng nào chưa được nghiệm thu phải tắt/ghi rõ trên gói sản phẩm.

## 6. Chi tiết từng giai đoạn

### GD00 — Đóng baseline, bảo vệ và phục hồi

**Trạng thái21/10: local_accepted**, trong phạm vi source/PostgreSQL/cấu hình PAO;
không phải DR toàn máy. Chi tiết và runbook tại [biên bản GD00](GD00-BASELINE-AND-RECOVERY-2026-10-21.vi.md).

**Mục tiêu:** mọi thay đổi kế tiếp có đường quay lại, không mất dữ liệu hiện tại.

1. Inventory source đang phục vụ, dependency lock, UI build, schema/contract, runtime pins và công việc đang chạy; phân biệt candidate0076.
2. Rà modified/untracked theo scope; số đếm cập nhật trong `git-baseline-plan.json`, không dùng987 cũ làm số hiện hành;
   quét secret và file sinh; chuẩn bị baseline Git có nguồn gốc.
   Commit/nhánh/push chỉ khi được phép riêng, không tự sửa remote hoặc trộn publication cũ.
3. Checkpoint nguồn + DB + inventory private files/khóa; khóa mã hóa lưu bằng cơ chế bảo mật riêng, không nằm Git/chat/report.
4. Phục hồi **clone riêng** từ backup, kiểm hash/version/archive/khả năng giải mã bằng khóa được cấp;
   không restore đè primary, không chỉ kiểm ZIP.
5. Tách startup thường khỏi nâng schema: schema mới phải qua verified checkpoint và rollback/runbook;
   startup trên revision đúng là idempotent, không chạy DDL ngầm.
6. Chốt test profile hiện tại: offline/unit, DB riêng, Windows/Linux, frontend/typecheck/build,
   browser, live acceptance; các runner dùng pao_test/Redis15 chạy nối tiếp có lock.

**Nghiệm thu:** baseline source manifest; clone boot/read và archive replay; backup sai hash/thiếu khóa bị báo rõ;
khởi động hai lần không nhân process/job; không mất row primary. Chỉ test lại phần chưa có bằng chứng hợp lệ.
**Rủi ro/phát sinh:** baseline Git cũ; backup cùng ổ F; thiếu key/blob; migration downgrade có dữ liệu.
**Xử lý:** giữ lịch sử, không commit bí mật; bản ngoài ổ khi được cấp; dừng schema nếu checkpoint hỏng.
**Gate còn cần:** nơi giữ khóa/backup ngoài máy và Git publication là quyết định riêng, không chặn inventory local.

### GD01 — Tài nguyên AI chung, đa model và mức suy luận

**Mục tiêu:** giải quyết đúng yêu cầu “kết nối Client/API xong, các phần khác dùng được luôn”.

1. Chuẩn hóa registry sẵn có: provider/auth source/catalog revision/capabilities/health/quota evidence,
   tách trạng thái cài binary, đăng nhập, catalog, inference và phạm vi provider hỗ trợ.
2. Client đứng trước API:3thẻ Codex/Claude Code/Antigravity; API mỗi provider một thẻ.
   Một nút kết nối có tiến độ; nếu phiên native hợp lệ thì tái dùng theo cơ chế chính thức,
   nếu chưa có thì mở luồng chính chủ. Không hỏi mật khẩu PAO lặp lại hay sao chép token của Javis.
3. Gỡ các đường yêu cầu AI grant cá nhân trong luồng thường bằng resolver cấp bản cài;
   giữ vai trò sửa cấu hình, phạm vi dữ liệu và kiểm quyền nghiệp vụ. Migrate có bản xem trước,
   không xóa ngay credential/history hoặc tự biến login cá nhân thành identity được chia sẻ.
4. Dùng một catalog có nguồn/thời điểm; kiểm model khả dụng ở lần gọi thật. UI chọn/search/filter
   provider, modality, model, effort chỉ theo capability; không suy “High” trong prompt là effort thật.
5. Hoàn thiện candidate Codex đã có: native dispatch/accounting/cancel, model/effort/pins,
   promotion/release/rollback. Không tự rollout0076 trước clone/gates hoặc thay profile cũ.
6. Rà lại **tài liệu chính thức hiện hành** cho từng phương thức/từng gói; xử lý theo bảng6.1.
   Nhánh thiếu thuê bao/điều kiện không làm kẹt adapter dùng được khác.
7. Nối Chat/orchestrator/agent/step/job/knowledge extraction/report/schedule qua resolver này;
   embeddings là capability riêng. Defaults kế thừa, override minh bạch; old runs không bị repin.
8. Một chính sách timeout/rate-limit/circuit-breaker/accounting; không auto fallback trả phí.
   Cost estimate, token reported và quota còn lại là ba khái niệm khác nhau.
9. Dọn đường personal/shared/legacy chồng chéo theo compatibility adapter, deprecation rõ;
   chỉ xóa sau mapping/history/replay pass, không thêm engine runner cạnh native.

**Nghiệm thu:** một nguồn hợp lệ → Chat và một job agent chạy thật; hai model/effort khác nhau nếu catalog
thực sự hỗ trợ; đổi nguồn/tab không nhập lại khóa; restart/revoke/429/cancel không treo hoặc dùng nhầm account;
hai SME không lẫn context; quan sát đúng provider/model/effort ở attempt, không chỉ ở dropdown.
Test fixture, binary offline, inference thật và shared-commercial được báo tách.
**Rủi ro/phát sinh:** điều kiện gói khác nhau, CLI tự cập nhật, tool nền của CLI, OAuth dưới user Windows khác,
quota cạn, cost fallback, credential custodian bị thu hồi.
**Xử lý:** pin version được kiểm, subprocess isolation/env tối thiểu, khám phá capability có timeout/cache,
compatibility probes không tiêu quota mặc định, invalidate revision và thông báo lỗi có hành động sửa.
**Gate:** không coi GD01 “tất cả3CLI live” khi một provider còn blocked/deferred; ghi rõ core pass và ngoại lệ từng provider.

#### Chú ý đã chốt với chủ sở hữu — 21/10/2026: local và Codex dùng chung

- **Tạm chờ nhánh Codex dùng chung** theo trả lời của chủ sở hữu: “Chưa có; giữ
  nhánh dùng chung chờ, tiếp tục phần local hợp lệ”. Không hỏi lại Client ID hoặc
  hồ sơ phê duyệt khi đang thực hiện các việc local không phụ thuộc nhánh này.
- **Không dùng việc chưa có Client ID sẵn làm chốt chặn GD01 local.** Đường Codex
  CLI local đã có bằng chứng chạy thật phải được phân biệt với luồng Sign in with
  ChatGPT riêng của PAO và với quyền cung cấp dịch vụ thương mại/dùng chung.
- Với luồng đăng ký động dành cho ứng dụng OSS/local đủ điều kiện, OpenAI cấp
  Client ID trong quá trình người dùng đăng nhập và cho phép. Không bắt khách hàng
  tự tìm/nhập Client ID, client secret hay API key để dùng đường thuê bao này.
  Đây là phần kỹ thuật PAO phải xử lý; không tự coi PAO thương mại đã đủ điều kiện.
- UX mục tiêu: **Cài PAO → Kết nối Client → đăng nhập chính chủ nếu cần → chọn
  model → sử dụng**. Client ID nhận diện đăng ký kết nối; không phải mật khẩu,
  API key hoặc model. Token phải được bảo vệ phía sau, không yêu cầu gửi qua chat.
- VPS/sản phẩm trả phí hoặc dùng chung cần xác minh phạm vi hỗ trợ riêng trước
  khi thương mại hóa. Một tài khoản đăng nhập trên một VPS không tự chứng minh
  mọi cách chia sẻ thuê bao đều được cho phép. Không tự chuyển gói, mua API,
  dùng fallback trả phí hoặc chia sẻ phiên cá nhân để vượt điều kiện.
- Ghi trạng thái tách biệt: `local_accepted` chỉ cho hạng mục đã kiểm thử;
  nhánh dùng chung `deferred_by_user`; các điều kiện nhà cung cấp chưa đạt giữ
  `external_pending`. Không đánh dấu toàn GD01 hoàn tất khi còn việc phần mềm
  chưa triển khai/kiểm chứng, cũng không để điều kiện thương mại chặn việc local
  hợp lệ không phụ thuộc nó. Claude live vẫn hoãn; Antigravity không suy ra đã
  chạy inference từ danh mục hoặc trạng thái đăng nhập.

Tham chiếu giải thích đã đối chiếu:
[Đăng ký động và đăng nhập](https://developers.openai.com/siwc/token-sharing-open-source/sign-in),
[Phạm vi OSS/local và paid/remote](https://developers.openai.com/siwc/token-sharing-open-source).
Chú ý này là quyết định phạm vi triển khai, không phải bằng chứng đã thêm OAuth,
đã thay runtime, đã nghiệm thu provider hoặc đã được phê duyệt thương mại.

#### 6.1. Phương án cho từng nguồn AI — không hứa vượt điều kiện nhà cung cấp

| Nguồn | Việc cần làm tiếp | Điều không suy đoán |
|---|---|---|
| Codex | Đánh giá official app-server và Sign in with ChatGPT plan usage cho local; xác minh PAO đáp ứng điều kiện đăng ký/client/host, model/effort, consent và consumer scope. Kế thừa candidate, sau đó live test đúng phạm vi | Không giữ kết luận cũ “bắt buộc pay-as-you-go”; cũng không suy một login trên1VPS cho phép phục vụ mọi user hoặc bán lại thuê bao |
| Claude Code | Hoàn thiện contract/UX/offline bằng native CLI hoặc Agent SDK; user đã hoãn live vì chưa có gói. Kiểm auth/gói/phạm vi nhúng trước khi chọn live path | Native login/SDK tồn tại không tự chứng minh quyền dùng chung thương mại. Không tự mua gói, dùng API key hoặc bật chi phí |
| Antigravity | Catalog/native detection và hướng native Antigravity → MCP PAO chỉ đọc có thể giữ. Muốn PAO gọi inference cần đường provider cho phép và isolation đã đo; đánh giá API/Enterprise như phương án riêng | FAQ hiện không hỗ trợ consumer CLI wrapper trong app bên thứ ba. Không lặp quota smoke khi input không đổi; không xóa tool gate60 để báo pass |
| OpenAI/OpenRouter/API khác | Dùng API adapter chung; explicit effort theo model. Gemini/Anthropic capability và effort còn phải hoàn thiện/kiểm chứng | Không gắn universal effort, không gọi token estimate là hóa đơn/quota |
| Ollama/local endpoint | Optional provider; tách extraction/embedding khỏi hard dependency startup; nếu không có embedding thì nói rõ retrieval lexical/chưa index | Không xóa mọi model local trước khi hết import/dependency còn dùng |

Nguồn kiểm21/10: [OpenAI plan usage](https://developers.openai.com/siwc/token-sharing-open-source),
[app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server),
[giới hạn](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations),
[Claude auth](https://code.claude.com/docs/en/authentication),
[Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview),
[Google FAQ](https://www.antigravity.google/docs/faq/).
OpenAI phân biệt app OSS/local và paid/remote (cần đăng ký quan tâm); preview có giới hạn công cụ,
trong đó image generation không được hỗ trợ trên đường plan usage đó. Không dùng làm cam kết bán hàng.

### GD02 — Đồng bộ realtime xuyên module

**Mục tiêu:** không còn “Settings nối rồi nhưng Chat chưa biết”, hoặc “job xong nhưng bảng việc chưa đổi”.

1. Inventory producer/consumer đang fetch/poll/SSE; xác định authority và event đã có để tái dùng.
2. Contract sự kiện: event ID/sequence, scope, entity/version, timestamp, correlation/request ID,
   actor tối thiểu, type/version; **không secrets, prompt riêng hay nội dung SME khác** trong payload.
3. Transaction ghi dữ liệu + outbox cùng commit; delivery at-least-once, consumer idempotent.
   Redis Pub/Sub chỉ đánh thức, không thay log bền hoặc cam kết exactly-once bên ngoài.
4. Một luồng đăng ký có scope phía backend cho UI; reuse SSE/replay/snapshot, gap/expiry xử lý rõ.
   Chọn SSE hay WebSocket theo nhu cầu đo; không đổi transport chỉ vì Javis dùng WebSocket.
5. Cache/query store frontend thống nhất: AI catalog/status/default; session; task/progress;
   approval; knowledge ingest/version; plan/report/usage. Mutation ACK phải invalidation đúng consumer.
6. Multiple tabs/devices, sleep/offline/reconnect/resume, chậm mạng/backpressure và phân trang;
   fallback poll có nhãn stale; không dồn vô hạn queue cho tab ngủ.
7. SME switch/logout/revoke chặn data cũ ngay ở server; client hủy subscription và xóa cache scoped.
8. Tự động hóa kiểm thử luồng Settings → Chat → Agent/Task → Review → Report, cộng negative isolation.

**Nghiệm thu mục tiêu đề xuất, chưa phải số đo hiện tại:** thay đổi đã commit đến các màn hình liên quan
p95≤2giây trên LAN/test ổn định; snapshot sau nối lại≤5giây khi hạ tầng khả dụng; fallback refresh≤30giây.
Đo ít nhất100sự kiện và3tab; mất mạng30giây rồi hồi phục không mất trạng thái cuối/nhân job.
Auth backend áp dụng tức thì, không chờ SLA giao diện.
**Rủi ro/phát sinh:** out-of-order, snapshot/event race, stale auth, event storm, pool DB bị giữ, proxy buffer.
**Xử lý:** revision compare/cursor replay, snapshot watermark, bounded fan-out, stream cleanup, rate limits,
trace latency và không giữ transaction dài. Ngân sách hiệu năng phải đo trên máy hiện tại trước tăng worker.
**Gate:** realtime nguồn ngoài bị giới hạn bởi webhook/API provider; luôn hiện “lần đồng bộ cuối”, không gọi polling Ads là tick thực.

### GD03 — Cài đặt và UI/UX dành cho người mới

**Mục tiêu:** người dùng không cần đọc terminal hoặc hiểu grant/ledger để dùng PAO.

1. Luồng bắt đầu: chủ doanh nghiệp → tên SME/nhãn hàng → chọn AI → kiểm tra → vào Chat;
   lời mời nhân viên là nút riêng, không mở đăng ký công khai.
2. Trang chủ hiển thị việc cần làm/duyệt, báo cáo mới và sức khỏe kết nối; chỉ đưa số liệu thật,
   không dùng zero/green giả khi chưa kết nối.
3. Cài đặt có các khu vực gọn: doanh nghiệp/nhãn hàng; AI; kết nối; an toàn; dữ liệu/backup;
   chẩn đoán nâng cao. Giữ URL/deep link/SME đã có, tránh một tab chứa mọi form.
4. AI: Client trước API; key masked “đã lưu”, thay/xóa có xác nhận và nút Lưu rõ; test không đồng nghĩa save,
   không echo secret. Model/effort ở đầu Chat, privacy/usage ở khu vực phụ đã thiết kế.
5. Kết nối: Quảng cáo / Bot System / Plugins theo nhóm / MCP; mỗi provider có hướng dẫn,
   trường cần nhập, lấy ở đâu, chọn tài khoản/đích, test/status/ngắt. Chỗ chờ không giả nút hoạt động.
6. Windows local installer/launcher/doctor idempotent: phiên bản, port, Docker/DB/Redis, quyền thư mục,
   user chạy CLI; optional Ollama/Temporal/media/voice. Lỗi thiếu prerequisite có nút/hướng dẫn sửa.
7. Nâng cấp gói có source/dependency pin, checkpoint, release health và rollback code;
   dữ liệu rollback là bước riêng. Không chạy `pip install`/auto-update CLI thẳng vào runtime đang phục vụ.
8. Rà toàn bộ dark/light, tiếng Việt, contrast,320/390/tablet/desktop, keyboard, focus,
   loading/empty/error/unsaved changes và hướng dẫn đặt cạnh thao tác.

**Nghiệm thu:** clone sạch/môi trường thử cài và chạy được không sửa DB tay; không cần Ollama nếu chỉ dùng AI ngoài;
5hành trình chính hoàn thành bằng UI; Settings → Chat không reload tay; restart nhận đúng binary/profile.
Đo thời gian cài sau prerequisites, số thao tác và lỗi người mới; đặt mục tiêu sau baseline, không hứa số phút chưa đo.
**Rủi ro/phát sinh:** antivirus, PATH/Windows user khác, port trùng, Docker/WSL ngủ, wizard quá nhiều bước.
**Xử lý:** probe bounded, runtime pin, lỗi tiếng Việt, nâng cao thu gọn; sửa Docker local có thể đảo ngược,
không reset volumes/reboot/xóa WSL tự ý.
**Gate:** môi trường máy mới/VM nếu chưa có chỉ báo local prepared, không chứng nhận cài mọi máy.

### GD04 — Tri thức doanh nghiệp và bộ năng lực nhất quán

**Mục tiêu:** Chat/agent dùng đúng hồ sơ, tài liệu và skill mà chủ vừa cấu hình.

1. Hoàn thiện hành trình có sẵn BusinessProfile/versions: doanh nghiệp, brand, sản phẩm, khách hàng,
   giọng thương hiệu, ngân sách và KPI. Một source, không nhập lại ở plan/knowledge.
2. Kho tri thức chia: doanh nghiệp / nhãn hàng / tài liệu-wiki / kỹ năng / agent-quy trình.
   Nhóm content, marketing, thiết kế, editor, Ads là metadata, không tự cấp tool.
3. Import nguồn → kiểm tệp/PII → ingest/version → citation → index; trạng thái và lỗi đến Chat.
   Full-text/lexical fallback và embedding optional được ghi rõ; graph chỉ hiện dữ liệu được phép.
4. Studio skill/agent/workflow reviewed/published version; import/export có preview,
   assigned agent, model/effort và tài liệu mẫu; tái dùng registry, không thêm định nghĩa song song.
5. Context compiler và lazy load kỹ năng dùng chung mọi engine; provenance và token budget;
   đổi brand/Brain không tiếp tục mang prompt/CLI resume của scope trước.
6. Learning mặc định đề xuất/xem diff; publish/revert phiên bản có kiểm quyền;
   không tự biến lời chat thành chính sách hoặc lệnh có quyền.
7. Search/export/retention theo phạm vi; memory riêng và nội dung đã thu hồi không lọt báo cáo.

**Nghiệm thu:** sửa profile/skill → Chat và job mới dùng đúng version; job cũ giữ pin;
nguồn có trích dẫn thật; hỏi chéo2SME/Brain bị chặn; reindex/retry không nhân tài liệu;
learning sai có thể xem và hoàn tác.
**Rủi ro/phát sinh:** memory poisoning, source lỗi/khổng lồ, trùng registry, embedding mismatch, stale pins.
**Xử lý:** version/provenance, file/size limits, review, cache scoped và migration/reindex riêng.
**Gate:** nhận tài liệu khách thật cần phạm vi/đồng ý; dữ liệu giả chỉ là nghiệm thu local chức năng.

### GD05 — Chu trình kinh doanh và agent thực thi thật

**Mục tiêu:** khép kín công việc, không thêm một “Goal runner mới” cạnh P6.

1. Đối chiếu S5/native/P6 đã có; chọn một use case: kế hoạch tháng cho một brand, đầu ra content text,
   phân tích dữ liệu nhập và báo cáo. Ghi điều kiện chưa có dữ liệu, không bịa KPI.
2. Chat tạo draft plan có version/nguồn/giả định/dự toán; chủ sửa/duyệt;
   dùng adapter tạo Project/Goal/Task hiện có, tránh chat chỉ hứa mà không tạo job.
3. Per-job assignment kế thừa brand/agent/step; preview “ai làm, model nào, dùng công cụ gì, trần nào”.
   Một model planner và model worker khác khi có năng lực thực tế.
4. Nối inference vào native execution còn dry-run theo chốt cấp phát đã có; giữ attempt/accounting,
   cancel/stop/ACK/idempotency/lease. Không xây hệ queue hoặc scheduler thứ hai.
5. Dependency, rework và review sản phẩm; background job tiếp tục khi đóng tab,
   có thể dừng, retry có preview, không tự phát lại hành động trạng thái unknown.
6. Giờ/ngày: scheduler native → báo cáo trong PAO → result inbox → Chat/activity;
   lịch có timezone, missed-run policy, quota/time/iteration budget và manual pause.
7. Outcome đối chiếu evidence, learning đề xuất; không kết luận tăng doanh thu do AI từ tương quan.
8. Đo concurrency trên worker hiện max_jobs=1/dispatch10giây; tăng có fair queue, per-provider
   concurrency và chống starvation, không mở hàng loạt model khiến máy/quota cạn.

**Nghiệm thu:** một business cycle end-to-end bằng AI thật đúng phạm vi được cấp;
plan → task/attempt → artifact/review → report, nhìn thấy model/effort/usage/pin từng bước;
crash/restart/cancel/duplicate event/rework không nhân việc, không mất báo cáo, không lẫn SME.
Tách nghiệm thu nội dung text với Ads/media; không yêu cầu cả3CLI live để đóng use case một nguồn.
**Rủi ro/phát sinh:** vòng lặp vô hạn, tool side effect, lỡ hạn quota, job mồ côi, report không có dữ liệu.
**Xử lý:** stop conditions/budget, owner review, durable state, incident center một nơi và “chưa đủ dữ liệu”.
**Gate:** chạy lịch/inference thật phải có cấu hình quota và phạm vi thử; chưa gửi Telegram hoặc chi tiền Ads.

### GD06 — Dữ liệu thật chỉ đọc và kết nối có giá trị

**Mục tiêu:** báo cáo khớp nguồn gốc, không tăng số logo connector để tính hoàn thành.

1. Nghiệm thu trước bằng file export thật nếu OAuth chưa sẵn sàng; chọn SME/brand/kỳ/tiền tệ/timezone,
   giữ original/hash/source metadata, không hỏi token trong chat.
2. Meta hoặc Google trước: audit official docs phiên bản hiện tại, auth/scopes/review,
   app PAO mặc định/BYO advanced, rotation/revoke, account/destination, rate limit.
3. Nối Settings → chọn tài khoản → sync → warehouse → Ads/dashboard/Chat/agent/report;
   cursor/backfill/incremental và ngày dữ liệu mới nhất phải nhìn thấy.
4. Đối soát chi phí/impressions/click/conversion/doanh thu với export theo cùng định nghĩa attribution;
   ghi tolerance, missing/late adjustments và FX, không ghép sai thước đo.
5. MCP: chọn một server thật read-only; scoped secrets, SSRF/process boundaries, timeout/revoke,
   tool discovery/capability đưa vào Gateway chung, không vào credential riêng của CLI.
6. Chỉ sau đó chọn TikTok, Sheets/POS/Pancake/Botcake… theo nhu cầu. Mỗi connector là một hồ sơ
   API + bài thử local + bài thử thật; GPT Ads giữ planned nếu chưa có API và quyền được xác minh.

**Nghiệm thu:** ít nhất1nguồn thật đối soát có biên bản; số liệu Chat/dashboard/report cùng snapshot;
ngắt/thu hồi/lỗi429 không mất dữ liệu hoặc báo xanh giả; chọn sai SME/tài khoản bị chặn.
**Rủi ro/phát sinh:** App Review, token hết hạn, tài khoản thiếu quyền, webhook không đến local,
dữ liệu trễ và chênh conversion windows.
**Xử lý:** file import thay thế rõ ràng, backoff/checkpoint sync, status stale/degraded và retry không nhân rows.
**Gate:** user đã hoãn dữ liệu thật trước đây; khi đến nghiệm thu mới cần chọn/cấp nguồn.
Không tự công khai webhook/VPS để xử lý thiếu OAuth.

### GD07 — Sáng tạo nội dung và media có sản phẩm thật

**Mục tiêu:** nối text → ảnh/video → phiên bản → chủ duyệt bằng file có thể dùng.

1. Brand brief/copy/calendar → agent thiết kế/editor; chọn model theo **modality**, không theo tên nghề.
2. Chọn provider/tool ảnh/video được hỗ trợ và phương thức tính phí hợp lệ, không giả model chat có image tool.
3. Artifact storage/version/preview/download; seed/source/reference/license/font/logo và metadata nguồn.
4. Quy trình feedback/rework, giữ bản cũ; tránh thay ảnh đã duyệt trong lịch đăng.
5. Render/transcode worker cách ly, giới hạn tài nguyên/cancel, không làm nghẽn Chat.
6. Nối lịch nội dung, plan/task/report; export trước, publishing qua GD08.

**Nghiệm thu:** tạo ảnh/video thật trên provider đã chọn, mở/tải được, nhận xét và sửa phiên bản,
dừng render không để process con; đúng text/logo theo rubric do chủ duyệt.
**Rủi ro/phát sinh:** phí render, bản quyền, watermark, chất lượng, file lớn/timeout.
**Xử lý:** dự toán/xác nhận trước lượt tốn phí, preview, giới hạn storage và provider fallback phải được chọn.
**Gate:** tài khoản media/chi phí/tài sản thương hiệu; có thể hoãn nhánh này mà không chặn MVP text.

### GD08 — Hành động ngoài hệ thống có kiểm soát

**Mục tiêu:** “tôi duyệt thì chạy”, không phải chỉ có nút approve.

1. Chọn riêng từng loại action: đăng bài/gửi tin/sửa Ads/budget; audit provider API/permissions.
2. Preview exact target/account/content/budget/version; approval gắn hash/phạm vi/thời hạn,
   tách duyệt plan, duyệt nội dung và cho phép hành động thật.
3. Reuse policy/approval/ledger/outbox hiện có; kiểm lại quyền và balance ngay trước gửi.
4. Adapter read-after-write/reconcile; unknown không retry mù; idempotency và duplicate prevention ở mức provider cho phép.
5. Kill switch/emergency stop, giới hạn chiến dịch, nhật ký ai/AI nào duyệt/gửi; rollback/bù trừ
   chỉ khi API cho phép, không hứa thu hồi bài/tin/chi phí đã phát sinh.
6. Nghiệm thu sandbox/test destination trước; một action nhỏ thật cần approval riêng ở thời điểm thực hiện.

**Nghiệm thu:** từ chối thiếu/đổi approval; không vượt trần; lost ACK không nhân action; revoke/cancel
chặn queued work; báo cáo khớp trạng thái provider và tiền thực tế.
**Rủi ro/phát sinh:** tiêu tiền, gửi sai khách, publish nhầm, retry trùng, action không đảo được.
**Xử lý:** deny mặc định cho writes mới, approval ngắn gọn một nơi, giới hạn cụ thể và reconcile.
**Gate:** quyền Ads/publishing/outbound và ngân sách chưa được cấp trong lượt lập kế hoạch này.

### GD09 — Kênh điều khiển, khách hàng, CRM và giọng nói

**Mục tiêu:** mở rộng kênh mà không tạo PAO thứ hai hoặc lộ quyền chủ.

1. Telegram trước: một bot thuộc1SME, nhiều bot/SME được; pairing numeric Telegram ID ↔ PAO member,
   quyền ứng dụng kế thừa. Đích nhận báo cáo tách người được điều khiển.
2. Cùng resolver AI/run/knowledge/approval/report như Web; slash commands/status/stop,
   pinned channel model nếu chủ muốn; không cấp lại AI theo từng bot/người.
3. Live inbound/outbound/dedup/reconnect/revoke/takeover trên bot/đích được chọn.
4. Zalo OA/Lark/Discord/Slack/WhatsApp làm từng adapter chính thức và scope;
   phân biệt admin channel và bot chăm khách, không cấp owner cho khách ngoài.
5. CRM native: contacts/deals/activities/consent/import/dedup nếu nhu cầu vượt dashboard attribution;
   customer inbox/manual takeover/handover và liên kết task/report.
6. Voice: transcript xác nhận → cùng Run → response TTS; mic consent, mute/barge-in/cancel,
   đo tiếng Việt/môi trường ồn; không tự chấp thuận hành động qua giọng nói.

**Nghiệm thu:** Web và một kênh thật cùng trạng thái; người lạ/member revoked bị chặn;
takeover dừng bot; giao tin unknown không gửi đôi; mic thật có rubric WER/latency và quyền riêng tư.
**Rủi ro/phát sinh:** impersonation, webhook trùng, ngập tin, PII, sai ASR, API cá nhân không được hỗ trợ.
**Xử lý:** identity mapping/dedup/rate cap, retention tắt đến quyết định riêng, official auth và labels rõ.
**Gate:** tài khoản/kênh, mic và đích gửi thật; không bật tất cả kênh để tính parity Javis.

### GD10 — Nghiệm thu local và pilot chủ doanh nghiệp

**Mục tiêu:** chứng minh PAO dùng được trong công việc hằng ngày, không chỉ tests xanh.

1. Chốt phạm vi MVP, danh mục enabled/disabled, real vs fixture và điều kiện gói AI.
2. Full regression trên **source/dependency/schema hiện tại** trong môi trường riêng; Node/contract/
   typecheck/build/browser dark-light, security negative, migration/restore khi có thay đổi.
   Không cộng dồn focused tests thành full hoặc chạy nhiều runner dùng chung DB.
3. Nghiệm thu real-data read-only + AI thật + chu trình GD05; test quyền, mất mạng, hết quota,
   restart, stale model, cancel/stop/retry và backup restore clone.
4. Pilot đề xuất7ngày sử dụng thực tế của chủ; ghi task hoàn thành, lỗi, thời gian tiết kiệm,
   chất lượng nội dung, token/quota/chi phí và tỷ lệ thao tác cần hỗ trợ.
5. Fix lỗi chặn công việc trước thêm tính năng; tài liệu “bắt đầu”, video/hướng dẫn nếu cần,
   issue list với owner/ưu tiên/reproduce và biên bản chấp nhận hạn chế.

**Nghiệm thu đề xuất:**0lỗi P0/P1 mở trong scope;100%journey bắt buộc đạt; không leak SME/
khóa; ít nhất1chu kỳ business có evidence thật; backup restore pass; chủ chấp thuận bằng văn bản.
Đây là mục tiêu, chưa phải kết quả21/10.
**Rủi ro/phát sinh:** scope creep, dữ liệu chưa cấp, dùng đồng thời làm drift test, demo pass nhưng thực tế lỗi.
**Xử lý:** freeze scope/source cho từng lượt, môi trường riêng, timestamp/correlation và giữ failures.
**Gate:** dữ liệu/quota/pilot owner; nhánh chưa thử phải ngoài scope thương mại, không gắn nhãn “toàn PAO xong”.

### GD11 — VPS, private production và thương mại hóa (đang hoãn)

**Mục tiêu tương lai:** cài cho từng khách hàng, vận hành và nâng cấp an toàn.

1. Mở lại yêu cầu host; chốt dedicated installation/tenancy, cơ chế cấp phép AI phù hợp,
   giá gói, quota/billing, hỗ trợ và chính sách dữ liệu. Không coi MIT của Javis là quyền bán dịch vụ model.
2. Reuse CI/private production đã chuẩn bị; chạy lại đúng source mới, khóa dependencies/image,
   vá security findings, SBOM/license/provenance, không lấy CI3151851 làm bằng chứng bản hiện tại.
3. Nonroot/least privilege/TLS/firewall/private DB/file secrets, user dịch vụ riêng, rotation,
   auth/2FA/session/rate limit và phân tách operator/SME owner.
4. Offsite backup mã hóa + keys/private blobs, restore máy sạch, RPO/RTO đo thật,
   alerts/monitoring/log redaction/incident response; kiểm reboot trên host thử được cấp.
5. Release/update/rollback/canary/compatibility; nâng phiên CLI có xác minh, không tự cập nhật đồng loạt.
6. Pilot private remote, support/export/deletion workflow theo chính sách đã chốt; public launch chỉ khi có quyết định.

**Nghiệm thu:** hosted CI đúng release, restore đầy đủ/HTTPS/reboot/security/owner gates đạt;
bản cài tái lập, tài liệu vận hành và quyền thương mại provider rõ ràng.
**Rủi ro/phát sinh:** mất keys, tenant leak, outages, chi phí VPS/quota, điều khoản nhà cung cấp thay đổi.
**Xử lý:** phục hồi tập dượt, release pin, rollback, least privilege và kiểm hợp đồng theo thời điểm.
**Gate:** **deferred_by_user**. Không tự thuê VPS, mở port/public OAuth callback, push/merge/deploy hoặc đổi gói.

## 7. Phạm vi mở rộng sau lõi — không bị bỏ quên

| Nhóm | Việc còn cần | Khi triển khai |
|---|---|---|
| Engineering/terminal | Bind repo, sandbox/process tree/network/env, diff/test/artifact, review trước apply/merge/deploy | Nhánh sau GD00/01/05; tái dùng P8/M7B, không mở shell toàn máy cho agent |
| Plugin/packs | Manifest/version/capability/provenance, preview import, signature/allowlist, isolation/update/revoke | Sau GD04/06; definition pack trước arbitrary Python plugin |
| Research/web/YouTube | Tool có nguồn, giới hạn tải, privacy/copyright, tách prompt injection khỏi authority | Theo nhu cầu GD04/07, không cấp browser vô hạn |
| Knowledge graph/portable Brain | Tối ưu graph lớn, export/import Markdown có conflict/version review | GD04 rồi đo nhu cầu; không Git-sync bí mật/runtime DB |
| Dashboard/usage/analytics | Một nguồn metric có freshness, usage/chi phí/quota tách biệt, health/incident actionable | GD02/05/06/10 |
| Mobile/notification/sharing | Responsive trước; push/link chia sẻ có scope/expiry/revoke sau threat model | GD03/09; không tự public Brain |
| Billing/licensing/admin ops | Entitlements sản phẩm, support tools, audit/export, legal/data lifecycle | GD11 khi mô hình thương mại được mở lại |

## 8. Chuẩn UX, realtime và nghiệm thu áp dụng cho mọi giai đoạn

- Không giao “nút mới đã có” nếu backend/run consumer chưa dùng được.
- Mỗi tính năng giao đủ: dữ liệu/API → runtime/worker → UI → đồng bộ → lỗi/retry/cancel →
  hướng dẫn tiếng Việt → test/restore/biên bản, hoặc ghi rõ phần external chưa đạt.
- Trạng thái đồng nhất: Chưa thiết lập / Đã lưu / Đang kiểm tra / Sẵn sàng / Gián đoạn /
  Cần đăng nhập lại / Chưa hỗ trợ. Luôn có lần kiểm tra cuối và hướng xử lý.
- Hành vi hỗ trợ khi thiếu dữ liệu: đọc và soạn nháp vẫn dùng được; chỉ chặn chức năng phụ thuộc
  thiếu nguồn. Không vô hiệu hóa toàn PAO vì một adapter lỗi.
- Không expose từng công tắc thử nghiệm cho khách; cấu hình nâng cao/operator có lý do và help,
  nhưng giữ feature flags nội bộ cho release/rollback, không xóa bảo vệ để che phần chưa làm.
- Không đổi enum/backend scope/URL/credential khi Việt hóa.
- Không tự xóa dữ liệu. Yêu cầu xóa có preview + xác nhận riêng; account invite-only giữ nguyên.

### 8.1. Bộ test xuyên tính năng bắt buộc

| Luồng | Điều cần chứng minh |
|---|---|
| Connect → Chat | Lưu/kết nối xong, catalog hiện đúng, dùng đúng nguồn mà không reload/cấp grant AI lại |
| Chat → Agent/Job | Model/effort override có hiệu lực ở adapter thật; tool authority không tăng |
| Profile/Knowledge → Plan | Đúng SME/brand/version/citation; thu hồi nguồn làm lượt mới tái kiểm |
| Task → Review → Report | Một identity nghiệp vụ; ACK/retry/stop/rework có lịch sử và cùng trạng thái nhiều tab |
| Disconnect/429 → mọi consumer | Báo lỗi rõ, bỏ chọn nguồn không còn dùng được, không paid fallback hoặc job hồi sinh |
| Offline → reconnect | Snapshot/replay lấp khoảng trống; không phát lại mutation/action |
| Workspace switch/revoke | Không cache/event/CLI resume/context vượt scope; quyền backend có hiệu lực ngay |
| Update → restore | Checkpoint/clone/contracts/archive/read replay; old execution pins không bị viết lại |

## 9. Quản lý rủi ro và tránh mắc kẹt một phần việc

Mỗi issue phải có: ID, phạm vi, ảnh hưởng, bằng chứng/reproduce, owner, phương án,
test cần đạt, gate external, trạng thái và bước kế tiếp. Không tạo thêm roadmap song song.

- **P0:** leak/secret/corruption/chi tiền hoặc hành động sai → dừng đúng đường tác động, giữ evidence.
- **P1:** không chạy core/mất job/sai scope/stale state → sửa trước thêm chức năng.
- **P2:** UX/hiệu năng/khôi phục chưa tốt → xếp trong giai đoạn có owner và tiêu chí đo.
- **External:** thiếu quyền/gói/API review/dữ liệu/host → ghi pending/deferred, nêu ai cần làm gì;
  tiếp tục phần độc lập, không gọi pass hoặc lặp test cùng input vô hạn.
- Mỗi lần thử lại phải nêu thay đổi input/giả thuyết. Với cùng blocker không đổi,
  không rerun full regression/smoke quota để tăng số test.
- Source thay đổi có phạm vi → focused tests trước; release current → full hiện tại khi cần.
  Giữ failed receipts/drift; không restore primary hoặc sửa assertion để làm xanh.
- Các gates bảo mật và điều kiện provider là backend/product constraint, không biến thành form grant dài cho người dùng.

## 10. Mapping lịch sử và bằng chứng

| Mốc cũ | Kế thừa / phần còn mở trong roadmap mới |
|---|---|
| M0–M2/P0–P5 | Nền đã có; GD00/01/04/06 chỉ xử lý gap, không viết lại registry/runner |
| M3/S6.1 | Dữ liệu thật và đối soát → GD06 |
| M4/S4 | Events/approvals/policy local → GD02/08, real action chưa đạt |
| M5A/P1/P2 | Brain/Knowledge/source/wiki → GD04 |
| M5B/P6/S5 | Outcome/native workflow/plan-job-report → GD05/10; dry-run chưa phải tự động AI thật |
| M6/S6.2 | UX/account/data local đã có; polish/install → GD03, current integration → GD10 |
| P7/S3 | Channel/inbox/voice local → GD09; mic/bot thật còn mở |
| P8/M7/M8 | MCP/engineering/media/extensions → GD06/07 và mục7 |
| EA/RAI | Tài nguyên AI/candidate/provider admission → GD01, không mặc định cài candidate |
| Phase3/S6 production | CI/private infra lịch sử kế thừa; GD11 hoãn, không mất công cũ |

Các báo cáo quan trọng:
[Enterprise/Knowledge](ENTERPRISE-KNOWLEDGE-LOCAL-2026-10-18.vi.md),
[local cycle](LOCAL-OPERATING-CYCLE-2026-10-18.vi.md),
[UX dark/light](LOCAL-UX-LIGHT-DARK-2026-10-18.vi.md),
[account/data](S62-ACCOUNT-DATA-LOCAL-ACCEPTANCE-2026-10-17.vi.md),
[hosted CI lịch sử](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md),
[production remediation lịch sử](PHASE3-GATE-REMEDIATION-2026-10-17.vi.md).
Không sửa receipt cũ để khớp kế hoạch mới.

## 11. Gói triển khai tiếp theo

**GD00 local đã đạt; kế tiếp hoàn thiện GD01**: giữ baseline/backup hiện tại,
rồi một đường tài nguyên AI dùng xuyên Chat–Agent–Job, model/effort động,
không grant AI cá nhân trong UX thường.

Trong GD01, chốt provider eligibility sớm; tiếp tục nguồn hợp lệ có sẵn,
để Claude `deferred_by_user` và Antigravity wrapper `external_pending` nếu điều kiện chưa thay đổi.
Không chờ cả3nguồn xong mới làm realtime/UX, cũng không gọi chúng đã live.

Sau GD01: GD02 đồng bộ trạng thái; GD03 cài đặt/UX; GD04–05 khép vòng nghiệp vụ;
GD06 dữ liệu thật; GD10 pilot local. Chỉ mở GD07/08/09 theo nhu cầu và quyền tương ứng,
rồi GD11 khi người dùng yêu cầu lại.

**Duyệt kế hoạch không tự cấp quyền gọi quota, gửi/đăng/chi tiền, thay identity nhà cung cấp,
xóa dữ liệu, commit/push hoặc deploy.** Các hành động có tác động được xác nhận tại bước cần thiết.

