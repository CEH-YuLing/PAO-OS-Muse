# GD00 — Baseline và phục hồi local

Ngày: **21/10/2026**. Nguồn duy nhất: `F:\PAO-ACOS`.

## 1. Kết luận và giới hạn

GD00 được nghiệm thu **local**, không phải chứng nhận khôi phục thảm họa hoặc production.
Biên bản máy đọc hiện hành: `.runtime/gd00-current-status.json`; trường `baseline`,
`checkpoint` trỏ đến các file gốc và `completion.json` bất biến của từng lượt.
Chỉ dùng lượt có `local_accepted=true`; lỗi trước đó không bị ghi lại thành thành công.

| Hạng mục | Phạm vi đã kiểm tra |
|---|---|
| Mã nguồn | Manifest SHA256 từng file, source ZIP loại `.env`, Git, dependencies, build, runtime; kiểm tra trích xuất không ghi đè/thoát thư mục |
| Database | Schema **0075**, **160 ORM/161 bảng vật lý**; clone riêng khớp từng hash hàng, cột, defaults, constraints, indexes, triggers và functions |
| Hợp đồng API | **429 operations/55 router specs**; OpenAPI source/live/file đã lưu khớp; không tái sinh contract |
| Bản lưu thực thi | **3 archive** đọc/replay chỉ đọc, không gọi lại model hay công cụ |
| Cấu hình riêng | `.env`, pin Python, metadata thiết bị CLI, metadata native Antigravity và MCP profile PAO nếu có: bản riêng mã hóa Windows CurrentUser DPAPI |
| Giải mã | Khóa phục hồi được mở trong bộ nhớ để giải mã **2 bản ghi credential thực** trên clone; không in hoặc lưu plaintext |
| Boot từ backup | Source được trích từ ZIP; API ASGI khởi tạo/lifespan trên clone, đọc `/health`, `/ready`, `/openapi.json`, `/v1/me`, `/v1/runs/{id}` đều200 |
| Khởi động lặp | Gọi launcher hai lần; PID, executable, start-time không đổi; hash toàn bộ bảng primary không đổi, không thêm job |
| An toàn lỗi | Dump/ZIP sai hash, path traversal, thiếu private `.env`, khóa giải mã sai/thiếu, DPAPI sửa bit, CLI/subprocess và mạng ngoài trong reader bị từ chối |
| Kiểm thử GD00 | **28 unittest +5 test archive +6 guard PowerShell**; logs và interpreter từng nhóm trong completion. Không cộng vào regression backend cũ |

Boot ASGI trên clone là kiểm tra backend đọc dữ liệu phục hồi, **không phải** khởi chạy
toàn bộ Web/worker trên một máy mới hoặc kiểm thử lại login POST/chat/model/Ads thật.
Web/API/ready đang phục vụ đều200. Không sửa backend nghiệp vụ, frontend, dependency,
contract, `.env`, schema hay bật provider. Candidate0076 **chưa cài**.

### Những việc còn chờ, không được đánh dấu đạt

- Backup/khóa **ngoài máy, khác ổ**; chưa có địa điểm được chọn. Tất cả bản hiện tại vẫn trên F.
- DPAPI phụ thuộc tài khoản/profile Windows hiện tại: chưa phải gói khóa portable.
  Mất profile Windows hoặc toàn bộ máy có thể không mở được bản DPAPI.
- Không sao chép token/keyring hoặc volume chứa đăng nhập gốc của Codex/Claude/Antigravity.
  Máy mới cần cài và đăng nhập lại bằng luồng chính thức; metadata không chứng minh tài khoản dùng được.
- Chưa phục hồi full host/Windows/Docker volume/model weights/Temporal/Redis queue đang chạy.
  GD00 bảo vệ source, dữ liệu PostgreSQL và cấu hình PAO; không hứa tiếp tục chính xác một job đang dở sau mất máy.
- Chưa commit/nhánh/push/merge; chưa deploy công khai hay nghiệm thu production/owner pilot.

## 2. Baseline đang phục vụ

| Thành phần | Phiên bản/trạng thái ghi nhận |
|---|---|
| Windows | Windows11, build26200; thông tin đầy đủ trong operating-inventory |
| Python |3.12.14; release `2a62981090134b159cc2162fc3e1e15e`, lấy từ `get_acos_python.ps1` |
| Backend binding |`f596abc415cb9e97b18b7da6e5e1d937fe9194ac82896ea73badcc6d3ac1bf3a` |
| Runtime packages | FastAPI0.141.1, SQLAlchemy2.0.52, asyncpg0.31.0, Alembic1.19.2, PyJWT2.15.1, cryptography50.0.2, ARQ0.28.0 |
| Node |24.13.0 |
| Docker | Desktop4.74.0 / engine29.4.3; PostgreSQL17 và Redis7.4 local healthy |
| Web |Next dev3200; Auto/Sáng/Tối giữ nguyên; bằng chứng228Node/typecheck/build/browser tại biên bản Auto, không gọi là lượt mới trong GD00 |
| Git | HEAD `e1eb473`,17 commit lịch sử; nhiều modified/untracked có trước. Danh sách đầy đủ và scope allowlist trong `git-baseline-plan.json` |

