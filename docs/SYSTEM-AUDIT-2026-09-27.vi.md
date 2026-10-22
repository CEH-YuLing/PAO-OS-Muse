# PAO — Báo cáo kiểm thử toàn hệ thống

Ngày kiểm tra: **27/09/2026**. Repository: `F:/Apex/apex`.

## Kết luận

PAO đang hoạt động ổn định ở lớp nền tảng local: API, web, PostgreSQL, Redis/ARQ,
Ollama, Telegram, Temporal và Voice đều khởi động; database ở revision `0019`.
Backend regression, runtime/SSE và production build đều đạt. Memory, Tool Gateway,
Temporal và Voice đã được smoke test bằng dịch vụ thật/local.

Hệ thống chưa sẵn sàng cho vận hành quảng cáo thực tế. Meta Ads, Google Ads,
TikTok Ads, CRM/attribution và Creative Intelligence chưa có connection hoặc dữ
liệu thật trong database. Phần năng lực Javis mới chủ yếu là registry, mapping và
shadow mode; các adapter cloud/channel/skill chưa được triển khai đầy đủ.

## Kết quả kiểm thử vừa chạy

| Hạng mục | Kết quả |
| --- | --- |
| System verifier | Đạt: revision `0019`, 60 bảng, 90 OpenAPI paths, API/Web/assets HTTP 200 |
| Tiến trình | Ollama, API, Web, ARQ worker, Temporal worker, Telegram đều sống |
| Backend regression | **167 passed** trên `pao_test` |
| Runtime/SSE | **8/8 passed** |
| Next.js production build | Đạt, 17 route |
| Python dependency check | Đạt |
| Temporal smoke | Đạt: workflow nhận approval signal và hoàn tất |
| Memory thật | Đạt: extraction, embedding 768 chiều, cross-session recall, brand isolation |
| Tool Gateway thật | Đạt: SearXNG trả nguồn PostgreSQL chính thức; approval mock không gửi ra ngoài |
| Voice local | TTS tạo WAV 234.830 byte; STT chạy CPU/int8 và trả transcript |
| PAO AI scroll/delete | Đạt test riêng: ba vùng cuộn độc lập và DELETE 204 cập nhật UI |
| Browser acceptance chính | **Không đạt do test đã cũ/thiếu đồng bộ** |
| Agent orchestration thật | **Không đạt yêu cầu Researcher → Editor** |

## Lỗi và hạn chế đang quan sát được

### P1 — Agent planner không ổn định với model local

Ca nghiệm thu yêu cầu đúng hai bước `Researcher → Editor` đã rơi vào `fallback`.
Chỉ `chief_of_staff` chạy và trả câu trả lời. Run vẫn mang trạng thái `completed`,
vì vậy người dùng có thể không nhận ra kế hoạch multi-agent đã bị bỏ qua. Thời gian
ca này là **121,4 giây**.

Cần thêm deterministic routing cho yêu cầu chỉ định agent rõ ràng, lưu lý do parse
failure và hiển thị cảnh báo fallback trên UI. Acceptance phải kiểm tra cả nội dung
trả lời và danh sách agent thực sự chạy.

### P1 — Chưa có tích hợp Ads/CRM production

Các cờ `META_ENABLED`, `GOOGLE_ADS_ENABLED`, Meta Write và global Autopilot đều
đang tắt. Database có 0 Meta connection, 0 Google Ads connection, 0 Ads entity,
0 metric, 0 report, 0 action, 0 attribution source/run và 0 creative asset.
TikTok Ads mới có trang readiness; connector backend chưa tồn tại.

Do đó các trang Ads, CRM, Analytics và Content & Creative đã có cấu trúc/API nhưng
chưa được nghiệm thu với account, quota, timezone, currency, rate limit và dữ liệu
thật. Meta Write và Autopilot chưa được phép vận hành.

### P1 — Phạm vi Javis chưa được tích hợp đầy đủ

- Fast path mới chạy **shadow**, chưa làm thay đổi execution path.
- Model router đa provider chưa triển khai; OpenAI, Anthropic, Gemini và OpenRouter
  đều chưa cấu hình và chưa có runtime adapter hoàn chỉnh.
- Tự học và skill importer đang ở trạng thái `partial`.
- Công việc định kỳ mới dựa trên Temporal workflow; recurrence scheduler chưa hoàn chỉnh.
- Zalo OA và Botcake mới xuất hiện trong catalog/cấu hình, chưa có channel adapter.
- File vault, terminal sandbox, plugin host và Brain filesystem importer chưa có.

### P2 — Browser acceptance chính đã lệch so với UI hiện tại

