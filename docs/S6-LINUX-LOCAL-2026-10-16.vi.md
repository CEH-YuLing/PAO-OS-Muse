# S6 — Chạy thử Linux cô lập và kiểm lại Windows

Ngày 16/10/2026. Target `F:\PAO-ACOS`. **Kiểm thử Linux local đã có kết quả
đạt theo từng stage; không một pipeline end-to-end xanh. Toàn S6 chưa hoàn thành.**

## Phạm vi và sự cô lập

`scripts/run_s6_linux.py` đóng gói source allowlist, bổ sung `.d.mts` theo
helper backup đã có. Không mang `.env`, model, DB thật, runtime, dependency
host hoặc Git history sang runner. Dockerfile lấy Python image local, Node22
và cài dependency lock cùng PostgreSQL client17. Runner dùng UID10001,
drop capabilities, no-new-privileges, giới hạn CPU/RAM.

PostgreSQL17/pgvector, Redis và runner đều riêng, không publish host ports,
không bind-mount host hay Docker socket. Test chỉ dùng `pao_test` và Redis15,
JWT/mật khẩu synthetic; không gọi provider thật. Profile PG native Linux chỉ
cho dump test DB và restore/drop clone UUID đã tự tạo; không mở guard primary.

Trước/sau lượt chạy so snapshot schema/row hash database chính và hash `.env`.
Cleanup kiểm ID/label UUID rồi chỉ xóa container/volume thử nghiệm tự tạo;
giữ source ZIP, image, log và artifact để tra lại. Không prune Docker chung.

Metadata thực đọc từ runner: Python3.12.14, Nodev22.23.3, PostgreSQL
server/client17.11, Redis server7.4.11, FastAPI0.141.1, SQLAlchemy2.0.52, asyncpg0.31.0, ARQ0.28.0,
Temporal Python SDK1.33.0, redis-py5.3.1, cryptography49.0.0, pytest9.1.1.
Binary Temporal native đã chạy, SHA256
`712217694cac9f786a72d4b6c876cd15f3dcf1bf31434d9fed6af25242a327a0`;
receipt `.runtime/s6-linux-3a1b5903bbeb452297dce4d3c5180c39/s6-temporal-binary.json`.

## Các lượt thực tế — không bỏ lịch sử lỗi

1. `fe90c7db05954fb18a85041763228ff2`: dừng trước test vì bản đóng gói đầu
   thiếu frontend declarations. Đổi sang `backup_acos_checkpoint.source_archive`
   để dùng cùng allowlist bổ sung `.d.mts`, không sửa frontend để lách typecheck.
2. `899b5045a824416a847b6d73d7477b97`: Linux đã chạy, nhưng fail. Dừng pytest
   có kiểm soát để lấy lỗi đầu thay vì tiếp tục hàng nghìn lỗi dây chuyền:
   **89 passed,33 failed,1 warning, bị ngắt**, không phải full suite.
   Test Meta managed-app vô tình đọc `.env` host; Linux sạch không có tệp này
   nên trả `meta_app_config_unavailable`. Đã thêm fixture autouse dùng tệp
   synthetic riêng cho mỗi test, vẫn chạy reader/validation thật; các bài
   installer/restart/rotation tiếp tục thay fixture riêng. Không đổi runtime
   security guard, không copy `.env` thật hoặc skip test. Manifest xác nhận
   primary/env không đổi, container thử nghiệm đã dọn. Trường linux_execution
   của manifest lỗi chỉ được đặt true khi toàn gate đạt; runner log/result
   mới là bằng chứng đã thực sự bắt đầu chạy Linux, không gọi lượt lỗi là pass.
3. `6ac9c601678446338cdaf51e41ad20bd`: không đạt, dừng ở nhóm lỗi khoảng32%.
   Source ZIP1202file, SHA256
   `2f8ff05156d49ec0a74e8f005b111e6997d6cfd592adf8d30d3d2551be5afb73`.
   Evidence: `.runtime/s6-linux-6ac9c601678446338cdaf51e41ad20bd/`.
   Đã vượt nhóm lỗi Meta và hai ARQ wall-clock gates. Sau đó xuất hiện4setup
   errors; SIGINT vướng lỗi teardown tmp_path của pytest nên không có tổng kết
   hoàn chỉnh. Tái hiện riêng fixture trong container không mạng xác nhận
   `Cached Temporal binary required; no implicit network download`:6điểm test
   tìm cứng `.exe` Windows trong runtime không được mang vào bản source sạch.
   Không suy số passed chính xác từ phần trăm/dấu chấm hoặc gọi lượt này full.
4. `3a1b5903bbeb452297dce4d3c5180c39`: backend đạt nhưng pipeline FAIL ở
   TypeScript, source1207file,
   SHA256 `8a881828e7446966178a82a0e9bf387af8361576b7ad35311520b8c50e9e9ee4`.
   Helper cache chọn đúng tên/định dạng PE hoặc ELF, không implicit download.
   Bootstrap riêng dùng SDK Temporal1.33.0 đã lock để lấy binary native và
   health-check server test, ghi hash. Lượt mới chạy smoke Temporal/ARQ/restore
   trước full; full vẫn đủ2224ca và fail-fast khi có lỗi, không dùng smoke thay
   full hoặc skip test. Các bản sửa đều ở tests/scripts, backend không đổi.
   Kết quả cuối: **2224passed,0fail/0error/0skip,1512.57s,61warnings**;
   **114Node passed**, TypeScript lỗi do allowlist bỏ sót5components`.jsx`.
   JUnit SHA256 `8811db711eaf3248b81270456f74afa1adff16b241091a1194d9916ecd5efd27`.
