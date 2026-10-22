# Bàn giao hiện trạng PAO cho Muse — 22/10/2026

## Sản phẩm và định hướng đã chốt

PAO là hệ điều hành hỗ trợ một chủ doanh nghiệp/nhóm1–3người vận hành doanh
nghiệp: hiểu hồ sơ/nhãn hàng → lập kế hoạch → phân việc cho agent/người → duyệt
sản phẩm/hành động → theo dõi → báo cáo. Một người có thể sở hữu nhiều SME;
dữ liệu/memory/credentials/usage của mỗi SME vẫn tách biệt. Tài khoản invite-only,
owner hiện có được tạo SME mới độc lập, không clone thành viên/memory/connection.

Mục tiêu thương mại có thể là bản cài riêng/VPS mỗi khách hàng; hiện ưu tiên
local dễ dùng, thực nghiệm bằng dữ liệu thật rồi pilot trước VPS/public.
Kết nối AI nên một lần, đa model/effort, Chat/Agent/Job dùng được ngay; không
thêm màn cấp quyền AI từng nhân viên. Quyền dữ liệu/công cụ/chi tiền vẫn riêng.
Nhà cung cấp không được hardcode theo agent: SME/brand/agent/step/job tùy chỉnh.

## Source snapshot và bằng chứng

Nguồn sao chép `F:\PAO-ACOS` là cây đang làm việc, gồm cả untracked/dirty cần
thiết theo allowlist; không chỉ lấy Git HEAD cũ. Source schema0077,161bảng vật lý,
435API operations. Source binding tại bàn giao:
`c66ec3423c4814b16000c34a0f868ad101e8204c06a7c1451e707c1eac1eaceb`.

`handoff/source-manifest.json` ghi hash source trước overlay. Root AGENTS được
thay bằng scope G:; bản gốc lưu `handoff/AGENTS-SOURCE-HISTORY.md`. Các file khác
phải giữ nguyên tới lúc tạo baseline. Copy không chứa history Git, receipts
runtime, dữ liệu SME hay secret. Các đường .runtime trong docs là tham chiếu lịch sử
ở nguồn, **không phải file đã copy hoặc bài test đã chạy trong fork**.

## Đã có trong mã nguồn

| Module | Đã có | Giới hạn/chưa xong |
|---|---|---|
| SaaS/enterprise |Owner, invite/members/roles, nhiều SME/brand, profile/version, session revoke, scoped export/yêu cầu xóa|Không public signup hoặc tự purge; production chưa đạt|
| Chat |History, SSE/replay/cancel, privacy, model/effort, usage, compact, safe error|Một số provider native buffered; realtime toàn app chưa thống nhất|
| AI registry |Installation resource, API/Client UI, đa model/effort, immutable routing|Shared Codex và toàn GD01 chưa xong; API key/login không mang sang fork|
| Muse |Profile riêng,5model selectable, text Chat/planner/Studio/job, actual usage, containment/cancel|Pin native1.4.10; overhead~14k; chưa token streaming/production/Contributor thật|
| Codex |Personal official profile, native model list6, riêng model từng chat, Luna đã thử ở nguồn|Codex container64KiB, native effort/shared identity còn gate riêng|
| Claude/Antigravity |UI/catalog và protocol/adapter preparation|Không coi text inference đã nghiệm thu; Claude user hoãn|
| Knowledge |Business/brand info, Brain/notes/sources/wiki/RAG/graph, skills/agent library|Embedding cần provider; media/editor là text-only nếu chưa build|
| Business |Profile→plan→review→job dependencies→artifact review→Task/Goal/Project/report|Synthetic local accepted, không phải chiến dịch thật tự vận hành|
| Goal/workflow |P6 native, workflow/version/scheduler/approval/recovery services|Không thêm runner; model-autonomous Goal/Temporal với Muse chưa accepted|
| Ads/channels |Meta/Google code, read warehouse, approvals; Telegram pairing/role/inbox; MCP|Chưa Ads thật/publishing; TikTok/GPTAds và nhiều plugin còn placeholder|
| UX |Việt hóa, Settings nested tabs, Client/API model popup, dark/light/Auto06–18h, task delete|Mỗi phần cần UX/realtime nghiệm thu thật, không suy từ build|
| Ops |Locked dependencies, source/DB checkpoint, restore/CI/private-production harness|Hạ tầng production/offsite/full-hostDR/owner pilot vẫn chưa đạt|