Hash lockfile, binary/runtime pin, activation flags, process identity, Docker version,
metadata volume CLI và OpenAPI nằm trong `operating-inventory.json`/`baseline.json`.
Không dùng `.runtime/current-local-release.json` cũ làm chứng nhận cho source hiện tại;
GD00 ghi hash của file đó để truy nguyên, không ghi đè lịch sử.

## 3. Tách khởi động và migration

`start_acos_local.ps1`, `start_local.ps1` và `restart_acos_backend.ps1` gọi
`check_acos_startup_schema.py --expected 0075`. Kiểm tra dùng kết nối PostgreSQL
**server-enforced read-only**, không chạy `alembic upgrade`.
Legacy launcher vẫn từ chối khi đang có release pin; không dùng `.venv` để thay runtime phục vụ.

Nếu schema trống, nhiều head,0074/0076 hoặc không kết nối được: dừng, không tự sửa DB.
Với thay đổi schema sau này, bắt buộc theo thứ tự:

1. Chọn revision cụ thể và source/lock/pin phát hành; kiểm tra job đang chạy và cửa sổ bảo trì.
2. Tạo checkpoint mới, xác minh hash và phục hồi clone thành công **trước DDL**.
3. Thử migration và khả năng đọc/rollback trên clone có dữ liệu; xem xét downgrade có mất dữ liệu hay không.
4. Có phê duyệt thay đổi schema rồi mới dùng công cụ apply theo checkpoint của release đó.
5. Cập nhật pin launcher trong cùng release đã kiểm chứng; không dùng `head` ngầm khi khởi động thường.
6. Nếu lỗi: giữ checkpoint/log và dữ liệu mới; không tự downgrade hay restore đè primary để khớp test.

Đây không tạo runner nghiệp vụ mới; tái sử dụng `backup_acos_checkpoint.py` và
`check_s03_restore.py`, chỉ bổ sung tùy chọn đọc clone từ source phục hồi.

## 4. Cách tạo và kiểm tra một bộ phục hồi mới

Chạy trên máy local với tài khoản Windows đã tạo DPAPI. Không gửi file private lên chat/Git.
Thao tác dưới đây không khôi phục đè primary nhưng tạo dump chứa dữ liệu riêng của doanh nghiệp.

```powershell
Set-Location -LiteralPath 'F:\PAO-ACOS'
. .\scripts\get_acos_python.ps1
$paoPython = Get-AcosPython 'F:\PAO-ACOS'
$env:PAO_ROOT = 'F:\PAO-ACOS'
$env:PYTHONPATH = 'F:\PAO-ACOS\apps\api;F:\PAO-ACOS\scripts;F:\PAO-ACOS\packages\cli-runtime;F:\PAO-ACOS\packages\pao-mcp'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
& $paoPython -B scripts/gd00_baseline.py prepare
& $paoPython -B scripts/backup_acos_checkpoint.py
```

Ghi lại **folder** do prepare in ra và **manifest** do checkpoint in ra. Kiểm tra exit code;
nếu một bước lỗi, không coi đã có bản backup được nghiệm thu. Giữ source/DB ổn định khi đối chiếu.
Sau đó, thay hai đường dẫn minh họa dưới đây bằng chính kết quả vừa nhận:

```powershell
& $paoPython -B scripts/gd00_baseline.py verify `
  --folder '.runtime/gd00-<run-id>' `
  --manifest '.runtime/checkpoints/<checkpoint-id>/manifest.json'
```

Verify chạy offline tests, launcher2lần, kiểm chứng source/dump, phục hồi database có tên
`pao_s03_restore_<UUID>` mới và boot reader từ source ZIP. Reader không mở cổng HTTP,
không chạy worker/CLI, chỉ cho mạng loopback tới PostgreSQL/Redis, tắt activation flags
**trong child**, dùng JWT giả riêng và kết nối DB read-only. Redis14 chỉ dùng PING/lifespan;
không đọc hay sao chép hàng đợi Redis0. Khóa giải mã thực chỉ đi qua môi trường child trong bộ nhớ.

Sau kiểm tra, chỉ clone của lượt đó bị xóa; source trích xuất, backup, private DPAPI, log và
receipt được giữ. Thư mục trích xuất là bằng chứng, không tự thay source đang chạy.
Mỗi lần prepare tạo run-id mới; không ghi đè thư mục lỗi. Pointer current chỉ cập nhật sau toàn bộ pass.
Nếu source hoặc dữ liệu primary thay đổi giữa các bước: FAIL có chủ đích, không restore đè;
phân biệt thao tác người dùng, rồi tạo baseline/checkpoint mới khi ổn định.

