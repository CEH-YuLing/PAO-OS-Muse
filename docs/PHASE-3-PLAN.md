# Phase 3 — Memory

Phạm vi: bộ nhớ dài hạn local có nguồn gốc, quản lý thủ công và truy xuất qua nhiều hội thoại; không mở Phase 4/Ads/tools.

## Quyết định kiến trúc

- Memory riêng theo **workspace + user + brand**. Brand nằm trong workspace, session có brand_id tùy chọn và bất biến; session cũ giữ null. Không truy xuất brand khác hoặc tự suy brand từ model. Chưa chia sẻ memory giữa thành viên.
- PostgreSQL pgvector lưu vector 768 chiều; model embedding local cấu hình qua env, mặc định embeddinggemma. Không gọi cloud. Lưu tên model cùng vector, không so sánh vector khác model. Exact nearest-neighbour phù hợp dữ liệu nhỏ, chưa cần ANN index.
- Structured memory: key/value, importance, status, source_run, timestamps và version. Chỉ active facts tham gia context. Tạo/sửa/xóa qua API/UI, viewer không ghi; optimistic version tránh ghi đè thay đổi mới.
- Sau run completed, job bền trong DB trích xuất tối đa 3 sự kiện bền vững từ **tin nhắn người dùng hiện tại**, không từ câu trả lời model. Output theo JSON schema/Pydantic; value phải là đoạn nguyên văn trong input. Không lưu mọi message. Trùng nội dung bỏ qua; cùng key khác value tạo pending conflict, không âm thầm thay fact cũ. User có thể xác nhận hoặc loại bỏ trên UI.
- Jobs dùng cùng ARQ worker max_jobs=1, timeout/retry hữu hạn và phục hồi sau restart. Không chặn trạng thái hoàn tất câu trả lời để chờ extraction. Không backfill các hội thoại cũ tự động.
- Retrieval trước gọi model: scope SQL bắt buộc, semantic + lexical/entity + recency + importance, số lượng và context có giới hạn. Khi embedding lỗi, báo degraded và dùng lexical scoped; chat vẫn hoạt động. Memory là dữ liệu tham khảo không đáng tin cậy như instruction, không được ghi đè system prompt.
- Xóa memory không xóa lịch sử chat nguồn; giữ tombstone nội dung rỗng/fingerprint để retry cùng nguồn không tái tạo memory đã xóa. Xóa/sửa không thể rút lại context của một run đã bắt đầu; áp dụng các run tiếp theo.

## Files / API / migrations

Thêm memory service/router/schema/job tests, model Brand/Memory/MemoryJob và migration 0002. Mở rộng gateway embed/structured extraction, runtime retrieval/job creation và contracts. Frontend thêm brand selection khi tạo session và MemoryPanel xem/tìm/tạo/sửa/xác nhận/xóa; job status rõ ràng.

API: /v1/brands (GET/POST), /v1/memory (GET/POST), /v1/memory/search (POST), /v1/memory/{id} (PATCH/DELETE), /v1/memory/status (GET theo session). SessionCreate thêm brand_id; không thay brand của session cũ.

## Trình tự và kiểm chứng

1. Schema/service/API, unit/integration tests với pgvector thật và provider giả lập.
2. UI/contract, build, browser tests (CRUD/conflict/isolation/reload) và regression Phase 2.
3. Sao lưu DB trước migration local; upgrade và đối chiếu số liệu. Downgrade/roundtrip chỉ pao_test.
4. Kéo model embedding, kiểm chứng local thật: fact từ hội thoại A → extraction/job → hội thoại B cùng scope truy xuất đúng; scope khác không thấy. Không dùng lịch sử cá nhân làm dữ liệu thử.

Rủi ro máy 16GB/CPU: đổi giữa embedding và chat model gây độ trễ; giữ một model loaded, tối đa một job. Không nâng driver/GPU. Model extraction có thể bỏ sót hoặc tạo key không nhất quán; UI cho sửa/xác nhận, không tuyên bố hiểu mọi business fact. Không thêm audit/policy Ads dưới tên Memory.
