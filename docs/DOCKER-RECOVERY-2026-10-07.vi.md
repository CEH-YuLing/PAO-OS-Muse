# Khôi phục Docker trước triển khai PAO

## Tái xuất hiện15/10/2026 — nghiệm thu S3.1B

Sau khi quay lại, Desktop/engine và toàn bộ cổng ACOS chưa chạy; WSL Docker
stopped. Start Desktop một lần, log mới05:11UTC xác nhận inaccessible
`dockerInference`, không suy ra chỉ từ lỗi Redis. CLI stop timeout20s. Đã
xác minh executable/start-time sáu tiến trình thuộc lần start này rồi dừng đúng
chúng; kiểm Docker thực sự dừng trước khi xử lý socket. Hai directory không
reparse và chỉ chứa expected socket0byte, giữ nguyên để hoàn tác tại:

- `Docker/run.stale-s31b-d68b2833c8e2473984d37dcea7ba498c`
- `docker-secrets-engine.stale-s31b-d68b2833c8e2473984d37dcea7ba498c`

Không xóa/reset/reinstall/update/reboot hoặc đổi settings/volumes. Engine29.4.3
đã phản hồi; chỉ start hai container ACOS có sẵn, PG/Redis healthy. Không tự
start các PostgreSQL/Redis/Temporal của repository khác hoặc launcher có auto-head
trước gate migration. Đây chưa là PAO API/Web/worker readiness hoặc production drill.

Exact restore checkpoint14/10 `p0-20261014T124839-544b00e6` từ chối vì duy nhất
`tenant_metadata_leases`: primary4row, dump1row. Không ghi đè primary hoặc bỏ
bảng khỏi so sánh. Checker bổ sung chẩn đoán chỉ tên bảng/count, vẫn từ chối
mọi row/hash/schema mismatch. Lập mốc dữ liệu hiện tại0059 và exact restore đạt:
`p0-20261015T053710-bfe33d96`,1076source/126physical/3M2archives/125business;
row hashes/schema equivalent/primary unchanged. Giữ cả dump cũ và mới.
Idle/safe-repair counts0, external flags off. Rollout S3.1B chỉ sau regression
và checkpoint riêng; source candidate0060 không là database đã0060.
Sau regression1737/5browser/96Node/build21, S3.1B đã rollout0060/live338 và exact
restore129physical/3archives đạt; API/ready/Web200/workerhealthy, idle0.
[Acceptance15/10](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md) sở hữu trạng thái mới,
không suy từ engine startup hoặc các evidence14/10 bên dưới.

## Tái xuất hiện14/10/2026 — S2.2B3

Log mới xác nhận inaccessible dockerInference, chỉ runtime sockets0byte;
directory không reparse. Giữ hai cặp runtime directories suffix
`stale-s22b3-2a87e4ef8c94473bb4aa82edc2b0b4d0` và
`stale-s22b3-65f1e879aa724823b9ba7237f81f0af7`. Không xóa volumes/settings,
reset/reinstall/update/reboot. Engine29.4.3/PG/Redis healthy,0058/checkpoint,
API/ready/Web200/workerhealthy/live334/binding/M2replay3/3 đạt theo
[evidence](S22B3-QUOTA-SETTINGS-2026-10-14.vi.md).

CLI stop timeout20s không bảo đảm stop đã kết thúc: thao tác stop cũ có thể
hoàn tất muộn, đóng instance vừa start và tạo socket mới. Không suy đoán chỉ
từ timeout; chờ stop thực sự hoàn tất, kiểm processes/log/entries mới trước
quarantine/start kế tiếp. Luôn kiểm executable/start-time; không retry mù.

## Tái xuất hiện13/10/2026 — S2.2B1

Log mới xác nhận dockerInference inaccessible. Bounded stop20s; xác minh
executable/start-time, dừng đúng Docker processes. Hai directories không reparse,
chỉ có expected sockets0byte; giữ recoverable, không xóa:

- `Docker/run.stale-s22b-510353eae5f141aa90137f623f4ea25f`
- `docker-secrets-engine.stale-s22b-b40e4d91dfd1416b90bfe9e2fc4635b1`

