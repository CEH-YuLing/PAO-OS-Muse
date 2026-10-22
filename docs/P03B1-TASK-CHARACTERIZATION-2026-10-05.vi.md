# P0.3B.1 — Task call-map và characterization

Ngày: 05/10/2026. Repo: F:\PAO-ACOS.
**PASS local P0.3B.1 (khảo sát + tests). Chưa extraction Task; P0/P01 chưa hoàn tất.
M4 chưa triển khai.**

## Phạm vi thực hiện

Chỉ thêm test và tài liệu; không sửa bất kỳ Python file trong pao, migration,
dependency/config, runtime, frontend hoặc generated contract. 69 source
fingerprints trước/sau giữ nguyên. API/worker không dừng hoặc restart.

Bản đồ AST tại [P03B1-TASK-CALLMAP-2026-10-05.json](P03B1-TASK-CALLMAP-2026-10-05.json):
task_api.py **870 dòng, 30 functions (18 endpoints + 12 helpers), 15 schemas**.
Đây là bản đồ static của module, không phải runtime tracing; direct-import scan
không bao gồm import động. app.py đăng ký router qua ROUTER_SPECS string.

## Ranh giới và luồng gọi

| Nhóm | Điểm vào / phụ thuộc | Quyền, transaction, invariant cần giữ |
| --- | --- | --- |
| Projects (3 API) | list/create/update; validate_owner | membership; update khóa row và version; commit tại endpoint |
| Goals (4 API) | create/project/owner; update GOAL_TRANSITIONS | completed cần mọi required Task completed + evidence; version/row lock |
| Tasks (4 API) | list/create/get/update; workspace/parent/run/dependency helpers | membership, workspace FK; update status/AI guard/version; TaskActivity và commit cùng transaction |
| Attempts/replay (4 API) | list/create/update/replay; fingerprint, dependency guard, skills/artifacts | task/attempt lock; request_key + input hash; pin skill; completed attempt → waiting_approval, chưa tự approved |
| Comments/activity (3 API) | task_owned; TaskComment/TaskActivity | quyền đọc/ghi membership, append activity, workspace scope |
| Pure helpers | bounded_json, clean_criteria, attempt_fingerprint | JSON character limit, normalization và canonical SHA; không DB/network |
| Dependency/parent helpers | validate_dependencies/sync_dependencies/validate_parent/ensure_dependencies_completed | workspace, graph cycle, normalized relation + UI JSON cache; HTTPException hiện nằm trong helper |

create_attempt gọi fingerprint → kiểm idempotency trước status guard →
ensure_dependencies_completed → validate_run → validate_input/snapshot →
insert attempt + đổi Task + activity → commit; IntegrityError có rollback/re-read.

update_attempt khóa attempt rồi Task, kiểm version/late result/cancel →
evaluate pinned skill/build artifact nếu có → cập nhật attempt và Task/activity →
commit. attempt_skill_replay chỉ đọc archive, không tự chạy evaluator/tool mới.

Consumers ngoài module:

- app.py compose router (import động).
- Telegram /tasks,/goals đọc ORM trực tiếp, không qua task_api helpers.
- business_tools.read_tasks đọc count theo status/UTC; runtime dùng kết quả brief.
- Shared models.py sở hữu Task/Goal/Project/TaskAttempt/Dependency/Comment/Activity
  cùng metadata; không tạo model registry khác.
- create_attempt hiện tạo record running và pin skill, **không enqueue worker**
  để tự thực hiện Task. Liên kết run_id không đồng nghĩa auto execution;
  không tìm thấy consumer TaskAttempt/TaskDependency khác trong pao ngoài models/task_api
  qua static scan. Đây chưa phải acceptance Task agent tự chạy end-to-end.

## Coverage hiện tại và mới

6 tests ở test_tasks.py hiện kiểm workspace/filter/viewer, version/evidence/
comment/activity, graph cycle, Goal 3 Task phụ thuộc, attempt idempotency/cancel/
parent guard và AI không bypass state machine.

test_skills.py và suite artifact M2 kiểm skill pin/input/output/replay.
Không coi test giả lập là live provider acceptance.

Thêm **9 tests** ở test_task_domain_characterization.py:

1. Fingerprint canonical: thứ tự key, Unicode, run identity, list order.
2. bounded_json dùng số ký tự JSON serialize, không byte; boundary và identity.
3. Criteria trim/drop blank/max500/None.
4. Hai transition matrices giữ nguyên.
5. Dependency rỗng/self/missing-workspace guard.
6. Dependency cycle bắc cầu và chain hợp lệ.
7. Parent rỗng/self/missing/cycle.
8. Execution dependency/parent completed và workspace guard.
9. HTTP + pao_test tái hiện create completed giữ progress nhập vào.

