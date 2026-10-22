> Hồ sơ Phase 0/1 trước khi đổi tên sang PAO. Tên APEX và đường dẫn dưới đây phản ánh thời điểm triển khai; xem [đổi tên PAO](REBRAND-PAO.md) và [hướng dẫn hiện tại](LOCAL-DEVELOPMENT.md).

# Phase 0 — Baseline và đối chiếu lộ trình

## Trước khi triển khai

Nguồn yêu cầu: Master Implementation Specification do người dùng cung cấp ngày 10/09/2026. Yêu cầu hiện tại chỉ bao gồm Phase 0 rồi Phase 1, tuần tự; không Ads, Telegram, Memory hoặc Autopilot.

Hiện trạng trước turn này: archive UI gốc và ba tài liệu phân tích tại `F:/Apex/docs`; chưa có backend, migrations hoặc kiểm chứng build. Không đánh dấu các tài liệu kế hoạch là chức năng đã triển khai.

Kế hoạch Phase 0: clone có lịch sử vào `F:/Apex/apex`; tạo nhánh `architecture/phase-0-1`; cài theo lockfile bằng `npm ci` (tái lập chặt hơn `npm install`); chạy build và ứng dụng; ghi cấu trúc component và kết quả. Chỉ sau baseline pass mới thay cấu trúc/thêm code Phase 1.

File thay đổi: chỉ tài liệu `docs/PHASE-0-*.md` trong Phase 0, ngoại trừ sửa baseline nếu phát hiện lỗi chặn build và ghi rõ. Database: chưa thay đổi. API: chưa thay đổi.

Rủi ro: Git đi kèm thiếu HTTPS helper; đã dùng Dulwich để clone Git thật, giữ commit upstream. Docker CLI có nhưng chưa thấy daemon; chưa có Ollama trên PATH. Những điểm môi trường Phase 1 này không được che bằng mock rồi tuyên bố luồng LLM thật đã đạt.

## Đối chiếu kế hoạch cũ với đặc tả mới

| Nội dung | Kế hoạch cũ | Quyết định theo đặc tả hiện hành |
|---|---|---|
| Mục tiêu | Trợ lý local cho nhóm nhỏ | Giữ local; đích dài hạn thêm Advertising OS theo phase riêng |
| Backend | FastAPI riêng, một model dùng chung | Giữ |
| Queue | PostgreSQL queue | Redis + ARQ; PostgreSQL giữ run/event và phục hồi trạng thái |
| Auth | Opaque session | JWT; không dùng Supabase cloud mặc định |
| API prefix | `/api/v1` | `/v1` |
| Dữ liệu hội thoại | conversations | sessions; auth token tách khỏi session hội thoại |
| Repository | Backend dưới UI | `apps/web`, `apps/api`, `apps/worker`, `packages/contracts` theo từng bước |
| Brand isolation | Scope mở rộng về sau | Đặt workspace/brand context nhất quán từ foundation, chưa dựng Ads schema |
| Memory/tools/voice | Đưa tương đối sớm | Theo số phase của master; không xây trong Phase 1 |
| Provider | Ollama local | Giữ phù hợp yêu cầu phần cứng; gateway boundary |
| Runtime frontend | P1 trong kế hoạch cũ; P2 ở mục 128 | Mục 153 yêu cầu hook/Orb và một Chief ngay acceptance đầu: chỉ làm cầu nối tối thiểu trong P1 |

Mục 137 yêu cầu Meta write ở Copilot trong khi mục 138 mới ghi phase approval UI. Khi tới đó, tuyệt đối không bật write trước khi cơ chế approval từ Phase 5 đã hoạt động. Hiện chưa triển khai các phase đó.

Sơ đồ component hiện tại: `app/page → ApexOverviewPanel + ApexWorld`; `ApexWorld → ReasoningWeb + ShaderBackground + ApexHeroOrb + OrbStatusBar + AgentOverview`; `ApexHeroOrb → ApexOrb + ApexCore3D`. State demo ở ApexWorld, roster/info static; API duy nhất là weather. Giữ nguyên các visual component trong baseline.
