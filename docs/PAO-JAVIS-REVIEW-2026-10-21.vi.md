# Đối chiếu PAO–Javis phục vụ roadmap ngày21/10/2026

Tài liệu tham khảo/thiết kế, **không phải roadmap thứ hai**.
Thứ tự và trạng thái triển khai do [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu.

## 1. Phạm vi thực sự đã khảo sát

- Trực tiếp tab **Chrome / Javis OS / http://localhost:7777/** ngày21/10/2026.
  Giao diện và `G:\Javis\VERSION` cùng ghi **0.204.0**; không dùng phiên bản0.78.0 từ ghi nhớ cũ.
- Đọc UI/navigation, mở menu model/effort và các mục dưới đây; chỉ điều hướng,
  không bấm Kết nối/Ngắt/Lưu/Test/Gửi/Cài/Chạy/Cho phép và không đổi model/effort.
- Không gửi chat, gọi quota, kích hoạt bot, nhập credential, chạy terminal hoặc cài plugin.
  Không chứng nhận DB/settings Javis bất biến: ứng dụng có thể tự ghi telemetry/trạng thái nền.
- Đọc mã nguồn chọn lọc tại `G:\Javis`: ARCHITECTURE.md, VERSION, LICENSE,
  server/antigravity_cli.py, claude_cli.py, codex_models.py, claude_sdk_engine.py,
  aux_engine.py, chat_runtime.py và dashboard/model-picker.js.
- Đối chiếu PAO: app/router/module inventory, installation_ai/service.py,
  business_planning/routing.py, cli_connections/antigravity_native.py,
  goals/api.py và runner_api.py, core_api.py, runtime.py, memory.py,
  usePaoRuntime.ts, launcher và các receipt hiện hành.
- Đây là khảo sát **các khu vực chức năng chính và các đường nối liên quan**, không phải đọc
  từng dòng toàn repo Javis, pentest, hay nghiệm thu tất cả connector/tính năng của Javis.
  Các hội thoại cũ trên Javis chỉ là nội dung người dùng/model, không phải bằng chứng runtime.
- Lượt này chỉ thay tài liệu PAO. Audit hệ thống ngay trước đó cung cấp snapshot0075;
  không chạy lại full regression hoặc tác động DB/provider để viết roadmap.

## 2. Những gì thấy trực tiếp trên Javis

| Khu vực UI đã mở | Quan sát | Giới hạn của bằng chứng |
|---|---|---|
| Hội thoại | Lịch sử/thư mục, tìm kiếm, chat, nút tệp/lệnh/kết nối, model/effort gần ô nhập; tên phiên/model pin có chú giải | Không gửi câu hỏi mới hoặc kiểm hồi đáp thật |
| Menu model | Nhóm theo provider, tìm kiếm; Codex hiển thị7lựa chọn, các nguồn chưa nối có chỉ dẫn | Số lựa chọn không đồng nghĩa7model đều được quota thật |
| Menu effort | Chip High mở dialog/slider Faster–Smarter | Không đổi slider; chưa kiểm payload provider trong lượt khảo sát |
| Models | Thẻ main/provider, model việc nền, model Telegram và trạng thái riêng | Codex Plus7, Antigravity6, OpenRouter50 là UI status/catalog, không live inference mới |
| Skills |6kỹ năng bật, nhóm AI/Marketing, import/tạo, thư viện hệ thống | Không sửa/chạy skill hoặc coi số lượng là chất lượng |
| Cộng sự | Agent hệ thống, tài liệu, chat riêng và lựa chọn model/effort | Không tạo/gọi agent |
| Quy trình | Tab quy trình riêng, import/tạo; danh sách đang trống | Không có workflow thực tế để nghiệm thu |
| Team | Mô tả leader, @mention và giao việc trong chat | Trang khởi tạo; không có bài chạy team thật |
| Chatbot/hòm thư | Bot/inbox riêng, lọc bot/trạng thái/nhóm, takeover;0hội thoại | Chưa xác minh bot thật hoặc handover |
| Việc | Dispatcher, worker/queue/exception/history, nút giao goal/pause | UI báo tối đa2workers nhưng không có task; chưa nghiệm thu dispatch |
| Việc định kỳ | Tách Việc/Sự cố/Nhật ký; loop/nhắc hẹn và scope brain | Chưa có lịch; không bấm chạy/dừng |
| Webhook | Mô tả event → workflow/job, một danh sách riêng | Chưa có webhook; không tạo secret/callback |
| Kết nối | Đã nối / sẵn có / store, nhiều tài khoản/dịch vụ, cổng dùng chung các engine | Botcake hiển thị1kết nối; không gọi dữ liệu hoặc gửi tin |
| Catalog connector | Nhóm kho ứng dụng/nhắn tin/văn phòng/marketing/Ads/bán hàng; hướng dẫn auth | Template/beta không đồng nghĩa kết nối đã hoạt động |
| Kênh Admin | Tách khỏi bot chăm khách; tabs Telegram/Zalo/Lark/Discord/Slack/WhatsApp; setup theo bước | Không lưu/bật/gửi test; không ghi lại giá trị credential trong báo cáo |
| Kho tệp | Theo brain; tìm tên/nội dung, upload/download, file/folder actions | Không tải/xóa/sửa nội dung |
| Đồ thị | Màn tri thức riêng và brain đang chọn | Không benchmark graph lớn hoặc kiểm ACL đa tenant |
| Tự học | Memory/wiki/skills, chế độ đề xuất/tự ghi, log/undo và backup Git tùy chọn | Không bật/tắt/học/sync; chưa nghiệm thu chống poisoning |
| Công cụ/plugins | Tool dùng chung qua hub; mô tả quyền tối thiểu, trạng thái, optional browser | “Đang chạy” là trạng thái plugin, không chứng minh provider có quyền và gọi được |
| Cài đặt | Nhãn hiệu/ngôn ngữ/theme, domain/SSL, autostart và cấu hình nâng cao | Không thay cấu hình máy hoặc cài tự khởi động |
| Coding | Nhóm riêng, khung chat/model/effort | Không mở shell/chạy code, không bind dự án hay đọc folder tùy ý |
| Store | Catalog hiển thị4trợ lý/24skills/4quy trình/4công cụ/41kết nối; có nhóm bán hàng, xã hội, marketing, sáng tạo, văn phòng, website và trạng thái cập nhật | Đây là mục trong kho, không phải số connector đang hoạt động; không cài/update, chưa audit supply chain mọi gói |

**Kết luận:** Javis có nhiều hành trình được nối và trình bày gọn hơn PAO ở khu vực AI/công cụ.
PAO có nền multi-SME, versioned approval, business ledger/contract/restore riêng cần giữ.
Không kết luận toàn Javis đã hoạt động thật hoặc an toàn hơn chỉ qua các màn hình này.

## 3. Các thiết kế nên học và cách đưa vào PAO

| Thiết kế Javis | PAO cần làm | Giai đoạn |
|---|---|---|
| Một engine event contract cho các nguồn AI | Registry/resolver/adapter chung; Chat, agent, job, report cùng dùng | GD01 |
| MCP Hub dùng chung CLI/API | Tool Gateway native PAO là authority; adapter CLI không tự mang tool ngoài scope | GD01/06 |
| Main / background / Telegram model | Mặc định cấp bản cài/SME; chat/agent/step/job/channel override có pin | GD01/05/09 |
| Model picker tìm kiếm theo provider | Một component/catalog/capability dùng khắp PAO, không mỗi trang một list hardcode | GD01/03 |
| Effort gần model | Chỉ hiện mức provider/model hỗ trợ, truyền adapter thật, minh bạch chi phí/độ trễ | GD01 |
| Phiên native nhận qua một nút | Backend doctor phát hiện binary/login đúng OS user; consent chính chủ khi cần | GD01/03 |
| Job server-side, browser chỉ subscribe | Reuse native run/attempt/queue; nhiều tab nhận trạng thái, đóng tab không mất việc | GD02/05 |
| Fan-out có backpressure | Replay/snapshot/dedup bounded; tab ngủ không chặn mọi user | GD02 |
| Incident/exception một nơi | Inbox lỗi có correlation, nguyên nhân, retry/stop đúng run; không “thử lại” toàn hệ thống | GD02/05/10 |
| Skills/agents/workflows có import và khu vực riêng | Tái dùng Studio versioned; nhóm nghề và assignment, không tạo kho song song | GD04 |
| Brain sources/wiki/memory rõ | Giữ authority DB/file version/ACL của PAO, projection/export Markdown | GD04 |
| Tool giao việc/lịch/đọc lịch sử từ Chat | Gọi native service bằng tool có schema; API engine và CLI có cùng nghiệp vụ | GD05 |
| Connector phân nhóm/multi-account | Settings per-provider/SME; card status, hướng dẫn và chọn đích; không mượn CLI credentials | GD03/06 |
| Admin channel tách chatbot khách | Giữ PAO member identity; bot customer không thành operator | GD09 |
| Tự học có log/undo | Proposed diff/publish/revert phiên bản, giới hạn phạm vi | GD04/05 |
| Optional tools/dependencies | Không cài Ollama/media/voice/Temporal nếu không dùng | GD03 |
| Backup và update nhìn được trên UI | Checkpoint/restore evidence rõ, keys/blobs bảo vệ riêng | GD00/03/11 |

## 4. Những gì không sao chép nguyên trạng

1. **SQLite/JSON/Markdown không thay PostgreSQL của PAO.** Đổi storage không giúp tự có
   UX dễ dùng, còn có thể làm mất transaction/tenant boundary/ledger hiện tại.
2. Không gom toàn bộ module vào một main.py lớn. Javis architecture ghi main khoảng20.000dòng;
   PAO cần giữ module ownership và extract các file lớn theo test, không đổi lõi hàng loạt.
3. Không copy default full quyền cho loop hoặc CLI sandbox-bypass. Source Codex Javis có
   nhánh `--dangerously-bypass-approvals-and-sandbox`; không dùng làm chuẩn triển khai PAO.
4. Không port engine fallback tự chọn nguồn khác khi chưa có consent/budget.
   PAO phải cho biết nguồn, model và ai trả tiền; quota lỗi không được lặng lẽ thành API bill.
5. Không lấy “đọc catalog thành công” làm inference readiness. Trong Javis
   `server/antigravity_cli.py:841–872`, auth_status lấy list_models và trả connected nếu có danh sách.
   Điều này giải thích UX nhận Client nhanh, nhưng không chứng minh lời nhắc đã được xử lý.
6. Không port mọi tool quyền toàn máy vào phiên khách/SME. API/CLI cùng dùng Gateway không có
   nghĩa cùng thấy mọi tài nguyên; context và tool policy phải lọc trước execution.
7. Không áp dụng một slider effort chung bằng tên hoặc prompt khi native provider không nhận.
   Tính năng effort cần capability và evidence theo model/version.
8. Không tự Git-sync nội dung mọi SME/khóa/media lên một repo; export/backup có scope và chính sách riêng.
9. Không hứa tạo ảnh/video bằng quota chat chỉ vì Javis có plugin đó; kiểm supported surface,
   loại tài khoản, công cụ và quyền sử dụng trước.
10. Không copy license notice thiếu provenance. Root Javis LICENSE là MIT21/10, nhưng dependency,
    dịch vụ, credential, model và thương hiệu có điều kiện riêng. Lượt này không port code Javis.

## 5. Tài liệu provider đã kiểm tra lại ngày21/10

Đây là ràng buộc thiết kế kỹ thuật/sản phẩm, không thay cho tư vấn pháp lý hoặc hợp đồng riêng.

| Nguồn | Điều kiểm chứng và tác động vào kế hoạch |
|---|---|
| [OpenAI plan usage](https://developers.openai.com/siwc/token-sharing-open-source) | Có hướng OAuth cho app open-source/local, host/client tách biệt; paid/remote cần đăng ký quan tâm. Vì vậy phải đánh giá lại lựa chọn tích hợp thay vì giữ kết luận cũ “luôn cần pay-as-you-go”; chưa chứng minh PAO đủ điều kiện hay1login phục vụ nhiều người |
| [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server) | Có protocol app-server/stream/resume; danh mục model không phải entitlement. Candidate PAO có thể kế thừa, nhưng cần kiểm account và lượt inference thật |
| [OpenAI preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) | Đường plan usage có giới hạn tools/input/history, không image generation trên surface này; route media cần đánh giá riêng |
| [Claude Code authentication](https://code.claude.com/docs/en/authentication) | Có nhiều nguồn auth và thứ tự ưu tiên; biến API key có thể làm đường trả tiền khác với login. PAO cần hiển thị credential source và không tự chuyển billing |
| [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview) | Official SDK hoặc CLI subprocess là các đường nhúng cần đánh giá. Chưa có thuê bao của user nên không làm Claude live hoặc khẳng định mọi quyền thương mại/đa người đã đạt |
| [Antigravity FAQ](https://www.antigravity.google/docs/faq/) | Google nói consumer plan không hỗ trợ wrapper CLI trong ứng dụng/coding agent bên thứ ba. UI Javis không thay thế điều kiện này; native Antigravity dùng MCP PAO là hướng khác, chưa phải provider trong Chat PAO |
| [Antigravity permissions](https://www.antigravity.google/docs/permissions?tab=cli) | Native tools/permissions phải đo theo binary và OS; không xóa chốt isolation để có một câu trả lời rồi gọi là an toàn |

Không gọi OAuth token endpoint, đọc keyring, mở rộng quyền, gửi prompt hoặc thử quota trong khảo sát này.

## 6. Các gap PAO cụ thể cần ưu tiên, không làm lại lõi

- Shared CLI `installation_ai/service.py:61` và API còn báo adapter_pending.
- Agent/step routing đã có nhánh installation resource, nhưng legacy actor grants còn tồn tại:
  hợp nhất UX/resolver mà giữ backward compatibility và kiểm scope tại worker.
- Antigravity status native `inference_enabled:false`, smoke60tools trước prompt chưa đạt.
- Goal admission/runner API hiện `model_calls:false`/dry-run: phải nối đúng execution path,
  không coi8cờ nội bộ mới là mục tiêu tự chạy.
- Chat SSE có cursor/replay và4lần reconnect; không chứng minh providers/tasks/approval/report realtime.
- Worker hiện1job, dispatcher10giây; cần đo độ trễ/fairness trước tăng concurrency.
- `memory.py` còn extraction default Ollama, launcher bắt buộc Ollama runtime:
  muốn Ollama optional phải tách dependency và capability thật.
- Launcher `start_acos_local.ps1:22` chạy migration0075, chưa enforce checkpoint cho schema mới.
- Installed source hiện hành khác baseline hosted CI cũ; cần current release evidence ở GD10,
  không chạy full lại chỉ để viết kế hoạch.
- Các gap CRM/media/TikTok/các kênh và production theo master, không gộp tất cả thành blocker AI.

## 7. Ghi nhận thay đổi tài liệu

- Master cũ được sao lưu nguyên byte trước thay thế; hash có trong master mới.
- Master mới sở hữu thứ tự GD; M/P/S/EA giữ làm mapping và receipt lịch sử.
- Không chỉnh backend/frontend, .env, schema, process pins, provider settings hoặc dữ liệu nghiệp vụ.
- Không coi trạng thái tài liệu “planned” là thay đổi feature gate; không cài candidate0076.
- Checklist links/ID và integrity file bảo vệ được kiểm sau khi viết tài liệu.

