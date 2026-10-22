# S3.1B — Nghiệm thu tích hợp và rollout local

15/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`, không sửa nguồn Apex.
Trạng thái: **local_accepted — S3.1B và tổng S3.1 (A+B)**; chưa nghiệm thu toàn S3/production.
[Phạm vi/ADR](ADR-S31B-TELEGRAM-LEGACY-MAPPING.vi.md),
[lịch sử triển khai14/10](S31B-IMPLEMENTATION-2026-10-14.vi.md),
[S3 register](S3-COMPLETION-REGISTER.vi.md).

## Phạm vi

S3.1B bổ sung explicit owner mapping Telegram legacy vào một SME, preview/hash/
version/request-key và journal/provenance/audit; generation mới đang tắt, không
repin receipt/Brain/session hoặc phát lại unknown/queued. Settings có hai consent,
lost-ACK/manual GET, revoke không hồi sinh host bot. Không thêm token, không
chọn SME hoặc apply mapping trên primary. S3.2/S3.3 và live provider vẫn riêng.

## Bằng chứng15/10

| Gate | Kết quả |
|---|---|
| Docker recovery |Engine29.4.3; PG15432/Redis16379 healthy; giữ hai directory socket, không reset/reinstall/update/reboot/xóa volume |
| Source/credentials |Backend binding `e7ddf35b27d826439541b55f50052817e12837097a9b6a912d399d71458934c3`; `.env` hash không đổi |
| Full backend |1737passed/0fail/0error/0skip,2000.27s; real ARQ wall-clock bật; `.runtime/s31b-backend-20261015.xml`;41ARQ deprecation warnings lịch sử |
| Real ARQ recovery |Between71.61s và during93.22s thực; một tool claim, không nhận việc trùng |
| Node/runtime/SSE |96passed/0fail/0skip,1294ms |
| Frontend |Production build21/21, standalone TypeScript noEmit đạt; không gọi zero-warning vì lint lịch sử |
| Restore helpers |8pure unittest đạt; không chạy pytest chồng lên database test |
| Browser tích hợp |5passed/0fail/0error/0skip,153.66s; `.runtime/s31b-browser-20261015.xml`; S11/S12/P7/S23F/S31B, API/DB thật, chỉ fixture, không mic/provider thật |
| Pre-rollout restore |`p0-20261015T053710-bfe33d96`:1076source/0059/126physical/125business/3archives, exact row hashes/schema equivalent/primary unchanged |
| Checkpoint trước migration |`p0-20261015T061352-c370d73c`:1077source/0059/126physical/3archives; exact restore/current binding/idle0 đạt trước thay đổi |
| Migration primary |0059→0060 đạt; old-column hashes exact,3archives giữ nguyên,3bảng mới rỗng, không backfill/credential copy; `.env` không đổi; alembic check đạt |
| Installed live |0060/live338/bindinge7ddf35b,129physical tables/3archives; full OpenAPI khớp, owner GET/anonymous401/foreign404/no-store đạt; journal0/no auto mapping |
| Runtime readiness |API health/ready/Web200, workerhealthy, Telegram bridge disabled; startup đúng Ollama/API/worker/Web local; không coi PID là readiness |
| Process/network/idle |Executable/start-time records khớp; listener8100 child2160→API13356,3200 child9068→Web18248,11434 Ollama20392; chỉ127.0.0.1, idle/safe-repair0 sau rollout |
| Post-rollout exact restore |`p0-20261015T061605-a3e42c8d`:1077source/0060/129physical/128business/3archives, row hashes exact/schema equivalent/primary unchanged |

## Phục hồi môi trường và sai khác checkpoint

Docker/WSL/API/Web đã tắt khi quay lại. Một lần start cho log mới xác nhận
inaccessible dockerInference; CLI stop timeout20s. Xác minh đúng executable và
start-time, dừng sáu process của lần start này, giữ socket0byte ở directories
không reparse, rồi khởi động lại. Xem [recovery runbook](DOCKER-RECOVERY-2026-10-07.vi.md).

Checkpoint14/10 `p0-20261014T124839-544b00e6` không còn khớp primary: duy nhất
`tenant_metadata_leases` primary4row/dump1row. Checker vẫn từ chối, không bỏ bảng
khỏi so sánh. Bổ sung diagnostic chỉ tên bảng/count, không in nội dung riêng tư.
Không ghi đè dữ liệu hiện tại bằng dump cũ. Mốc mới0059 ở bảng trên đã exact
restore đạt, giữ cả hai bản sao. Idle/safe-repair0; external gates off.

## Rollout và bước tiếp

Các gate đóng đã đạt trong bảng trên. Không có service cũ đang chạy khi quay lại;
không stop PID cũ hoặc đoán PID. Sau migration khởi động bằng launcher ACOS:
API13356/worker11032/Ollama20392 lúc13:15:00VN và Web18248 lúc13:15:03VN;
đã đối chiếu đúng executable và start-time với process records. Health/live/restore
là proof thực tế, không chỉ log Started. Giữ mọi checkpoint/dump và socket quarantine.

Sau đồng bộ master/register tạo thêm checkpoint nguồn cuối và exact restore;
manifest cuối cung cấp trong handoff, không sửa lại source để thêm self-reference.

S3.1A+B đã đóng local; đúng một việc tiếp theo **S3.2 bot-specific
runtime**. Không coi storage/mapping là resolver token, nhiều bot gửi thật, HTTPS/
reboot production hoặc toàn S3 đã nghiệm thu. Không hỏi lại các lựa chọn SaaS đã duyệt.