5. Frontend-only `007a30565a024df997e531c7cd2072c1`: **PASS** Node114,
   TypeScript, Next production build22pages. Script so toàn app/API/tests/
   contracts/dependency locks với archive đã đạt backend, chỉ cho bổ sung
   đúng5JSX bị thiếu; không đổi code ứng dụng. Dùng đúng image immutable từ
   lượt4, container không mạng/DB/host mounts. Chỉ kiểm lại frontend, không
   chạy lại2224backend hoặc sửa manifest FAIL trước đó. Receipt/log:
   `.runtime/s6-frontend-linux-007a30565a024df997e531c7cd2072c1/`.
   Node có0fail/0cancel/0skip; build còn React-hook warnings đã ghi log,
   không disable lint để qua gate. Primary/app/env không đổi, container đã dọn.

Source backup đã sửa để gồm JSX lồng thư mục và declarations, cùng Dockerfiles/
shell hạ tầng cần để dựng lại dự án;4archive tests đạt. Vẫn loại `.env`, runtime,
dependency/build và linked trees. Cần dùng checkpoint mới sau sửa, không gọi
source ZIP cũ thiếu JSX/Dockerfiles là bản frontend có thể build độc lập.
Checkpoint mới đã tạo và kiểm chứng: `.runtime/checkpoints/p0-20261016T153537-821c7155/manifest.json`,
1218sourcefiles/149tables/3M2artifacts/revision0070. Không kèm `.env`/keys.

Theo [API chính thức Temporal](https://python.temporal.io/temporalio.testing.WorkflowEnvironment.html),
`start_local` dùng dev server thật; `dev_server_existing_path` tránh tải ngầm,
SDK có lựa chọn tải CLI tương thích vào thư mục chỉ định. Không dùng server
mock hoặc time-skipping để thay bài kiểm tra real-clock này.

Linux container local không phải GitHub-hosted workflow đã chạy, VPS production,
HTTPS hay reboot/failover của máy chủ. Chưa tự push/dispatch GitHub.

## Những kiểm tra đã có kết quả cuối trong lượt này

- 18 nhóm unit offline đạt:6preflight,4CI guard,4Linux PG transport guard,
  4platform-native Temporal cache; Windows chọn PE cache đã có đạt.
- 4archive tests đạt sau sửa, gồm nested JSX và Dockerfile/shell; không gộp
  chúng vào2224backend. Diagnostic preflight cập nhật implementation_pending
  sau snapshot Linux,6unit host kiểm lại đạt; không sửa app/backend/tests input.
- Windows focused regression: **44/44 passed,81.46s**, gồm Meta installer,
  tenant app isolation/rotation và native populated P7 restore. Artifact
  `.runtime/s6-windows-focused.xml`; không gọi đây là full Windows rerun2224ca.
- Windows Temporal/ARQ sau sửa fixture: **9/9 passed,87.06s**,2ARQ deprecation
  warnings; artifact `.runtime/s6-windows-temporal.xml`. Bao gồm parent cancel,
  hai bước qua queue thật, cancellation drain/unknown; không gọi provider.
- Browser nghiệp vụ lần đầu dừng ở setup với `fetch failed`; chưa đủ bằng
  chứng kết luận lỗi UI hoặc khẳng định nguyên nhân RAM. Máy chỉ còn khoảng
  1.3GB RAM trống lúc Docker build. Không retry tự động POST gây duplicate.
- Sau build, chạy lại browser trên DB/API dùng một lần: **PASS**, profile
  versions/monthly draft/history/stale pins/unknown budget/routing/specialist
  denial/tenant isolation/mobile320–390px; dùng API/DB thật với dữ liệu giả.
  Populated restore và immutable review/routing/operations checks đạt. Artifact
  `.runtime/s5-browser.json`, ảnh `.runtime/s5-authoring-mobile.png`.
  Chưa có OAuth, Ads, media generation hoặc gửi tin thật trong bài này.
- Backend/UI/schema/.env chính chưa đổi:0070/live382/binding c22f08ca…f94269.

## Phần sản phẩm còn thiếu — không đổ cho môi trường

[ADR vòng đời tài khoản/dữ liệu](ADR-S6-ACCOUNT-AND-DATA-LIFECYCLE.vi.md)
ghi hai lựa chọn người dùng đã chốt: invite-only và chưa tự xóa. Invite/member
management, session revocation và export/delete-request UI/API đầy đủ vẫn
**implementation_pending**, không phải đã có chỉ nhờ tài liệu hoặc unit guard.
Retention kênh cũ cần đồng bộ chính sách; primary hiện0customerbindings.

Các gate dữ liệu thật/hành động được cấp riêng/owner pilot tiếp tục hoãn;
production host/HTTPS/reboot vẫn chưa có môi trường nghiệm thu. Không đổi các
gate này thành PASS từ hồi quy synthetic hoặc bản Docker build thành công.
