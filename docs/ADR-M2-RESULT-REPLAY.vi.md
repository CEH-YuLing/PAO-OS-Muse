# ADR — M2 replay kết quả, không replay side effects

Ngày 05/10/2026. Phạm vi PAO local, ba skill được duyệt và business tools chỉ đọc.

## Quyết định

“Replay giữ đúng skill version” trong M2 là đọc lại kết quả đã lưu cùng contract,
input, tool outputs, nguồn và version/hash tại thời điểm thực thi. Không đọc
lại business records hiện tại để thay lịch sử. Không tải/chạy backend cũ.

Run command hoàn tất lưu pao-skill-result-v1 trong execution_plan, cùng transaction
với response/result. API chỉ phục vụ sau khi run completed. TaskAttempt skill
completed lưu artifact riêng ở cột nullable skill_artifact (0024), cùng transaction
với result/evidence/state. Không backfill artifact cho lịch sử trước triển khai:
không đủ bằng chứng để tái tạo snapshot quá khứ. Run/attempt dở, failed/cancelled,
artifact thiếu/hỏng trả 409; không tạo job mới.

Reader v1 không gọi registry hiện tại, LLM, tool, evaluator hiện hành hay business
service. Giữ reader định dạng v1 khi bổ sung v2; thay format/evaluator cần contract
và tests mới. Reader kiểm hash toàn artifact, hash snapshot, record/workspace,
shape result và nguồn command là subset của nguồn tool đã đọc. Có thể đọc kết quả
cũ dù code digest/registry thay đổi. Execute/complete vẫn dùng version guard.

Không có API sửa artifact terminal. Người có quyền sửa PostgreSQL vẫn có thể
viết lại payload và hash: hash không phải chữ ký, không chống DBA. RBAC/session
owner bảo vệ run; membership/task scope bảo vệ attempt. Dữ liệu archive là dữ liệu
nghiệp vụ riêng, không copy vào Git; xóa theo lifecycle record mẹ, backup private.

## Budget và phạm vi

Ba skill hiện tại khóa execution_mode=deterministic_read_only. Không có planner/
stream model trong skill path; token sinh là 0, dưới trần manifest. Mode LLM không
được chấp nhận. Trần timeout đã pin, hai tools, response 32000 ký tự, artifact
256000 bytes. Không giả rằng đã có token metering cho skill LLM chưa tồn tại.

Business_verified luôn false trên replay: result kỹ thuật hoặc input/evidence
do người dùng ghi không phải kiểm chứng doanh thu/nhân quả ngoài PAO. Attribution
preview là lời gọi rõ ràng riêng; không tự bổ sung tool thứ ba vào command.

## Ngoài M2 local

Resume công việc dở bằng executable cũ, archive toàn dependency/native runtime,
rolling upgrades, HA/mất Redis server/load và SLA production là vận hành nâng cao,
không được khẳng định đã đạt. Dữ liệu account thật và đối soát metric thuộc M3.
Skill LLM mới cần gate token metering riêng; không được đổi mode để bỏ gate.

Rollback 0024 xóa cột archive attempt mới, nhưng giữ result/evidence/snapshot
và run artifact. Vì có mất archive, chỉ rollback local sau backup/restore/review;
không downgrade local tự động. Roundtrip chỉ chạy trên pao_test.
