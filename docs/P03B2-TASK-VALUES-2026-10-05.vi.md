# P0.3B.2 — Pure Task helper extraction
Ngày 05/10/2026; F:\PAO-ACOS. PASS local.

bounded_json/clean_criteria/attempt_fingerprint chuyển sang modules/tasks/values.py,
task_api giữ alias/type identity cho schemas/tests. Thân hàm AST và phần còn
lại của task_api bằng trước, OpenAPI canonical hash không đổi. 69 source
fingerprints: chỉ task_api đổi, service/init/test mới. Không sửa progress/default/
state machine, schemas/transaction/DB/job ownership hay frontend.

Idle 9 nhóm jobs và enabled schedules đều0; flags bên ngoài false.
Backup/restore 65tables/3archives/revision0024 đạt; giữ private backup:
.runtime/m2-20261005T142825-7fc289ef.dump (286494bytes).
API/ARQ dừng sau gate, restart cùng source; web/Ollama giữ nguyên.

- Backend **347 passed**, không skip, 364.23s; pao_test/Redis15, real-clock bật.
- ARQ recovery between73.28s/during96.69s, mỗi ca một tool claim.
- Runtime/SSE8/8; browser12routes API mock.
- Full baseline/source/savedUTF8/live OpenAPI bằng nhau; HTTP health/ready/Web200.
- Artifact M2 cũ3/3 quaHTTP; smoke counts/revision/hashes không đổi;0job mới.
- Process API23892/worker7976: interpreter/UTC-start-time/entrypoint đúng.
- Binding trước395487f16b9623ceef7244992c10a92f33c06907902ae547b868a77680253a6e;
  sau99d931091986b16b461a3d2fc6d24f12e3345a3a16d0d10250b570454332f5bd.
  API live khớp fresh source; worker cùng source/interpreter startup, chưaRPCdigest.

Không nới guard/rebind job/sửa archive/migration, production build hoặc roundtrip.
Không bật integration/M4, không sửa bản gốc hay commit/push.
Rollback patch riêng đưa helpers về TaskAPI, kiểm idle/backup/restart cùng source.
P0.3B.2 đạt là ranh giới pure helper, chưa tách DB/graph/Attempt use cases.
