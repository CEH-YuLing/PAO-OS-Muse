# ADR P4: Studio định nghĩa, không phải nền tảng chạy code

## Phạm vi

Studio đặt trong `pao/modules/studio`, dùng PostgreSQL và permission service hiện
có. Không tạo microservice, registry file có thể sửa, worker workflow mới, hoặc
quyền gửi email/Ads. Workflow runner thuộc P6; M4 vẫn chưa được triển khai.

## Định nghĩa và quyền

- `studio_definitions` là identity theo workspace/kind/slug, có revision và con
  trỏ published version. `studio_versions` giữ payload/hash bất biến; trigger
  PostgreSQL chặn sửa payload hoặc xóa. `studio_events` chỉ được thêm.
- API dùng `/v1/studio/definitions?kind=agents|skills|workflows`, thay vì ba bộ
  CRUD trùng nhau như đề xuất ban đầu. Có bootstrap, clone, versions, fixture,
  validate/review/publish/rollback, archive, import dry-run và export.
- Operator chỉ sửa định nghĩa của mình; owner/admin có thể review/publish.
  Tự review phải xác nhận rõ, lưu audit; không được mô tả là review hai người.
  Skill/workflow phải có fixture schema đạt trước review.
- Archive ngăn lựa chọn mới nhưng không xóa version, pins hay lịch sử. Không có
  endpoint hard delete. Rollback chỉ tới version đã từng review.
- M2 có 5 agent và 3 skill file bất biến. Bootstrap khóa workspace và import
  mirror idempotent, hash drift bị từ chối. M2 vẫn chạy bằng registry file cũ.
  Seed không được sửa/publish lại; clone tạo draft mới, không kế thừa approval.

## Hợp đồng và giới hạn

Schema chỉ hỗ trợ object đóng, string/array bounded, integer/number/boolean,
enum và bounds. Không `$ref`, remote schema, regex hoặc arbitrary code.
Import chỉ data JSON; không nhận API key, shell, endpoint hoặc env fields.
Kiểm tra mẫu secret/injection là lớp lint bổ sung, không phải bảo đảm nhận diện
mọi secret trong văn bản tự do; người dùng không được dán credentials vào prompt.

Skill mới chỉ có mode `llm_text`: một generation, không planner, không memory,
không tools, không lịch sử hội thoại đưa vào model. Tool allowlist khai báo chỉ
là upper bound cho tương lai, chưa có thực thi. Input/output là JSON object.
Exit criteria hiện hỗ trợ `non_empty:field` và `equals_input:field`; điều kiện
khác bị từ chối, không giả vờ đánh giá thành công bằng model.

Lệnh `/slug {JSON}` hoặc `/skill slug {JSON}` chọn published version trước LLM;
input thiếu/sai bị từ chối, không suy đoán công cụ/argument. Semantic matching
chỉ shadow, không chạy và chưa mở canary.

Run pin skill/agent ID, payload và content hash trong `runs.studio_snapshot`;
engine pin giữ ngân sách nhỏ hơn policy session, max_calls=1 và reported usage
bắt buộc. P3 ledger source `studio_skill` ghi một attempt thực; usage unknown
không được coi là 0. Deadline và cancellation đóng generation đang chạy.
Model preference phải trùng engine session; không tự chuyển cloud/provider.
Brain scope phải trùng session và qua quyền Brain hiện hành.

Output được buffer và kiểm tra schema/exit criteria trước response delta. Đây
là draft do LLM tạo, không phải evidence hoặc approval. Không ghi thành memory.

## Workflow

DAG tối đa 12 bước, tham chiếu published skill versions. Kiểm tra cycle, missing
dependency/agent, schema và data bindings. Input bắt buộc có nguồn chắc chắn;
nguồn step phải nằm trong depends_on. Không endpoint execute workflow. Tại P6
runner phải ánh xạ vào Task/Attempt/Temporal và thực hiện lại các gate quyền.

## Giao diện và nghiệm thu

Trang Skills giữ catalog/preview/replay M2, thêm Studio với editor JSON,
templates, fixture schema-only, versions/hash, review/publish/rollback, clone,
archive và import/export. Fixture schema-only không gọi model và không xác nhận
chất lượng nội dung. UI workflow không được hiển thị là đã thực thi.

Nghiệm thu local phải gồm full regression, runtime/SSE, production build,
browser real API/DB/ARQ với model giả lập và restore hash, migration up/down/up,
live old M2 replay, một thử nghiệm LLM local bằng dữ liệu tổng hợp. Production
reboot/VPS, semantic canary và connector thực không nằm trong nghiệm thu P4.
