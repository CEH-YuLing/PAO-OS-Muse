# Phase 3 — Memory: kết quả nghiệm thu

Hoàn thiện và kiểm tra lại ngày 13/09/2026. Phạm vi theo mục 129 của master specification: PAO nhớ một business fact từ hội thoại trước và sử dụng đúng khi cần. Không mở Phase 4 hoặc hệ thống Ads.

## Đối chiếu lộ trình

| Hạng mục Phase 3 | Kết quả |
|---|---|
| pgvector | Migration 0002, vector 768 chiều, model stamp, truy vấn cosine trong đúng scope |
| Memory extraction | Job bền sau run completed; JSON schema/Pydantic; tối đa 3 fact nguyên văn, importance >=3; dedup và pending conflict |
| Memory retrieval | Semantic + lexical + recency + importance; top-k/context giới hạn; fallback khi embedding lỗi hoặc treo |
| Structured memory | SQL facts có key/value, nguồn run, trạng thái, version; brand/session FK; phân quyền theo workspace/user/brand |
| Memory UI | Thêm/sửa/tìm/xóa, duyệt mâu thuẫn, bật/tắt theo hội thoại, chọn thương hiệu khi tạo hội thoại, trạng thái extraction |

Chief sử dụng Memory như một dịch vụ. Node Memory không được nhận là agent độc lập đang thực thi. Session cũ có brand null, không tự backfill nội dung hội thoại cũ. Model/gateway giữ local CPU, không cần cloud.

## Bằng chứng kiểm thử

- **27 backend tests đạt** với PostgreSQL/pgvector và Redis thật, provider giả lập. Bao gồm phân quyền và scope, concurrent dedup, conflict/version, tombstone chống tái tạo khi retry, extraction không nhận value bịa, opt-out/revocation, retry hữu hạn, stale job recovery, vector không hợp lệ và fallback timeout.
- Migration downgrade/upgrade trên **pao_test** đạt; Alembic check không phát hiện schema drift. Không downgrade database người dùng. Vòng roundtrip đạt 26 tests; bài fallback timeout bổ sung sau đó nằm trong lượt 27 tests cuối.
- **8 Node tests đạt**, frontend production build và kiểm tra TypeScript đạt.
- Browser acceptance Edge headless/reduced motion đạt: lifecycle/reconnect/replay, failure/cancel, chuyển/reload session, logout/token expiry; Memory CRUD, duyệt mâu thuẫn, search, delete HTTP 204, opt-out, xóa draft khi đổi session, tạo session theo brand và không hiển thị memory scope khác. API trong browser test được giả lập; không dùng hội thoại cá nhân.
- **Ollama thật đạt** trong pao_test: hội thoại A cung cấp dữ kiện thương hiệu trà giả lập Sen Mây nhắm Malaysia; extractor lưu 1 fact có vector 768 chiều; hội thoại B trả lời đúng: “Thị trường mục tiêu chính của thương hiệu trà Sen Mây của bạn là Malaysia.” Phạm vi không gắn thương hiệu không truy xuất được fact của brand. Lượt cuối hoàn tất 110,3 giây, exit code 0; đây là thời gian của ca thử, không phải benchmark chung.

Báo cáo model thật: `.runtime/phase-3-local-acceptance.json`. Script tái lập: `scripts/verify_memory_local.py`. Ảnh browser: `.runtime/phase-3-memory-browser.png`, `.runtime/phase-3-browser-final.png`. Các artifact runtime được gitignore.

Trong quá trình thử, embedding chỉ có value “Malaysia” không đủ ngữ cảnh. Đã sửa embedding thành key + value và yêu cầu extractor ưu tiên mệnh đề đầy đủ. Đã sửa nhãn accessibility của textarea/select và giới hạn chiều cao vùng Orb khi bảng Memory mở dài.

## Triển khai local và dữ liệu

Database chính lên **0002**. Đã tạo backup `.runtime/pre-phase-3-20260912.dump` (43.243 byte), kiểm tra archive bằng pg_restore. Đối chiếu trước/sau migration và sau khởi động lại ngày 13/09:

| Dữ liệu | Trước | Sau |
|---|---:|---:|
| Tài khoản | 1 | 1 |
| Hội thoại | 3 | 3 |
| Tin nhắn | 23 | 23 |
| Run | 12 | 12 |

Không đổi mật khẩu/tài khoản. Không nhập dữ liệu acceptance vào database chính. Docker, PostgreSQL, Redis, Ollama, API, worker và web đã được khởi động lại; worker dispatch hoạt động. Giao diện tại http://127.0.0.1:3100/.

## Giới hạn còn lại

CPU i3/16GB có thể chậm hoặc timeout với câu trả lời dài; không nghiệm thu GPU. Extraction có thể bỏ sót hoặc đặt khóa không đồng nhất; UI cho kiểm tra/sửa. Đổi embedding model chưa có reindex hàng loạt. Không có ingestion tài liệu, CRM domain tables, Advertising Memory, planner, tool gateway hay Ads integration trong phase này.

Hướng dẫn dùng, cấu hình, migration và kiểm thử: [MEMORY.md](MEMORY.md). Thiết kế: [PHASE-3-PLAN.md](PHASE-3-PLAN.md). Phase tiếp theo theo lộ trình là **Phase 4 — Agent Runtime**, chưa triển khai trong đợt này.