Engine29.4.3/ACOS PG/Redis healthy; prechange checkpoint0053 verified. Sau
rollout0054, API/ready/Web200/workerhealthy, live330/binding/M2replay3/3 khớp.
Xem [S22B1 acceptance](S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md).
Không volumes/settings/reset/reinstall/reboot; production drill vẫn chưa đạt.

User cho phép ngày07/10/2026: nếu Docker chặn triển khai, tự chẩn đoán và xử lý
Docker trước. Không cần hỏi lại cho các bước khôi phục local có thể hoàn tác.
Không tự xoá volumes, factory reset, unregister WSL, reinstall hoặc reboot host.

## Lỗi quan sát

Docker Desktop4.74.0 không khởi động Engine, log lần lượt báo:
`initializing Inference manager` / `initializing Secrets Engine`, Windows1920
`The file cannot be accessed by the system`, rồi listener123 invalid name.
PostgreSQL15432/Redis16379 không sẵn sàng, chưa tạo được checkpoint M4.

Đã đọc metadata và xác nhận hai directory dưới đây chỉ chứa socket 0byte dạng
ReparsePoint. Không mở nội dung credential hoặc đụng VHDX/settings/volumes.

## Biện pháp đã thực hiện

1. Thử Docker Desktop stop có timeout; lệnh thông thường không dừng được.
2. Xác minh executable trong Program Files/Docker và process creation-time,
   dừng đúng các process Docker đang crash. Không stop process theo wildcard.
3. Move-Item riêng dockerInference không được Windows cho phép. Không dùng
   recursive delete, fsutil delete, sửa reparse tag hoặc factory reset.
4. Đổi tên directory runtime socket đã xác minh không phải reparse directory:
   `AppData/Local/Docker/run` →
   `AppData/Local/Docker/run.stale-0b6f2430dafb414d83185ddafef13be9`.
   Bản cũ chứa đúng dockerInference/userAnalyticsOtlpHttp.sock, cả hai 0byte.
5. Sau khi vượt inference, Docker báo lỗi engine.sock. Xác nhận directory
   `AppData/Local/docker-secrets-engine` chỉ có engine.sock0byte, rồi giữ tại
   `docker-secrets-engine.stale-cb372f5cae9d4c7180497454e8140c58`.
6. Tạo directory runtime trống đúng tên cũ, khởi động Docker Desktop Hidden.
   Không xoá các directory đã giữ; chỉ phục hồi khi Docker dừng và path được kiểm.

7. Xử lý riêng từng directory làm socket inference từ lần thử trước lại chặn
   startup. Đã kiểm kê và cô lập đồng thời cả hai runtime directories, giữ thêm:
   `Docker/run.stale-c5c676100685421783c566a164a08f18` và
   `docker-secrets-engine.stale-573f682a850f45159d7f332b11405181`.
   Không có mục nào bị xoá. Engine sau đó trả server version29.4.3.

## Kiểm chứng sau sửa

- PostgreSQL/Redis ACOS containers healthy, giữ volumes hiện có.
- API health/ready và Web HTTP200; worker healthy. Web cần cold-start trước
  lượt health cuối, không nới điều kiện checker để bỏ qua startup failure.
- Full live OpenAPI/binding khớp source P5, archive replay M2 đạt3/3.
- Database vẫn revision0034, business writes tắt, actual MCP connections0.
- M3 readiness vẫn thiếu app/credential/connection/report; không gọi Meta.
- Checkpoint verified sau sửa:
  `.runtime/checkpoints/p0-20261007T055002-f6e45762/manifest.json`, 569 source
  files, 89 physical tables, 3 artifacts, revision0034. Không chia sẻ runtime.
- Không thay backend code hoặc chạy migration M4. Đây là khôi phục môi trường,
  không phải chứng nhận M4 hay production reboot drill.

## Nguyên tắc áp dụng lần sau

