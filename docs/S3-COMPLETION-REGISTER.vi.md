# S3 — Telegram nhiều bot, sổ checkpoint

15/10/2026, `F:\PAO-ACOS`. Master roadmap sở hữu thứ tự. S2 đã đóng local;
không bắt đầu lại S2 hoặc coi schema namespace là transport nhiều bot đã chạy.

**Mốc hiện hành16/10:** [S4 cũng đã local_accepted](S4-COMPLETION-REGISTER.vi.md),
primary0065/live353; tiếp theo S5 theo master. Các số và câu “tiếp theo S4”
trong sổ S3 này thuộc mốc đóng S3 ngày15/10, không phải thứ tự hiện tại.

**Toàn S3.1–S3.3 local_accepted15/10:**93focused/109Node/TypeScript/build21/
browser tích hợp đạt. Backend2078ca có kết quả cuối đạt: full2077/1lỗi allowlist
script phục hồi, sửa script rồi27retry đạt, backend không đổi; không full rerun.
[Báo cáo hiện hành](S3-INTEGRATION-2026-10-15.vi.md). Primary0064/live349,
134physical/3archives;API/ready/Web200,current binding/replay3/3, không bot thật.

| Checkpoint | Trạng thái | Gate |
|---|---|---|
| S3.1A namespace foundation | local_accepted14/10 |1709backend/0fail/0skip,25namespace/44focused,4browser/80Node,0059/live334/current binding/exact restore; [evidence](S31A-LOCAL-ACCEPTANCE-2026-10-14.vi.md) |
| S3.1B explicit legacy mapping | local_accepted15/10 |1737backend/0fail/0skip,5browser/96Node/build21;0060/live338/current binding/exact restore; [evidence](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md) |
| S3.1 tổng | local_accepted15/10 |A+B đạt; storage/explicit consent, chưa resolver/transport nhiều bot |
| S3.2 bot-specific runtime | local_accepted15/10 |A/B/C tích hợp, regression/migration/live/replay đạt theo báo cáo tổng |
| S3.2A scope/lease/metadata kernel | local_accepted qua tích hợp tổng15/10 |Mốc source trước có143focused/52kernel; [evidence lịch sử](S32A-KERNEL-2026-10-15.vi.md); nay đã nối API/worker và nạp trong0064 |
| S3.2B durable profiles/cursor/ingress/outbox | local_accepted qua tích hợp tổng15/10 |Mốc source trước có368affected/41scoped+25Node/candidate0063 roundtrips; [evidence lịch sử](S32B-SCOPED-EXECUTION-2026-10-15.vi.md); nay đã tích hợp C/Settings và rollout0064, không gửi thật |
| S3.2C bridge/webhook/report integration | local_accepted15/10 |Polling/sender/worker/webhook/mode/report/oversize/idle-week/generation revoke đã tích hợp và kiểm thử; [tích hợp](S3-INTEGRATION-2026-10-15.vi.md) |
| S3.3 Settings/setup | local_accepted15/10 |Token/getMe/mode/pairing2phase/team grants/Brain immutable/status/disconnect và hướng dẫn/Việt hóa Cài đặt đã rollout; browser API/PG thật/provider giả lập đạt |
| Live/production | external_pending |Bot/đích được owner cấp, tin thử vô hại, HTTPS/reboot; chưa bật hoặc kết nối thật |

Toàn S3 đã đóng local, **bước kế tiếp là S4**, không triển khai lại
store/identity/admission/outbox/mapping hoặc coi Settings/team chưa bắt đầu.
Primary0064/live349/bindingc44d27b2,134physical/3archives khớp source;
checkpoint trước migration và kiểm phục hồi cuối giữ trong `.runtime/checkpoints`.
Không tự
chọn SME để map bot host; không yêu cầu secret trong chat. Nếu chưa có bot,
fixture đủ cho code/DB gates; không đánh dấu live acceptance.

Yêu cầu15/10 đã có code/fixture/browser evidence trong báo cáo tổng; chưa dùng
kết quả này để gọi live/production đạt. Bot thật và tin thật vẫn cần phạm vi
được cấp phép; không yêu cầu người dùng gửi token qua chat.
