# P0 — Local foundation acceptance
Ngày05/10/2026. Target F:\PAO-ACOS.

**P0 LOCAL đạt theo các gate/lát cắt dưới đây; P0 PRODUCTION chưa đạt.**
Đây không phải hoàn tất mọi feature PAO hoặc mọi lần di chuyển module.
Người dùng chọn không reboot host, chưa có VM/VPS thử riêng.
P1 chưa triển khai, M4 vẫn chưa được phép.

| Nhóm | Trạng thái/evidence |
| --- | --- |
| P0.1 | Inventory/module/route/script ownership map đã đạt tĩnh |
| P0.2 | Reconciliation + app factory/shims/full contract đạt local |
| P0.3 | Warehouse/report/Telegram helper + Task values + run state/tool audit + frontend platform feature boundaries đạt theo lát cắt; transaction/job ownership giữ nguyên |
| P0.4 | Evidence-based implemented/configured/healthy/accepted và shadow không active; UI không suy health từ token |
| P0.5 local | Worker/bridge lease, request correlation log, local CI runner, isolated build, bounded supervisor restart drill và source+DB manifest backup đạt |
| P0.5 production | Chưa có môi trường reboot; chưa service installation/24-7/cold restore/real bridge/remote CI acceptance |

Kết quả mới cuối chuỗi: **366 backend passed không skip**, real ARQ recovery,
runtime8/8, browser12routes mock, TypeScript và production build18pages đạt.
Full OpenAPI baseline/source/savedUTF8/live tương thích,64ORMtables/65DBtables/
revision0024 giữ nguyên; artifact M2 cũ3/3 đọc quaHTTP,0job mới trong smoke.
Xem [P0.5 acceptance](P05-LOCAL-OPERATIONS-2026-10-05.vi.md) cho startup failures
đã ghi thật, retry có giới hạn và drill rerun đạt, không chỉ successful PID.

Báo cáo mới:
- [P0.3B.2 Task values](P03B2-TASK-VALUES-2026-10-05.vi.md)
- [P0.3C state/audit](P03C-STATE-AUDIT-2026-10-05.vi.md)
- [P0.4 catalog evidence](P04-CAPABILITY-EVIDENCE-2026-10-05.vi.md)
- [P0.5 operations/CI/backup](P05-LOCAL-OPERATIONS-2026-10-05.vi.md)

## Nợ kỹ thuật / giới hạn không được đánh dấu xong

Task create completed progress27 vẫn27 (đã tái hiện); ORM defaulttodo lệch CHECK
(static); potential lock order cần stress test. Chưa fix trong refactor thuần.
Task DB/graph/Attempts và schema/models, whole Telegram bridge/module, whole
runtime/gateway/frontend domains chưa tách hết. Đây là refactor theo lát cắt;
gate P1 hiện hành không buộc mọi lần move P0.3 nhưng business execution acceptance
không được suy từ unit tests hoặc folder mới. Task Attempt chưa tự enqueue worker.

CI workflow có trong repo/local runner PASS, chưa remote run. Bridge test mock/
disabled không bằng live Telegram. Worker lease chỉ liveness. Provider accepted
unknown không fabricated. Private encryption/JWT keys phải phục hồi qua quy trình
riêng, không bỏ chúng vào Git/source archive.

## Handoff

Có thể chọn **P1.1: ADR Brain scopes/ACL/legacy mapping** tiếp theo sau xác nhận;
chưa tự tạo Brain tables hoặc bật M4. Nếu ưu tiên xử lý lỗi Task trước P1,
tách checkpoint behavior-fix riêng, thay characterization test minh bạch.
Production reboot/supervisor gate giữ pending cho môi trường được cấp riêng.

Repo hiện có các thay đổi chưa commit; đã backup private source+DB theo manifest,
không tự commit/push sang remote không được xác minh. Rollback source từng patch
review, không reset working tree hay downgrade DB local.