### Chuẩn bị Git

`git-baseline-plan.json` liệt kê từng modified/untracked, phân biệt file nằm trong source
allowlist; không stage tất cả bằng `git add .`. Source ZIP bảo vệ cả source chưa tracked.
Giữ remote/branch/HEAD/index; chỉ commit hoặc publish khi có yêu cầu riêng.
Quét source và tất cả blob lịch sử có giới hạn, so với giá trị secret cấu hình và mẫu token/khóa.
Một marker private-key ở `test_artifact_learning.py:51` là fixture chống prompt poisoning,
đã đọc kiểm tra; ngoại lệ ràng buộc **hash toàn file**, không bỏ qua toàn thư mục tests.
Không phát hiện secret đã cấu hình trong scan này **không phải** chứng nhận tuyệt đối không có bí mật.

## 5. Test profile hiện hành

| Profile | Cách dùng và giới hạn |
|---|---|
| Offline GD00 | Pinned Python: `-m unittest scripts.test_acos_startup_schema scripts.test_gd00_baseline scripts.test_s03_restore -v`; không DB/Redis/provider |
| Source archive |5pytest trên `scripts/test_acos_checkpoint.py`; dùng `.venv` dev đã có pytest, tắt plugin tự nạp/cache; không cài pytest vào runtime đang phục vụ |
| Python/startup guard |`scripts/test_acos_python_pin.ps1`;6guard và parse launcher, fixture giả giữ trong `.runtime/pin-tests` |
| Contract preflight |`scripts/run_p0_checks.py --preflight-only`; sửa guard cũ154ORM thành đúng160ORM source0075; không chạy regression/build khi preflight-only |
| Backend DB Windows |`scripts/test_backend.py`: **chỉ pao_test/Redis15**, dev interpreter có pytest/plugins. Mọi operator dùng `isolated_test_slot()` từ `local_cycle_test_lock.py`; không chạy runner song song |
| Linux/hosted CI |`ci_entry.py`, `ci_restore_profile.py` và disposable Linux runner: profile test riêng; không chạy lại CI trong GD00, không gắn receipt cũ vào source mới |
| Frontend |Node tests dưới `apps/web/lib`, TypeScript, build; thừa kế đúng source Auto chưa đổi, không báo lượt mới228test |
| Browser |Biên bản Auto là phạm vi UI đã thử; cloneASGI là phục hồi backend, không thay thế browser E2E mới |
| Live |Web/API/ready200, contract khớp, bản lưu lịch sử đọc được; chưa nghiệm thu quota/provider/Ads/bot mới |

Không cộng 39kiểm tra GD00 vào2258regression lịch sử. Profile backend đầy đủ, Linux,
provider, dữ liệu thật và pilot có điều kiện riêng; không dùng preflight để tuyên bố chúng đã đạt.

## 6. Rủi ro/phát sinh và cách xử lý

| Rủi ro/phát sinh | Xử lý và trạng thái |
|---|---|
| Cùng ổ F bị hỏng | Offsite/portable key còn external_pending; chưa có DR toàn máy |
| Mất DPAPI Windows profile | Bản local có thể không mở; cần chốt kho khóa độc lập trước production |
| Dump chứa dữ liệu nhạy cảm | Không Git/chat/public; quyền truy cập của operator local; chưa có bản dump offsite mã hóa độc lập |
| Native client mất đăng nhập | Không trích token/keyring; cài và đăng nhập lại chính thức, test provider riêng |
| Có công việc đang thực thi khi hỏng máy | Giữ DB/source; đánh giá job/lease/outbox theo runner hiện có; không tự replay hành động bên ngoài |
| Source/history chưa commit | ZIP có manifest bảo vệ; Git baseline commit/publication cần quyền riêng |
| User thao tác trong lúc so hash | Fail và giữ dữ liệu mới; không khôi phục primary để làm xanh test |
| Launcher trước đây tự migrate | Đã tách bằng schema read-only gate, có unit/revision-negative và2lượt start |
| Lượt reader đầu thiếu Redis auth | Clone đã dọn; sửa reader dùng config riêng phục hồi trong bộ nhớ, không đổi Redis thật; lượt lỗi giữ nguyên |
| Shell PS5/PS7 kế thừa module path | Lượt kiểm tra đầu bị thiếu Get-FileHash; child chọn shell cài sẵn và tự dựng module path, không đổi hệ thống |
| Sandbox chặn loopback asyncio | Chỉ dừng đúng unittest đã đối chiếu exe/start-time; chạy lại có quyền local, không dừng PAO |
| Runtime phục vụ không chứa pytest | Không cài thêm vào runtime;5test archive dùng dev env; một warning config asyncio do tắt autoload, không có test bị skip |

Tiếp theo là **GD01 — AI dùng chung xuyên Chat/Agent/Job, đa model và effort**.
GD00 không tự mở rộng sang tính năng đó, không bật nhà cung cấp hoặc quảng cáo thật.