Kịch bản `scripts/verify_workspace_ui.cjs` bấm mở bảng điều khiển ngay sau submit
đăng nhập mà không chờ dialog đóng, làm login layer chặn click. Khi thêm bước chờ
trong bản test tạm, kịch bản còn kỳ vọng Settings có 5 tab trong khi UI hiện có 6
tab vì đã thêm “Năng lực Javis”. Một lượt chạy tiếp theo còn cho thấy trạng thái
Google Ads mock không ổn định khi điều hướng toàn bộ route.

Đây là nợ của test harness. Cần cập nhật mock `/v1/platform/catalog`, chờ hydration
rõ ràng, sửa số tab, và bổ sung test scroll/xóa hội thoại vào suite chính.

### P2 — Voice chạy được nhưng chất lượng tiếng Việt còn thấp

Smoke test tạo audio thành công trong 906 ms; STT mất khoảng 24,3 giây. Transcript
của câu tổng hợp tiếng Việt sai nhiều từ. `voice/status` hiện chỉ kiểm tra model/path
và SAPI có sẵn, chưa phản ánh chất lượng hay lượt synthesis gần nhất.

Cần bộ mẫu giọng nói thật, WER/CER, lựa chọn voice tiếng Việt phù hợp và health check
có canary ngắn. Lần chạy trong sandbox bị Windows chặn COM; chạy với quyền SAPI đầy
đủ đã đạt, nên lỗi quyền sandbox không được tính là lỗi production.

### P2 — Độ trễ local cao

- Agent acceptance fallback: **121,4 giây**.
- Tool search + Researcher + Chief: **130,1 giây**.
- Memory extraction + embedding + recall: **206,4 giây**.
- SearXNG trả kết quả đúng nhưng báo 1 search engine không phản hồi.

Cấu hình CPU tuần tự bảo vệ máy i3/16 GB nhưng trải nghiệm tương tác còn chậm. Cần
telemetry TTFT/p50/p95, active fast-path canary sau khi qua quality gate, giảm prompt
context và profile GPU mới khi nâng cấp phần cứng.

### P2/P3 — Khoảng trống vận hành và quản trị

- Chưa MFA/SSO, refresh token, revocation toàn thiết bị và quản trị multi-workspace đầy đủ.
- Chưa quota tenant, retention policy, export/delete workflow toàn diện.
- Email và calendar vẫn là mock có approval; competitor intelligence chưa triển khai.
- Telegram bridge chưa được đóng gói thành Windows service/supervisor; các fault test
  PostgreSQL restart, advisory lock và workflow chờ nhiều ngày còn thiếu.
- Chưa có load test, penetration test, dependency/CVE audit hoặc disaster-recovery drill mới.
- Repository hiện là worktree thay đổi lớn chưa commit; lịch sử Git vẫn phản ánh baseline cũ.

## Dữ liệu production hiện có

| Dữ liệu | Số lượng |
| --- | ---: |
| User / workspace | 1 / 1 |
| Session | 10, trong đó 8 đã archive |
| Message / run / agent run | 53 / 27 / 31 |
| Active run | 0 |
| Memory | 0 |
| Project / task | 0 / 1 |
| Automation workflow projection | 0 |
| Telegram peer / update / delivery | 1 / 10 / 16 |
| Voice interaction | 3 |
| Meta/Google connection | 0 / 0 |
| Ads entity/metric/report/action | 0 / 0 / 0 / 0 |

## Phần đã hoàn thành và dùng được

- Auth local, workspace scope/RBAC, chat bền vững, SSE/reconnect/cancel và session archive.
- Ollama local, Chief, agent trace, Memory pgvector và Tool Gateway có approval/audit.
- Telegram polling với whitelist và delivery outbox.
- Projects/tasks/comments/activity ở backend và UI.
- 12 workspace route độc lập và shell điều hướng thống nhất.
- Meta/Google read-only contracts, warehouse, reporting, intelligence, approval,
  creative và attribution đã có mã nguồn cùng unit/integration test.
- Temporal durable workflow và Voice local.
- PAO AI có cuộn độc lập cho danh sách, chat, context và có xóa mềm hội thoại.

## Thứ tự sửa/triển khai đề xuất

1. Sửa planner fallback và thêm acceptance deterministic cho agent routing.
2. Cập nhật browser acceptance để phản ánh đủ 12 route, Javis catalog và PAO AI delete/scroll.
3. Kết nối Meta read-only bằng account thật, nghiệm thu dữ liệu và reporting trước mọi write.
4. Kết nối Google Ads read-only; triển khai TikTok backend sau khi hai connector đầu ổn định.
5. Hoàn thiện Javis theo thứ tự provider telemetry → Brain importer → skill registry →
   recurrence → fast-path canary → Zalo/Botcake.
6. Nâng chất lượng Voice và bổ sung benchmark latency/quality cho model local.
7. Hoàn thiện supervision, backup/restore drill, security audit và load test trước production.

