# PAO Memory — vận hành Phase 3

Memory phục vụ cá nhân/nhóm nội bộ, tự host. Đây là dịch vụ của Chief of Staff; chưa phải agent độc lập. Phạm vi nghiệm thu theo mục 129 của master spec: nhớ một business fact từ hội thoại trước và sử dụng khi phù hợp.

## Sử dụng

1. Đăng nhập, chọn **Thương hiệu cho hội thoại mới** hoặc để **Không gắn thương hiệu**, rồi tạo hội thoại. Thương hiệu của hội thoại không đổi sau khi tạo.
2. Nói rõ một dữ kiện bền vững. Sau khi câu trả lời hoàn tất, worker trích xuất tối đa 3 dữ kiện. Mở **Bộ nhớ cá nhân** để xem trạng thái xử lý. Chờ trích xuất hoàn tất trước khi kiểm tra ở hội thoại khác.
3. Tạo hội thoại mới cùng tài khoản, workspace và thương hiệu rồi hỏi lại. Phạm vi không gắn thương hiệu được giữ riêng, không tự nhập vào mọi thương hiệu.
4. Trong bảng Memory có thể thêm/sửa/tìm/xóa dữ kiện. Dữ kiện cùng khóa, khác nội dung nằm ở **Chờ duyệt mâu thuẫn**. **Duyệt và dùng** thay bản active cũ thành superseded; không tự chọn bản mới dựa trên phỏng đoán.
5. Bỏ chọn **Dùng và ghi nhớ cho hội thoại này** để dừng truy xuất/trích xuất cho các lần tiếp theo. Xóa một memory không xóa hội thoại gốc và không rút lại context đã gửi tới model trong run đang chạy.

Bộ nhớ riêng theo `workspace_id + user_id + brand_id`; thành viên khác cùng workspace không được đọc/sửa. Viewer chỉ đọc bộ nhớ của chính mình. Thương hiệu là tên dùng chung trong workspace, chưa phải CRM/products/Ads domain model.

## Luồng dữ liệu

- Working context: tối đa 12 message gần nhất, giới hạn 4000 ký tự; giữ prompt hiện tại. Không tự backfill lịch sử cũ vào memory.
- Run completed ghi `memory_jobs` cùng transaction terminal. Dispatcher ARQ quét mỗi 10 giây; cùng worker `max_jobs=1`, tối đa 2 lần extraction, phục hồi lease khi worker mất. Extraction không trì hoãn sự kiện hoàn tất câu trả lời, nhưng có thể làm run sau chờ worker.
- Extractor dùng JSON schema và Pydantic. Chỉ lấy phát biểu trong prompt hiện tại, importance >=3, value phải là đoạn nguyên văn. Model có thể bỏ sót hoặc đặt khóa không nhất quán; kiểm tra/sửa trong UI khi dữ kiện quan trọng.
- SQL facts lưu key/value, importance, active/pending/superseded/deleted, version, timestamps, source_run_id. Sửa thủ công tăng version; source_run_id vẫn trỏ nguồn ban đầu, không khẳng định nội dung đã sửa còn nguyên văn nguồn.
- Embedding bao gồm **khóa + giá trị**, tránh mất quan hệ khi value ngắn như tên quốc gia. Vector 768 chiều có model stamp. Không so sánh với vector mang model khác. Đổi embedding model cần sửa/lưu lại các fact muốn tái tạo embedding; chưa có reindex hàng loạt.
- Retrieval bắt buộc scope SQL trước xếp hạng. Exact cosine top 40, kết hợp lexical của tối đa 1000 fact active, recency và importance. Trả tối đa 5; context fact giới hạn 1500 ký tự. Không chèn memory vào system instruction. Chỉ bổ sung dữ liệu tham khảo trước lịch sử/prompt.
- Query embedding giới hạn tối đa 30 giây để dành thời gian cho câu trả lời. Embedding lỗi dùng lexical trong đúng scope; run vẫn chịu tổng timeout. Fact chưa có embedding hoặc model stamp cũ chỉ được tìm theo từ khóa.
- Xóa làm rỗng key/value/vector, giữ fingerprint làm tombstone chống tạo lại cùng nội dung khi retry. Không có tự khôi phục từ tombstone. Tối đa 1000 bản ghi mỗi scope, kể cả tombstone; list phân trang 100, API write/search giới hạn 20/phút/người dùng.

## Cấu hình và triển khai

```dotenv
MEMORY_ENABLED=true
EMBEDDING_MODEL=embeddinggemma:300m
MEMORY_TIMEOUT_SECONDS=180
MEMORY_TOP_K=5
MEMORY_MIN_SIMILARITY=0.3
```

Cài dependency theo `requirements.lock`, kéo model bằng Ollama đang dùng, sao lưu DB rồi chạy `python -m alembic upgrade head`. Revision `0002` tạo extension vector, ba bảng brands/memories/memory_jobs và hai cột session. Session cũ giữ brand null, memory enabled true; không chuyển dữ liệu hội thoại thành fact khi migration.

Trên máy local hiện tại:

```powershell
.runtime/ollama/ollama.exe pull embeddinggemma:300m
.venv/Scripts/python.exe -m alembic upgrade head
```

Giữ profile CPU và một model loaded như `scripts/start_local.ps1`; không cần cloud hay nâng driver. Việc chuyển model và câu trả lời dài có thể chạm timeout 180 giây trên i3/16GB. Nên hỏi ngắn khi kiểm tra chức năng; không coi thời gian test là benchmark năng lực chung. Có thể chỉnh timeout trong phạm vi cấu hình và restart API/worker nếu nhu cầu thực tế cần thiết.

Để rollback, dừng API/worker, sao lưu mới và xem migration trước khi dùng `downgrade 0001`: thao tác này mất bảng Memory/brands. Không chạy downgrade trên dữ liệu cá nhân để thử; roundtrip chỉ dùng pao_test.

## Kiểm thử

```powershell
.venv/Scripts/python.exe scripts/test_backend.py --roundtrip
npm run test:runtime
npm run build
npm run test:frontend
.venv/Scripts/python.exe scripts/verify_memory_local.py
```

Backend tests dùng pao_test/Redis 15 và xóa dữ liệu test. Local acceptance tạo tài khoản/dữ liệu giả trong pao_test, gọi Ollama thật, lưu báo cáo `.runtime/phase-3-local-acceptance.json`. Không chạy hai lệnh backend test và local acceptance cùng lúc vì test fixture truncate database kiểm thử.

Browser acceptance dùng API giả lập, kiểm tra thao tác UI và hồi quy runtime; không dùng tài khoản hay lịch sử cá nhân. Acceptance model thật và browser mock bổ sung cho nhau, không được gọi browser mock là bằng chứng model thật.

## Giới hạn của phase

Đã có semantic và structured facts, brand boundary và working conversation context. Chưa có ingestion tài liệu/research/meeting, products/customers/suppliers riêng, Advertising Memory, planner/multi-agent, tool approvals hoặc integration Ads. Các phần đó thuộc các phase sau của master spec; không dựng sẵn backend rỗng cho chúng.

Tham chiếu kỹ thuật: [Ollama embed API](https://docs.ollama.com/api/embed), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [pgvector Python/SQLAlchemy](https://github.com/pgvector/pgvector-python), [embeddinggemma](https://ollama.com/library/embeddinggemma).