## Bằng chứng mới nhất trên NGUỒN, không cộng thành full regression mới

- Provider-token policy22/10: default mới `provider`, bỏ context/output/run token
  cap riêng PAO. Legacy API bounded và snapshot cũ giữ nguyên. Privacy/calls/
  timeout/byte guards còn. Muse Spark1.2/High planner695, final1369token completed;
  replay0call,2quota calls dữ liệu tổng hợp.10focused/262Node/build và installed
  GET2SME/5Muse/6Codex/3replay đạt.552functional đạt nhưng receipt false do sessions drift.
- Muse business22/10:2dependentjobs qua ARQ thật, owner review, Task/Goal/Project
  completion/report đúng usage;134focused và1live test/2calls. Chưa P6 Goal/Temporal.
- Muse adapter:543scoped backend/31nativeunits/257Node/build. Original orchestrator
  pytest failed fixture assertion dù2attempt completed; giữ nguyên failure.
- Codex multi-model:6native catalog,2Luna model đã chạy marker thật qua UI nguồn;
  không coi là mọi model/effort/shared identity được nghiệm thu.
- GD00 source local restore accepted. OldPhase3 hosted2258 là baseline lịch sử,
  không phải full regression của source mới hoặc fork này.

Đọc theo thứ tự độ mới: PROVIDER-TOKEN-POLICY → MUSE-BUSINESS-JOB-ACCEPTANCE →
MUSE-TEXT-ADAPTER → GD01-CODEX-MULTI-MODEL → master roadmap. Chỗ report cũ còn
nói Muse catalog-only/minimum32768/65536 được note mới supersede, không sửa history.

## Roadmap hiện hành

| Giai đoạn | Mục tiêu | Trạng thái nguồn |
|---|---|---|
| GD00 |Baseline/backup/restore|Local accepted; offsite/full-hostDR pending|
| GD01 |AI dùng chung, đa model/effort, Chat/Agent/Job|In progress, nhiều lát cắt accepted|
| GD02 |Realtime provider/job/review/report xuyên app|Chưa nghiệm thu toàn contract|
| GD03 |Bộ cài/UX người mới|Có UX lát cắt; bộ cài sản phẩm còn việc|
| GD04 |Business knowledge/skills/agents thống nhất|Core có; còn hợp nhất/nghiệm thu|
| GD05 |AI business cycle thật|Synthetic Muse job accepted; real quality/pilot còn chờ|
| GD06 |Số liệu thật read-only/đối soát|User chưa cấp data/live connector; không tự hỏi lại trong prep|
| GD07 |Ảnh/video có artifact thật|Chưa coi text model là image/video provider|
| GD08 |Publish/send/Ads write có duyệt|Cần authority và live acceptance riêng|
| GD09 |Telegram/CRM/voice/channel|Nhiều code/fixture; từng connector cần live riêng|
| GD10 |Local owner pilot|Chưa đạt|
| GD11 |VPS/private production/thương mại|Hoãn theo người dùng|

Không có cơ sở tính phần trăm hoàn thành toàn sản phẩm từ số file/test. Không
mở lại P6/S2/S3 hoặc tạo hệ runner mới vì chưa đọc receipts/roadmap.

## Việc fork cần làm tiếp

1. Xác nhận baseline trong `handoff/COPY-ACCEPTANCE.json`; fork không thừa hưởng
   đăng nhập hay connection của nguồn. Đăng nhập PAO bằng tài khoản sandbox mới.
2. Chủ đăng nhập Muse chính thức vào profile PAO của fork nếu cần test chat;
   không dùng profile Orca ngầm. Không tự chạy quota thật để "chứng minh đã nối".
3. Chốt một gap GD01/nhánh thí nghiệm rồi thiết kế checkpoint/test/rủi ro trước.
4. Ưu tiên quan sát lỗi/usage và context lớn; giữ pins/ledger/approval/replay.
5. Sau contract nguồn AI ổn định mới đi GD02 realtime, không tuyên bố GD01 xong.
