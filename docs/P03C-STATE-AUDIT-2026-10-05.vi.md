# P0.3C — Conversation/run state và tool audit boundaries
Ngày 05/10/2026; F:\PAO-ACOS. PASS local, không đổi nghiệp vụ.

TERMINAL/emit/finish chuyển sang modules/conversations/state.py; runtime giữ
aliases, core_api dùng state trực tiếp thay import worker orchestration.
audit chuyển sang modules/tools/audit.py, tool_gateway giữ alias.
AST thân helpers và code còn lại bằng nhau, trừ imports/assignment đã chọn.
Caller vẫn sở hữu row locks/transaction; thứ tự event/agent/message/memory và
permission/approval/tool claims/job names giữ nguyên. Không tách toàn gateway
hay execution pipeline; không thay metadata/models/runtime package.

73 preflight source fingerprints: chỉ runtime/tool_gateway/core_api đổi,
services/init/test mới. Idle9nhóm/schedules0; flags ngoài tắt.
Backup/restore65tables/3archives/revision0024:
.runtime/m2-20261005T143902-ac292eda.dump,286494bytes, private giữ lại.
API/ARQ drain/restart cùng source; Web/Ollama giữ nguyên.

- Backend **353 passed**, không skip,336.89s,pao_test/Redis15, real-clock bật.
- ARQ recovery77.28s/97.78s, mỗi ca một claim.
- Runtime8/8; browser12routes mock.
- Source/savedUTF8/live OpenAPI không đổi; HTTPhealth/ready/Web200.
- 3/3 old M2 artifact replay; counts/revision/hashes giữ nguyên;0jobmới.
- API16752/worker7772 interpreter/UTC-start-time/entrypoint xác minh đúng.
- Binding mới e7d82c0f25bfd3bbd5167d680d6a94e0531504c28654f5805d226f6f492979f1;
  API live/source khớp, worker cùngsource/interpreter, chưaRPCdigest riêng.

Không nới pin/rebind, sửa archives/migrations/frontend, production build,
roundtrip hoặc bật integration/M4. Không commit/push/sửa bản gốc.
Rollback patch riêng restore helpers và imports, idle/backup/restart đồng bộ.

P0.3 backend đạt các lát cắt tasks/business/conversation/runtime/tools; frontend
feature boundary sẽ kiểm cùng catalog P0.4. Chưa phải toàn bộ monolith được tách:
graph/Attempts/schemas/models/bridge và provider execution còn nợ kỹ thuật.
