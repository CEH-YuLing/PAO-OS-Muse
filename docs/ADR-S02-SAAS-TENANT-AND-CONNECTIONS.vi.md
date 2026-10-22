# ADR-S02 — SaaS nhiều doanh nghiệp, bộ nhớ và kết nối có phạm vi

Ngày 11/10/2026 (Asia/Saigon). Target `F:\PAO-ACOS`.
Trạng thái: ba quyết định sản phẩm được người dùng phê duyệt trực tiếp; thiết kế
mapping/quyền/threat model bên dưới đã được ghi nhận cho triển khai theo checkpoint.
Đây không phải nghiệm thu cách ly runtime, migration hoặc kết nối production.
Thứ tự do [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu.

**Cập nhật16/10: S3 và toàn S4 đã local_accepted; bước tiếp theo là S5.**
Xem [sổ S4](S4-COMPLETION-REGISTER.vi.md). Các đoạn tiến độ11–15/10 phía dưới
là lịch sử; không dispatch lại S3.2C hoặc suy ra real OAuth/production đã đạt.

Cập nhật14/10: toàn S2/S2.3 đạt local theo [S2 register](S2-COMPLETION-REGISTER.vi.md)
và [nghiệm thu tích hợp](S2-FINAL-INTEGRATION-2026-10-14.vi.md):1684backend/
21browser/80Node/build21/0058/live334/exact restore. S3.1A nay đạt local0059/live334
theo [evidence](S31A-LOCAL-ACCEPTANCE-2026-10-14.vi.md). S3.1B và tổng S3.1 cũng
đạt local15/10,1737backend/5browser/96Node/build21/0060/live338/exact restore theo
[evidence mới](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md). S3.2A kernel nay
source_verified theo [evidence](S32A-KERNEL-2026-10-15.vi.md); tiếp theo duy nhất
S3.2C — bridge/webhook/report integration; B đã
[source_verified368affected/25Node/candidate0063](S32B-SCOPED-EXECUTION-2026-10-15.vi.md).
Chưa rollout candidate hoặc gọi
nhiều bot thật đã accepted; A/B/C hữu hạn trong ADR-S32.
Các dispatch/quota UI chưa đạt
trong evidence13/10 phía dưới là lịch sử, không thứ tự hiện hành. Không thay
quyết định sản phẩm/threat model hoặc coi focused tests là toàn SaaS/production.

## 1. Quyết định đã chốt

1. Một hệ thống PAO dùng chung phục vụ nhiều SME.
2. Một SME có nhiều nhãn hàng, thành viên và kết nối; một user có thể thuộc nhiều SME.
3. OAuth qua ứng dụng PAO là mặc định khi provider hỗ trợ mô hình đó; SME có
   thể dùng App ID/Secret riêng ở chế độ nâng cao. Telegram và provider token-based
   có luồng nhập credential riêng, không ép thành OAuth không được hỗ trợ.
4. Settings phải có giao diện cấu hình phù hợp từng app; trước triển khai mỗi
   connector, kiểm tài liệu API chính thức hiện hành và yêu cầu xác thực/quyền.

Phê duyệt này không cấp quyền gọi tài khoản thật, chi tiền, đăng bài, public
deploy hoặc tự chuyển private context sang cloud. Credential không đưa vào chat.

## 2. Mapping: kế thừa entity hiện có

Đã đối chiếu `models.py`, `modules/brains/access.py`, connector service và các
entity Project/Goal/Task trong lượt này. Không tạo bảng hoặc đổi ID ở S0.2.

| Khái niệm sản phẩm | Nền hiện có | Phần triển khai tiếp |
|---|---|---|
| Doanh nghiệp/SME | Workspace | Dùng workspace_id làm tenant ID; Company là nhãn UI, không một tenant engine mới |
| Người dùng của nhiều SME | User + Member(workspace_id,user_id) | Role/grant theo từng SME; chọn workspace rõ ràng, không quyền toàn cục từ vai trò ở SME khác |
| Nhãn hàng | Brand có workspace_id | Brand grants, profile và mapping tài khoản; kiểm parent tenant ở mọi request/job |
| Bộ nhớ/tri thức | Brain/BrainMember/Memory, source versions | Giữ private legacy memory; nguồn được retrieve theo workspace + brand/Brain ACL + actor |
| Kế hoạch tháng | Project/Goal/Task + StudioVersion/plan pins | BusinessPlan/profile/version là lớp nghiệp vụ mới ở S5; không coi Studio DAG là kế hoạch marketing đầy đủ |
| Chiến dịch | Project/plan references và Ads entities từ provider | Campaign brief nội bộ khác remote campaign; schema/mapping cụ thể chốt trong S5/S4, không giả entity đã có |
| Phân công/thực thi | Task/TaskAttempt, Studio/Goal execution, ARQ/Temporal | Một execution ownership; specialist adapter đi qua Gateway/policy, không bỏ dry-run fences |
| Kết nối | ModelProviderConnection, ConnectorConnection/Secret, Meta/GoogleConnection | Resolver có tenant/connection/config version; migrate dần từng provider, không bảng token chung thiếu schema |
| Phê duyệt | Domain approvals/event timeline/grants | Pin phạm vi/hành động/version và recheck; quyền dự án không mặc nhiên là quyền chi tiền |
| Ngân sách/tài nguyên | Task budgets/Goal reservations/Ads policy | Tenant quota và campaign money ledger tách mục đích; AI token budget không là Ads budget |

Workspace sở hữu dữ liệu; user tạo dữ liệu không làm dữ liệu tự thuộc mọi SME
của user đó. Cùng tên nhãn hàng hoặc remote ID không đủ xác định tenant.

## 3. Ranh giới bộ nhớ và ngữ cảnh

- Mặc định không có bộ nhớ doanh nghiệp dùng chung toàn hệ thống. Brain của SME A
  không được search/retrieve/compact/learn vào SME B dù cùng owner hoặc cùng model.
- Phân biệt dữ liệu doanh nghiệp được cấp quyền chia sẻ, dữ liệu nhãn hàng và
  private user memory/chat trong workspace. Owner/admin quản trị doanh nghiệp
  không tự được đọc private legacy facts; giữ fence hiện có trong Brain access.
- Chia sẻ kiến thức giữa các nhãn hàng cùng SME cần grant rõ. Chuyển nội dung
  giữa hai SME cần thao tác export/import/copy có quyền nguồn và đích, provenance,
  human confirmation; không link ngầm hoặc đồng bộ tự động bởi AI.
- Retrieval lọc quyền trước khi chọn chunks, không retrieve toàn bộ rồi nhờ LLM
  bỏ phần trái quyền. Context compiler phải kiểm lại mọi input reference.
- Context và cache identity chứa tenant/brand/Brain/actor theo scope thực tế,
  version và permission epoch nếu cần; không cache cross-tenant để giảm chi phí.
- Run/session/learning proposal giữ workspace/Brain/source pins đã admit. Chuyển
  doanh nghiệp trên UI không chuyển run, sửa lịch sử hoặc cho nguồn A vào B.
- Backend xác minh membership và parent scope, không tin workspace ID từ model,
  prompt, browser, webhook hoặc chỉ tên doanh nghiệp trong câu chat.
- Logs, audit, usage, search, graph, download/export và backup/restore phải được
  đưa vào isolation corpus; không chỉ kiểm màn hình chat.

## 4. Tài nguyên theo doanh nghiệp

- Scope riêng cho files/storage, token/model usage, job concurrency, schedule
  count, connection count/rate, tool budget và ngân sách chiến dịch.
- Shared infrastructure có thể dùng chung process/DB/model; không có nghĩa chia
  sẻ state/context/credential. Không bắt buộc DB hoặc model vật lý riêng cho mỗi SME.
- Reservation/quota do server xử lý atomic; job mang tenant/connection pins,
  quyền được kiểm lại trước external/model call và trước phát hành kết quả.
- Cân bằng hàng đợi để SME lớn không làm SME nhỏ mất lượt; đặt các ngưỡng sau
  baseline workload, không tự hứa SLA hoặc giới hạn số lượng chưa được đo.
- Hết quota thì báo lý do/đề xuất rõ, không mượn credential/ngân sách của SME khác.
  Usage measured/estimated/unknown tách biệt; không giả usage thành hóa đơn/quota provider.
- Chuyển workspace hủy/discard response đang hiển thị sai scope, đóng stream cũ
  phù hợp và tải state đúng doanh nghiệp. Không tự hủy mọi job của SME cũ: job
  tiếp tục trong scope cũ nếu còn quyền và chưa có lệnh cancel.

## 5. Quyền mặc định và phê duyệt

Giữ role hiện có, không tự tạo platform-admin bypass. Dưới đây là đích chính
sách để triển khai và test, không phải quyền đã được backend đồng bộ toàn bộ.

| Vai trò | Quyền mặc định dự kiến | Không mặc nhiên có |
|---|---|---|
| owner | Quản trị workspace/team/quota và connections; cấp brand grants | Đọc private memory người khác hoặc hoạt động ở SME khác |
| admin | Quản lý được giao trong SME, dữ liệu chung theo grant | Quyền chi tiền, xem secret rõ hoặc đọc private Brain |
| operator | Thực hiện task/soạn draft theo brand/connection grant | Sửa app secret, tự cấp quyền, launch Ads không approval |
| analyst | Đọc/phân tích nguồn và tạo đề xuất khi được grant | External write hoặc đổi ngân sách |
| viewer | Đọc phần được cấp | Sửa dữ liệu/quyền, gọi công cụ gây side effect |

- Scope connection có người quản lý và người sử dụng; không cần chia secret
  cho nhân viên. Secret chỉ có nhập/thay thế, trạng thái che và audit; không đọc lại rõ.
- Owner là approver mặc định. Delegated approver chỉ có explicit grant theo loại
  hành động/brand/account/budget, expiry; admin không tự thành finance approver.
- Duyệt kế hoạch cho phép chuẩn bị công việc nội bộ, không blanket approval mọi
  external action. Action approval gắn version nội dung/kế hoạch, resource/account,
  connection version, money/currency và thời hạn; chỉnh payload cần duyệt lại.
- Global emergency kill switch vẫn ở platform; bật tenant không vượt gate này.
  Platform hỗ trợ bảo trì không có quyền mặc định đọc private data/secret qua UI.

## 6. Settings và quy tắc nghiên cứu connector

Mỗi lượt S3/S4 hoặc connector mới bắt buộc có một hồ sơ provider cập nhật tại
thời điểm triển khai (không lấy mô tả hôm nay làm auth spec đã xác minh):

1. Đọc tài liệu chính thức; ghi link, ngày kiểm tra, API version hỗ trợ và các
   điều kiện developer app/review/business verification/test mode. Không bypass.
2. Lập ma trận managed app/BYO/token-based đúng khả năng provider; ghi scopes,
   callback/webhook, expiry/refresh/revoke, rate limits và account/destination IDs.
3. Thiết kế UI theo thuật ngữ thật của provider, required/optional rõ, help links
   và bước mở portal/tạo app/copy credential. Không gọi mọi secret là access token.
4. Dùng auth flow an toàn hiện hành; server tạo state và kiểm callback, tenant và
   version. Kiểm CSRF/replay/redirect/SSRF, secret redaction và log/error sanitization.
5. Tests local không network trước; live check chỉ với account/destination được
   owner cấp. App review pending hiển thị pending, không giả trạng thái connected.

Luồng Settings đích:

```text
Chọn doanh nghiệp → chọn provider → kết nối qua PAO / cấu hình nâng cao
 → xác thực hoặc nhập thông tin → kiểm tra → chọn account/Page/bot/advertiser
 → gán nhãn hàng và quyền → lưu → trạng thái kết nối
```

- Telegram hiển thị token input an toàn và hướng dẫn; bot identity xác minh sau
  nhập, đích chat/user là bước riêng. Chưa chạy getMe hoặc gửi tin ở S0.2.
- Facebook/Meta phân biệt Ads/Page và từng quyền đọc/đăng; không đồng nhất một
  Meta Ads token với quyền quản lý mọi chức năng Facebook.
- TikTok chưa có adapter: UI phải ghi chưa triển khai cho đến khi backend/auth
  tests tồn tại. Đọc API Marketing hay Content Posting phù hợp use case, không
  dùng quyền Ads để suy ra quyền đăng video.
- Google/OAuth và provider khác có form/flow riêng. Managed mode không yêu cầu
  SME tạo developer app; BYO advanced cho ID/secret phù hợp nếu provider hỗ trợ.
- Trạng thái tách saved/configured/connected/healthy/accepted; có last check,
  scopes, expiry, lỗi cần xử lý, reconnect/rotate/disconnect và revoke queued jobs.
- Nút “Kiểm tra kết nối” nêu rõ network read-only gì sẽ thực hiện; “Lưu” không
  tự gửi báo cáo/đăng bài/bật Ads. Giữ safety gates và approval nghiệp vụ riêng.

## 7. Threat model và corpus nghiệm thu bắt buộc

| Rủi ro | Kiểm soát và ca kiểm chứng |
|---|---|
| Một user thuộc A và B làm lẫn context | Switch với SSE/request đang bay; run pins giữ A; B không thấy snippets/artifacts A |
| IDOR/cross-tenant references | Thay workspace/brand/Brain/connection/account IDs trên API/job/export; deny trước provider call |
| Cache/search/learning trộn memory | Có cùng từ khóa trong A/B; retrieval/compaction/proposal chỉ trả nguồn được grant; permission revoke invalidates cached output |
| Owner/admin privilege expansion | Admin B không điều khiển A; owner không tự đọc private facts của đồng nghiệp |
| Token/state/webhook bị gắn sai SME | OAuth replay/config-version mismatch; forged webhook; token rotate giữa enqueue/execute; fail-closed |
| Telegram cùng update ID trên hai bot | Identity/dedup/lease/outbox có connection namespace; không đụng bot hoặc nhận nhầm peer |
| Hàng đợi dùng state cũ | Member/brand/connection grant revoke khi pending; recheck và không side effect |
| Budget race/noisy neighbor | Concurrent reservation và worker throughput tests; một SME hết quota không tiêu tài nguyên/quỹ SME khác |
| Crash/backup/log rò dữ liệu | Restore scoped state/pins/keys đúng tenant, không secret logs; kiểm file temp theo ownership |
| Prompt injection từ nguồn/API | Untrusted data không đổi tenant/permission/approval; Gateway kiểm độc lập model |

DB constraints/RLS là lớp cần đánh giá tại S1, không bật bằng docs hoặc tuyên bố
đã secure vì có workspace_id. Cần test connection pooling/session context và
DB-role bypass nếu chọn RLS. Không thay đổi quy tắc private legacy migration.

## 8. Ranh giới triển khai và checkpoint tiếp theo

S0.2 đã ghi quyết định/mapping/quyền/threat model và tiêu chí connector UI, chưa
triển khai code. Checked source là căn cứ reuse, không live health/test hôm nay.
Không claim S0 toàn bộ đạt hoặc tenant isolation đã nghiệm thu.

**Chuyển giao từ S0.2 sang S0.3 (lịch sử):** phục hồi Docker/runtime an toàn nếu còn không chạy,
kiểm live schema/contract/binding/idle, verified backup/restore và source safety
checkpoint trước S1. Không hỏi lại ba lựa chọn đã chốt. Không commit/push toàn
bộ dirty tree, reboot hoặc destructive repair nếu chưa có authority riêng.

Cập nhật sau triển khai11/10: [S0.3 đã đạt local](S03-LOCAL-BASELINE-ACCEPTANCE-2026-10-11.vi.md),
S1.1 cũng [đạt local](S11-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
S1.2 cũng [đạt local](S12-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
S1.3 cũng [đạt local](S13-LOCAL-ACCEPTANCE-2026-10-11.vi.md) trong corpus đã định;
S2.1A inventory/mapping preview [đạt local](S21A-LOCAL-ACCEPTANCE-2026-10-11.vi.md)
theo [ADR-S21A](ADR-S21A-CONNECTION-INVENTORY.vi.md);
S2.1B1 staged persistence/eligibility đạt local theo
[evidence](S21B1-LOCAL-ACCEPTANCE-2026-10-11.vi.md) và [ADR](ADR-S21B1-STAGED-CONNECTION-GRANTS.vi.md);
B2a model execution-denial đạt local theo [evidence](S21B2A-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
B2b explicit model consent/pins đạt local theo [evidence](S21B2B-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
**Snapshot lịch sử13/10: S2.1/S2.2A/B1/B2a/B2b native coverage đạt local; khi đó tiếp theo S2.2B3 quota Settings/integration**.
[S22B2A evidence](S22B2A-LOCAL-ACCEPTANCE-2026-10-13.vi.md); full S2 chưa đạt.
[B2b metadata backend đạt local](S22B2B-METADATA-QUOTA-2026-10-13.vi.md),0056/live334;
Credential payload/URL logging đạt local theo
[evidence](S22B2B-CREDENTIAL-PAYLOAD-2026-10-13.vi.md),356affected/browser3;
Local discovery/selection quota đạt425affected/browser4 theo
[evidence](S22B2B-LOCAL-DISCOVERY-2026-10-13.vi.md); legacy unaccounted inference
đạt local theo [evidence](S22B2B-LEGACY-ACCOUNTING-2026-10-13.vi.md),0056/live334,
472pass+focused38/38/Knowledge3/browser4/build21/restore124business.
Shared admission/Memory embedding đạtlocal0057/live334/189backend/browser2+1 theo
[evidence](S22B2B-MEMORY-EMBEDDINGS-2026-10-13.vi.md); Knowledge index/query nay đạt
local0058/live334/565integrated B2b/browser2+1 theo
[evidence](S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md). B2b native coverage đóng local.
[S22B1 evidence](S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md);
Tại snapshot13/10, quota UI/full S2/global host fairness/production chưa đạt. ADR không tự dispatch
checkpoint hoặc coi kết quả local là SaaS/production đã nghiệm thu.