Không áp dụng rename mù quáng. Chỉ khi log mới xác nhận đúng lỗi/socket, đã
kiểm kê directory chỉ có runtime sockets 0byte và Docker đã dừng. Nếu có file
khác, secrets/database hoặc directory reparse, dừng để đánh giá/nhờ user.
Không thay đổi flags inference nếu chưa có bằng chứng sẽ giải quyết vấn đề.
Mọi CLI probe phải có timeout, không lặp khởi động vô hạn.

Tham khảo báo cáo lỗi tương tự tại
[Docker desktop-feedback448](https://github.com/docker/desktop-feedback/issues/448)
và [527](https://github.com/docker/desktop-feedback/issues/527). Đây là user bug
reports trên repo Docker, không phải cam kết recovery được Docker bảo đảm.

## Tái xuất hiện ngày08/10/2026 — tiếp tục P6.3B2b2b

Sau gián đoạn phiên kiểm thử, Engine và dịch vụ PAO đều tắt. Khởi động Desktop
báo đúng lỗi remove dockerInference/Windows inaccessible; không suy luận chỉ
từ lỗi PostgreSQL. CLI stop có timeout25s không hoàn tất. Đã xác minh đúng
executable/creation-time và dừng các Docker processes; chờ process thực sự
thoát trước đổi tên. Directory không phải reparse, mỗi mục bên trong chỉ là
socket0byte đã kiểm kê; giữ riêng để hoàn tác:

- `Docker/run.stale-9a31d2badddc43fbabe8f2a151a2dece`
- `docker-secrets-engine.stale-5dab33a4893c4bb1ba15aca54574a345`

Không xóa volumes/settings/runtime cũ, không reset/reinstall/update/reboot.
Engine29.4.3, PostgreSQL/Redis healthy; verified checkpoint685source/97tables/
3artifacts/0039 tại `.runtime/checkpoints/p0-20261008T090844-c5fb8d3e/manifest.json`.
Sau regression871pass, restart PAO: API/ready/Web200, workerhealthy, contract254/
binding khớp, M2replay3/3, P6.2replay7/7,153synthetic goal histories và idle0 đạt.
Web cần cold-start; đã rerun checker nguyên vẹn sau HTTP200, không bỏ endpoint.
Gate workflow/goal/live write vẫn tắt. Không coi đây là production reboot drill.

## Tái xuất hiện ngày10/10/2026 — P6.4 persisted schedules

Engine và PAO đều tắt; Desktop báo đúng inaccessible dockerInference. Stop CLI
timeout20s, kiểm tra executable/creation-time và dừng đúng Docker processes.
Chờ process thực sự thoát; directory không reparse, chỉ socket0byte. Giữ:

- `Docker/run.stale-p64-62c000fb3c93406bb2231c7e170096e3`
- `docker-secrets-engine.stale-p64-0c6817f89ca248e9996a0be56e220b94`

Không xóa volumes/settings/socket cũ, không reset/reinstall/reboot. Engine29.4.3,
PG15432 và Redis16379 healthy. Checkpoint0041 trước schema mới verified:
`.runtime/checkpoints/p0-20261010T050002-6c9184cc/manifest.json`,756source files,
101physical tables,3artifacts. Live health sau rollout ghi trong báo cáo P6.4;
không dùng startup Docker làm bằng chứng PAO hoặc production đã đạt.

## Tái xuất hiện ngày09/10/2026 — Temporal child drain

Engine tắt; sau start Desktop log mới xác nhận lỗi dockerInference. Stop CLI
timeout20s. Xác minh executable/start-time, dừng đúng Docker process và giữ hai
directory chỉ có socket0byte, directory không reparse:
Docker/run.stale-3057c36e3e8e4080a6ae804bd83aef35 và
docker-secrets-engine.stale-f6756e7cdaa04503bfac55a728be425d.
Không xóa volumes/settings/reset/reinstall/reboot. Engine29.4.3 hoạt động,
start lại đúng ACOS PostgreSQL/Redis; checkpoint708source/97tables/3artifacts/
0039 verified trước startup. Web cần cold-start; sau HTTP200 rerun checker
nguyên vẹn. Xem [báo cáo](P63-TEMPORAL-CHILD-DRAIN-2026-10-09.vi.md).
