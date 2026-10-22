# Stage L — Settings & Integrations

Route `/settings` là control plane chỉ hiển thị hoặc thao tác trên capability backend thật.

## Khu vực

1. General: tài khoản, workspace và role.
2. Integrations: Meta Ads, Google Ads, Telegram và trạng thái TikTok chưa triển khai.
3. AI & Voice: agent registry, local STT/TTS.
4. Safety & Approvals: provider write, autopilot và approval authority.
5. System Status: trạng thái tổng hợp các service.

Meta và Google OAuth dùng endpoint thật. Secret và biến môi trường không được trả về trình duyệt. Các cài đặt chưa có write API được hiển thị chỉ đọc.
