# ADR-S5 — Hồ sơ và kế hoạch nghiệp vụ có phiên bản

16/10/2026. Target `F:\PAO-ACOS`. Toàn S5.1–S5.6 đã local_accepted0070/live382;
không phải nghiệm thu production hoặc quyền mở hành động bên ngoài.

Cập nhật mới nhất0070/382: đã nối native job adapter/worker, ghim phiên bản,
duyệt nội dung, ledger/hành động mô phỏng, stop và báo cáo nội bộ theo lịch P6.
Các đoạn0066–0068 dưới đây là lịch sử thiết kế. Trạng thái nghiệm thu hiện tại
do [sổ triển khai S5](S5-COMPLETION-REGISTER.vi.md) quản lý: hồi quy2224/2224,
primary0070/live382 đã đạt. Không diễn giải các câu “chưa có”
của checkpoint cũ thành yêu cầu dựng lại adapter hoặc runner.

Cập nhật0068: routing config phiên bản/hierarchy/preflight đã triển khai tại
[S5.3](S53-ROUTING-PREFLIGHT-2026-10-16.vi.md). Preview không phải durable job
pin hoặc inference authority; chưa có adapter/worker S5.3. Các mục0066/0067
bên dưới là diễn tiến lịch sử, không dispatch làm lại review/materialization.

## Mapping và phạm vi hiện có

Các bullet bên dưới mô tả checkpoint đầu0066; phần cập nhật0067 ở mục quyền ghi
review/materialization đã được bổ sung sau đó. Không triển khai lại các bước đó.

- Workspace là SME; Brand hiện có là nhãn hàng. Không thêm tenant engine.
- `business_profiles` là head theo workspace/brand; `business_profile_versions`
  là các snapshot bất biến, có actor/request/revision/hash. Dữ liệu chưa biết
  giữ null hoặc missing_fields, không suy thành KPI/budget bằng 0.
- `monthly_plans` và `monthly_plan_versions` là bản nháp nghiệp vụ, không thay
  Project/Goal/Task hoặc Studio/Temporal/ARQ. Version ghim chính xác profile
  version; chỉnh profile không đổi kế hoạch/lịch sử cũ mà đánh dấu stale.
- S5.2 chỉ có authoring/version/DAG/due-date foundation, chưa approval invalidation,
  dispatch/materialization hoặc phát hành kế hoạch nghiệp vụ. Không được gọi nó
  là toàn S5.2 hoàn tất.
- Budget trong profile là số dự kiến Decimal, không phải ledger/cap khả dụng,
  reservation, spend thực tế hoặc quyền chi tiền S5.4.
- Specialist trong deliverable là loại công việc dự kiến, chưa gán hãng/model,
  connection, Brain hoặc quyền công cụ S5.3.

## Quyền và kiểm tra dữ liệu

Cập nhật0067: owner review là quyết định một lần theo plan version/hash, hạn1–720h,
self-review/missing-data confirmation. Role admin không tự thành approver. Profile/
plan edit, expiry hoặc người duyệt mất quyền làm quyết định cũ không còn hiệu lực.
Materialize sau review tạo đúng một native Project/Goal/Task set trong một transaction;
Task vẫn draft/unassigned, không Run/Attempt/chi tiền. Binding/audit DB immutable;
native task/goal mutations và P6 admission không sửa các task/goal đã thuộc S5.
Guard kiểm sự tồn tại bảng để source candidate không làm hỏng startup trên0065;
khi bảng có pins, tắt flag không bỏ quyền sở hữu. Đây chưa content/action approval
hoặc job executor, không tháo guard để biến draft thành công việc đã thực thi.

- Authoring hiện owner/admin trong đúng SME; chưa cấp quyền nhân viên qua profile.
  Đây là dữ liệu chung của người quản lý, không đọc/copy private Brain/memory.
- Khóa Workspace trước, kiểm lại User.active/Member hiện tại và parent Brand.
  CAS revision + request key + fingerprint chặn lưu trùng/xung đột; retry cũ sau
  khi có revision mới bị chặn để không hiển thị head cũ như dữ liệu hiện tại.
- DB bảo vệ scope/identity/version append-only, head FK deferred trỏ đúng
  snapshot; plan source phải thuộc profile/SME của chính plan. Không xóa lịch sử.
- Typed input đóng; body <=64KiB, UTF-8/control/date/DAG/decimal/timezone checks;
  errors không phản chiếu body, responses no-store. Text là dữ liệu chưa tin cậy,
  không cấp quyền hoặc tự trở thành chỉ dẫn hệ thống; không tuyên bố có DLP.
- Chưa cho import URL/file/private sources vào profile. Không model/provider call.
- `BUSINESS_PLANNING_ENABLED=false` mặc định và trong `.env.example`. Chỉ bật
  process test trên API/database riêng; chưa sửa .env hoặc enable primary.

## Những phần bắt buộc tiếp theo của S5

1. S5.2: phê duyệt đúng version, liên kết Project/Goal/Task/Artifact hiện có,
   chỉnh plan vô hiệu approval đúng phạm vi, giữ immutable execution pins.
2. S5.3: SME→brand→agent→step→job routing, model/connection grants và Brain ACL,
   capability/privacy/quota/fallback guards; adapter specialist thật qua shared
   admission/Run/Studio/Gateway, không tháo fixed Echo guards của P6.
3. S5.4: money ledger planned/reserved/spent/released, Decimal/minor units theo
   currency/account/campaign; race/headroom/data age/unknown guards.
4. S5.5: owner/default approver hoặc grant được duyệt rõ; plan/content/external
   approvals riêng; worker recheck, emergency stop và unknown reconciliation.
5. S5.6: dùng schedule ownership hiện có cho report giờ/ngày, nguồn/time window/
   metric pins, missing data và proposal. Không tạo scheduler thứ hai.
6. Gate tích hợp: hai SME, hai model theo step, source→plan→task→draft→review→
   simulated action→report, kill/restart/revoke/budget/restore, evaluation model
   local thật. Ảnh/video/posting/campaign creation là adapter/gate riêng.

Chưa nối execution từ các bảng authoring; không đánh dấu S5 hoàn tất khi thiếu
các mục này. S6/real provider/production vẫn là gate riêng, không hạ tiêu chí.
