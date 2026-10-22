# Phase 18 — Voice

Phase 18 nối microphone → browser VAD → Faster Whisper local → PAO Core → Windows SAPI/Piper local. Bấm nói trong lúc PAO đang phát hoặc chạy sẽ dừng playback và yêu cầu hủy run hiện tại trước khi thu lượt mới.

## Phạm vi đã triển khai

- Browser `MediaRecorder`, echo cancellation/noise suppression, RMS VAD, auto-stop sau im lặng và hard limit 30 giây.
- Raw upload theo content type allowlist, giới hạn 10 MiB, rate limit, RBAC và session/workspace scope.
- Faster Whisper Small chạy CPU `int8`, model chỉ đọc từ `.runtime/models`; `local_files_only=True` ngăn tải ngầm.
- TTS local bằng Windows SAPI COM; boundary Piper có sẵn cho hệ điều hành khác.
- Transcript được đưa thẳng vào run hiện tại; kết quả hoàn tất được tổng hợp thành WAV và phát trong browser.
- Orb dùng đủ `listening`, `processing`, `reasoning`, `speaking`; mic mới có thể ngắt playback/run.
- Database chỉ lưu metadata audit (bytes, duration, provider, trạng thái); không lưu raw audio, transcript hoặc nội dung TTS.

## An toàn và tài nguyên

Voice mặc định tắt trong `.env.example`. `scripts/setup_voice.py --download --enable` tải model được chọn vào storage local và bật gate. Máy hiện tại dùng một model/job, CPU `int8`; không bật CUDA do cấu hình GTX 1060/driver trước đó chưa ổn định.

Faster Whisper cung cấp CPU INT8 và VAD tích hợp theo [tài liệu dự án chính thức](https://github.com/SYSTRAN/faster-whisper). Windows SAPI chỉ chạy trên máy local; có thể chuyển sang Piper executable/model bằng cấu hình mà không thay API.

## Xác minh

- Migration roundtrip `base → 0017`, Alembic check và toàn bộ 156 backend tests đạt.
- Test RBAC, format/size, fail-closed, STT/TTS audit và không có trường lưu audio/transcript.
- Smoke test thật TTS → WAV → Faster Whisper đạt trên CPU local; kết quả/độ trễ nằm ở `.runtime/phase-18-voice-smoke.json`.

## Kết quả triển khai local

- Backup cuối `.runtime/pre-phase-18-20260922-181341.dump` có 260.420 bytes và đọc được bằng `pg_restore --list`.
- Counts của 50 bảng cũ giữ nguyên; database lên revision `0017`.
- Backend Phase 1–18: 156 tests; runtime state/SSE: 8 tests; production build và browser acceptance đều đạt.
- OpenAPI có 83 paths. Runtime chính báo Voice enabled, STT ready, TTS ready; smoke gần nhất tạo WAV 234.830 byte, TTS khoảng 0,8 giây và STT khoảng 16,5 giây. Meta Write và Autopilot vẫn tắt.
