# S1.1 — Nghiệm thu local doanh nghiệp đang hoạt động

Ngày11/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`.
Trạng thái: **local_accepted**. Không phải nghiệm thu toàn S1 hoặc SaaS production.
Thiết kế tại [ADR-S11](ADR-S11-ACTIVE-ENTERPRISE.vi.md).

## Phần đã triển khai

- Read-only context API kiểm membership hiện hành, no-store,401/404; reuse schema
  Membership, không migration/bảng/JWT tenant claim mới. Contract308→309operations.
- Một activeWorkspace/role dùng chung; thay25consumer files từng lấy workspace
  đầu tiên. Orb/topbar/mobile sidebar có selector. Nhiều SME phải chọn rõ;
  preference lưu riêng theo user và chỉ khôi phục khi membership còn hợp lệ.
- Switch bỏ client session/draft/selected IDs, reset pending prompt và SSE view;
  generation fence loại JSON response scope cũ, không cancel/repin server run.
- Yêu cầu custom AI từng job đã ghi trong AGENTS/master/kế hoạch: S2 nền connection
  theo SME, S5.3 routing SME→brand→agent→step→job với privacy/capability/budget/
  fallback/approval/pins. Chưa triển khai routing nhiều model hoặc media adapter.

## Bằng chứng lượt này

| Gate | Kết quả |
|---|---|
| Backend focused | 67passed/0failed/0skipped,59.98s: tenant context,Task,Brain scopes,Engine,Chat management |
| Context sau thêm no-store | 3passed ở lần rerun riêng; anonymous/outsider/unknown,role riêng,revoked membership,brand parent |
| Pure frontend + runtime/SSE | 12passed/0failed/0skip:4tenant +8runtime/SSE |
| TypeScript | noEmit đạt; generated contract khớp source OpenAPI; ORM114 |
| Browser S1.1 | 1passed87.51s; HTTP/API/DB thật trên pao_test/Redis15, không fixtures trả JSON giả hoặc gọi LLM |
| Browser UI hồi quy | 12modules đạt qua verify_workspace_ui.cjs; đây là API fixtures, không nghiệm thu business thật |
| Production build | exit0,21/21static entries; .pao-build-check tách cache Web live |
| Live runtime | /health,/ready,Web3200 đều200; ARQhealthy; schema0048; context200/no-store,anonymous401/unknown404 |
| Live integrity | 309operations source/saved/live khớp; bindinge76a4db458aed99d20cbecd002c0a455ded25d6e443e49bdabc1c680de02c5f1; M2archives3/3read/replay |

Browser report:
`.runtime/s11-browser-ab37406a588040d7ac5c04a439a90aba/browser.json`
và screenshot`s11-mobile.png`. Chứng minh task/chat/Settings chọn SME B,role viewer
không kế thừa owner SME A,reload giữ B,tampered hint không fallback,mobile selector
và response taskA thật bị giữ trễ rồi release không xuất hiện ở SME B.
Không chạy lại full1156backend tests hoặc8browserP6/P7; evidence10/10 giữ nguyên.
Build còn warnings Hooks/pages lint config; không tắt lint để lấy pass.

## Backup và rollout

Trước restart checkpoint:
`.runtime/checkpoints/p0-20261011T083459-196f7617/manifest.json`,828source,
115physical tables,3archives,0048; basic verify và exact clone restore đạt.
Row hashes114business tables khớp,schema equivalent,primary unchanged.
Clone`pao_s03_restore_4ba113eba47d44adad6554b227ff6a8f`đã dọn,giữ dump/source.
Đây là source S1.1 trung gian,không được coi là archive có mọi fix/report cuối.

Chỉ restart API/ARQ đúng executable/command/start-time khi active jobs0;
API8224/worker23500 ở thời điểm rollout. Không dừng Docker/Web/Ollama.
Cold-start health probe đầu chưa thấyAPI; ready/Web200 và workerhealthy sau đó.
Rerun đầy đủ health đạt200,không restart lại hoặc nới health checker. Helper mới
có bounded startup wait,syntax checked; không chạy lại restart chỉ để test helper.

`.env`SHA256 giữ
`5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
Không đổi credentials/gates/primary rows/schema,không gửi social/Telegram,chạy Ads,
chi tiền hoặc public deploy. Giữ protected Apex/Javis và dirty changes có trước;
không Git commit/push/reset.

## Các lỗi đã xử lý và giới hạn

- Browser mobile ban đầu timeout vì chờ visible session rail vốn CSSẩn; đổi
  sang kiểm response SME đúng,selector và DOMattached. Giữ mọi isolation assertions.
- Selector đặt trong session strip làm overlap Orb nav; tách dropdown xuống
  hàng riêng,giữ tên SME/logout và chạy lại12module layout assertions đạt.
- Raw Response/body/blob,SSE đang chạy,tab/cache/membership refresh là S1.2;
  worker/outbox/files/exportnegative corpus là S1.3. Không tuyên bố hoàn tất cả S1.
- M3/live providers,P7.5real mic/channel,remote CI/reboot/offsite/production vẫn mở.
- Old exact-binding job pins không tự đổi theo backend mới; không sửa snapshot
  để ép thực thi lại. Read-only archive replay khác re-execution compatibility.

**Việc tiếp theo duy nhất: S1.2 — scope của cache/SSE/in-flight/raw response khi chuyển SME.**

## Checkpoint cuối đã verify

`.runtime/checkpoints/p0-20261011T084533-8078c0b6/manifest.json`:831source,
115physical tables,3archives,0048. Basic manifest/hash verify và exact clone
restore đều đạt; row hashes114business tables khớp,schema equivalent,primary
unchanged. Clone`pao_s03_restore_68e5b24a482f4bfdbe34ed1020574a15`đã dọn;
giữ source/dump. Sau checkpoint chỉ thêm dòng evidence này và đính chính một
dòng snapshot tenant audit trong kế hoạch; không đổi code/contract/binding.
Archive không được mô tả là chứa chính dòng self-reference này.
