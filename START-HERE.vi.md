# PAO OS Muse — bắt đầu tại đây

Bản phát triển độc lập từ PAO ngày22/10/2026, dành cho chủ sở hữu dùng Muse Code
trong Orca. Không phải VPS/public release hoặc bản backup chứa dữ liệu thật.

## Chạy và đăng nhập

Mở PowerShell trong `G:\PAO OS Muse`, chạy:

```powershell
.\Start-Muse.ps1
```

Mở **http://127.0.0.1:3300/**. Tài khoản local mới và mật khẩu ngẫu nhiên nằm
trong `.runtime/first-login.txt` trên máy. Không gửi mật khẩu cho Muse/chat,
không commit file đó. Tài khoản này không phải tài khoản của PAO gốc hoặc Muse.

Dừng API/worker/Web của bản này:

```powershell
.\Stop-Muse.ps1
```

Docker giữ dữ liệu để lần sau chạy lại. Không dùng `down -v`, prune hoặc reset.
Nếu PowerShell chặn script, dùng tùy chọn **process-only**, không đổi policy máy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-Muse.ps1
```

## Mở trong Orca và làm việc bằng Muse

1. Mở Orca, thêm/mở thư mục `G:\PAO OS Muse` (không chọn folder nguồn ổ F).
2. Chọn agent Muse Code mà bạn đã cài/đăng nhập trong Orca.
3. Gửi nội dung `handoff/PROMPT-FOR-MUSE.vi.md` làm yêu cầu đầu tiên.
4. Yêu cầu Muse đọc `AGENTS.md`, `MUSE.md` và `handoff/PROJECT-STATE.vi.md`.
5. Kiểm tra Git baseline trước khi sửa. Không tự push lên remote PAO gốc.

Không tự khởi chạy coding agent hoặc tiêu quota Muse trong bước cài đặt này.
Orca/Muse coding agent và provider Muse bên trong PAO là hai luồng khác nhau.

## Kết nối Muse để chat trong bản PAO này

Vào **Cài đặt và kết nối → AI và giọng nói → Nhà cung cấp mô hình → Client → Muse**.
Đăng nhập chính chủ theo luồng Muse khi được yêu cầu, rồi Kết nối/kiểm tra danh mục.
Chọn Muse/model/effort trong PAO AI. Bản mới không lấy login của PAO gốc và không
mượn token từ profile Muse/Orca. Việc đăng nhập dùng cùng tài khoản thuê bao được
hỗ trợ hay không phải tuân thủ nhà cung cấp; không suy ra entitlement từ catalog.

Chưa đăng nhập thì AI hiện chưa kết nối là đúng. Không tự gọi Ollama/API thay thế.
Không cần cài Ollama để mở Web/API/quản lý công việc; memory extraction/embedding
local đang tắt vì chưa có model/embedding server riêng. Bật lại khi đã cấu hình
nguồn phù hợp, không trỏ sang runtime nguồn một cách ngầm định.

## Cổng và dữ liệu riêng

| Thành phần | Bản Muse | PAO nguồn — không thao tác |
|---|---|---|
| Web |127.0.0.1:3300|127.0.0.1:3200|
| API |127.0.0.1:8200|127.0.0.1:8100|
| PostgreSQL |127.0.0.1:25432 / pao_muse_local|15432 / pao_acos_local|
| Redis |127.0.0.1:26379 /0|16379 /0|
| Test |25432 /pao_test; Redis26379 /15|Không dùng DB/Redis test nguồn|
| Docker project |pao-os-muse|pao-acos-local|
| Python |.venv riêng trong G:|Runtime pin nguồn trong F:|

Mã nguồn, migration, tests, contracts và tài liệu được sao chép; dependency
được cài riêng từ lockfile. Không sao chép node_modules/venv cũ, Git history,
database, memory, .env, blobs, token/login CLI hoặc key nguồn.

## Cài lại dependency nếu cần

Không chạy những dòng sau vào folder nguồn. Không xóa môi trường hiện có để thử.
Đã cài xong trên máy hiện tại thì không cần chạy lại. `Install-Muse.ps1` gói lại
các bước cài lockfile/build/setup; có thể dùng khi cần dựng lại môi trường trong
đúng folder này. Dừng bản Muse trước khi build/cài lại; không chạy song song build/dev.

```powershell
# Đang đứng tại G:\PAO OS Muse
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
npm.cmd ci --no-audit --no-fund
.\.venv\Scripts\python.exe -B scripts\muse_sandbox.py setup
```

`setup` không reset tài khoản/dữ liệu đã tồn tại. Chỉ migration tới0077 trong
database Muse đã guard; khi nâng schema sau này cần backup/restore clone riêng.
Source `.env.example` là ví dụ gốc, **không dùng để ghi đè `.env` bản Muse**.

## Giới hạn hiện tại

Đây là source đầy đủ và bộ chạy local độc lập, không phải mọi tính năng đều đã
có dữ liệu hay được bật. Temporal/Goal durable, bot thật, Ads write, API paid,
Ollama/embedding/voice và shared Codex không được tự kích hoạt. Đọc báo cáo cài
đặt tại `handoff/COPY-ACCEPTANCE.json` để biết bài nào thực sự đã chạy trên G:.

Kiểm tra lại sau khi sửa code bằng `Test-Muse.ps1` (10test focused, không phải
full suite) và `.venv\Scripts\python.exe -B scripts\verify_muse_install.py`.
Verifier hash chỉ dùng trước thay đổi phát triển; sau khi bạn sửa code, mismatch
là đúng và cần đối chiếu Git baseline, không viết lại manifest để che drift.
Settings có thể trả503 riêng cho Antigravity chưa provision; đây là trạng thái
chưa kết nối được ghi rõ trong nghiệm thu, không phải mọi Client đã hoạt động.
