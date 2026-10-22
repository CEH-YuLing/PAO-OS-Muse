# PAO-ACOS — Baseline môi trường độc lập

Ngày nghiệm thu: 05/10/2026. Thư mục dự án chính: `F:/PAO-ACOS`.

## Kết quả

Code PAO, Python dependencies, Ollama executable/thư viện CPU và model store
đang được sử dụng từ thư mục PAO-ACOS. Không cần executable hoặc dependency
từ checkout Apex cũ để khởi động. Python 3.12 nền, Node.js và Docker vẫn là
các chương trình được cài trên máy; virtual environment cần tạo lại khi chuyển
máy, không phải một Python portable.

## Thành phần vận hành

- `.venv`: tạo mới từ Python 3.12.14, cài `requirements.lock` và PAO editable.
- `requirements-dev.lock`: cố định phiên bản test đã được nghiệm thu.
- `.runtime/ollama`: Ollama 0.34.0, 44 tệp CPU/license, khoảng 72.9 MiB.
- `.runtime/models`: Qwen local hiện có, chưa có embedding model.
- Docker project `pao-acos-local`: PostgreSQL cổng 15432, Redis cổng 16379.
- Database ứng dụng `pao_acos_local`: migration `0022 (head)`.
- Web cổng 3200; API cổng 8100; Ollama cổng 11434.

## Kiểm thử trong lượt này

- `pip check`: đạt, không có dependency lỗi.
- Import code và dependency: đường dẫn đều nằm trong PAO-ACOS.
- Backend regression: 182 passed trong 118.74 giây, dùng database `pao_test`
  riêng trên PostgreSQL ACOS và Redis DB 15; schema check đạt.
- Runtime/SSE: 8/8 passed.
- Chat qua web proxy/API/worker/Ollama mới: completed sau 62 giây,
  trả lời `Chào bạn!`, không error.
- API ready và web dashboard: HTTP 200.
- Chạy launcher hai lần: nhận đúng process hiện có, không tạo trùng.
- Cú pháp hai script PowerShell: đạt.

## Các lệnh dùng hằng ngày

Từ thư mục dự án, sau khi Docker Desktop sẵn sàng:

```powershell
./scripts/start_acos_local.ps1
```

Đợi chat đang chạy hoàn tất trước khi dừng:

```powershell
./.venv/Scripts/python.exe scripts/check_acos_idle.py
./scripts/stop_acos_local.ps1
```

Khi dựng lại Python trên một máy khác:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
./.venv/Scripts/python.exe -m pip install --no-deps -e .
```

## Git baseline

Git được khởi tạo riêng trong PAO-ACOS. Baseline chỉ chứa mã nguồn, cấu hình
mẫu và tài liệu; không có `.env`, runtime, models, dependencies, logs hoặc data.
Không cấu hình remote và không push. Git bundle local sẽ được lưu trong
`.runtime` để phục hồi code; đây không phải backup database hoặc backup khác ổ.

## Giai đoạn tiếp theo

Giai đoạn 3/M1 đã có code và regression đạt. Bước chuyển môi trường trước
Giai đoạn 4 đã hoàn tất. Giai đoạn 4/M2 (Skill Registry và business tools)
chưa bắt đầu trong baseline này.

M2 sẽ bắt đầu với manifest/version/hash, schema input/output, quyền tool và
evaluator; ba skill đầu theo roadmap là daily-business-brief,
investigate-ads-drop và creative-fatigue-review.

Temporal, Telegram, Voice, live Ads và Memory chưa được nghiệm thu lại trong
môi trường độc lập này; không xem regression là bằng chứng kết nối thật.