Mock helper tests không chứng minh concurrency/DB FK; integration tests hiện có
dùng PostgreSQL/Redis thật cô lập. Chưa bổ sung concurrency stress test graph/attempt.

## Lỗi/rủi ro tìm thấy — chưa sửa

- **Đã tái hiện:** POST Task completed với progress=27 trả completed,
  completed_at có giá trị nhưng progress vẫn 27. create_task dùng nhánh status
  == 'done' không hợp TaskStatus; PATCH sang completed thì normalize 100.
  Test mới ghi nhận hiện trạng, không coi đây là yêu cầu sản phẩm: cập nhật test
  khi thực hiện fix riêng.
- **Static, chưa tái hiện:** Task ORM default='todo' không khớp CHECK status mới.
  API truyền status nên đường API hiện tránh default này; direct ORM creation có rủi ro.
- **Cần kiểm concurrency:** update_task (Task → running attempts) và
  update_attempt (Attempt → Task) có lock order khác nhau; chưa chứng minh deadlock
  bằng test đồng thời. Không sửa lock order trong extraction thuần.
- Graph traversal ở validate_dependencies giới hạn 500 nodes, parent 100;
  cycle/incomplete guards ở create/update/attempt có logic khác nhau.
  Không gộp/chuẩn hóa chúng khi di chuyển helper mà chưa thêm characterization.
- Tasks, Goals và Attempts có state machine riêng; attempt completed chưa phải
  Task completed. Không bỏ bước approval/evidence để tối giản kiến trúc.

## Kiểm chứng mới trong checkpoint

| Gate | Kết quả |
| --- | --- |
| Full backend | **345 passed**, không skip, 395.01s; pao_test/Redis DB15; PAO_ARQ_WALL_CLOCK_TESTS=1 |
| Characterization rerun | **9 passed**, 0.85s sau dọn unused import trong test; không đổi logic |
| Real ARQ recovery | between 72.47s; during 94.95s; mỗi ca một tool claim |
| Runtime/SSE | **8/8 PASS** |
| Source fingerprint | 69/69 Python source files không đổi |
| Full OpenAPI | Baseline/source/saved UTF-8/live bằng nhau |
| API/Web health/ready | HTTP 200 |
| Live M2 replay | **3/3 artifacts cũ** qua HTTP; hash/content giữ nguyên |
| DB smoke | Counts/revision/artifacts không đổi; revision0024; 0 job mới |

Binding vẫn:
395487f16b9623ceef7244992c10a92f33c06907902ae547b868a77680253a6e.

Task source SHA256:
9bd12b7a5154bb8eed0c74bfd031429887dd60f8b3888ce510dda6429e9fcf82.

Preflight: 9 nhóm active/pending bằng0; sync/report schedules enabled0; flags
Meta/write/Google Ads/Telegram/Temporal/autopilot false. Không chạy backup/restore
mới vì không rollout code/state local, không restart API/worker. Test runner chỉ
upgrade/check pao_test; không --roundtrip. Không chạy browser acceptance hoặc
production frontend build trong checkpoint này, không dùng số cũ làm kết quả mới.

Không gửi tin/Ads/email thật, không bật lịch/connector/M4 hoặc deploy công khai.
Bản gốc Apex sạch; không sửa F:\Apex\apex/F:\Javis OS, không commit/push.

## Lát cắt đề xuất tiếp theo

**P0.3B.2: tách 3 pure helpers bounded_json/clean_criteria/attempt_fingerprint**
sang modules/tasks/values.py; giữ aliases task_api, không di chuyển schemas,
models, endpoints, transaction hay thay state machine.

Gate: idle/backup trước rollout source binding, AST body unchanged, full
OpenAPI/regression/replay; restart API/ARQ đồng bộ vì source digest đổi.
Nếu chọn sửa lỗi progress/default, làm checkpoint riêng và sửa characterization
expectation rõ ràng; không âm thầm fix trong extraction. Trước tách DB/graph/
attempt service phải bổ sung kiểm thử concurrency và transaction ownership.

Rollback checkpoint hiện tại chỉ cần review bỏ test/docs mới nếu không cần;
không có code nghiệp vụ/DB migration cần rollback, không reset working tree.
