# Codex — Sửa chọn model và triển khai lại local

Ngày20/10/2026. Nguồn và bản cài `F:\PAO-ACOS`; backup001 giữ nguyên.

**Cập nhật tiếp nối:** người dùng đã đăng nhập lại; UI đọc/chọn/lưu model và
consent đã đạt, một native job thật trả `PAO_CODEX_OK` với hai attempt completed.
Xem [nghiệm thu sau sửa](CODEX-NATIVE-LOCAL-ACCEPTANCE-2026-10-20.vi.md).
Các trạng thái pending bên dưới là lịch sử thời điểm cài bản sửa, không phải
gate đăng nhập/job còn thiếu ở hiện tại.

## Kết quả và chốt còn lại

**Đã cài bản sửa code local; chưa nghiệm thu native job thật sau sửa.** Người
dùng yêu cầu “Hãy tự sửa và triển khai lại” sau khi được thông báo rủi ro ghi
profile. Đã thực hiện đúng một diagnostic inference ngắn và một đọc danh mục;
không copy token, đổi tài khoản, lấy khóa API hoặc fallback trả phí.

Phiên PAO trên trình duyệt hết hạn. Đã nhờ đăng nhập lại trong khi tiếp tục
kiểm thử/cài đặt. Không tự phát hành JWT để POST, sửa model/consent bằng SQL,
đoán mật khẩu hoặc bypass phiên đăng nhập nhằm đóng gate thật.

Cuối lượt đọc: profileconnected/v5, model vẫn `gpt-6.1-sol`, personalpolicy
revision1/bật. **Cấu hình thực tế chưa chuyển sang model được hỗ trợ**. Không
tuyên bố người dùng đã chat được chỉ vì code/build/health đạt.

## Nguyên nhân đã xác định

Diagnostic cùng binary/image/profile và cấu hình text-only như native worker:
`thread.started` → `turn.started` → `error` → `turn.failed`, exit1, HTTP400,
phân loại `model_unavailable` + `invalid_request`,6.22s. Đây là bằng chứng
model đang cấu hình bị từ chối, không phải giả định từ lỗi chung hoặc lỗi
Ollama. Không xuất raw provider body, auth cache, email/tokens hoặc reasoning.
Không có usage thành công: quota đã tiêu vẫn chưa xác định.

Qua RPC chính thức `account/read` + `model/list`, xác thực ChatGPT hợp lệ;
danh mục trả6model, `gpt-6-astra` mặc định, không có `gpt-6.1-sol`. Các model
khác: `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`.
Danh mục không bảo đảm quota/entitlement/inference; không hardcode danh sách
này trong sản phẩm. Các container diagnostic đã tự dọn; volume/profile giữ lại.

## Bản sửa đã cài

1. Hai API POST theo đúng chủ hồ sơ và workspace: `.../cli-connections/{id}/models`
   đọc danh mục; `.../cli-connections/{id}/model` đổi model có xác nhận/version.
   Không nhận executable, RPC, token hoặc argv từ HTTP. Chỉ model/default được
   xuất ra, giới hạn100model, từ chối phân trang chưa hỗ trợ hoặc DTO bất thường.
2. Tái sử dụng LoginTransport và durable `setup_operation_id` để khóa profile,
   chặn dispatch đang chạy/unknown. Recheck session, membership, owner, runtime
   pin và source trước/sau I/O. Cleanup không xác minh được giữ fence, không
   đoán là profile rảnh. Không thêm queue/runner/schema hoặc auth importer.
3. Đổi model đọc lại danh mục, tăng source version, không sửa pin/consent/job/
   hội thoại cũ. Personal policy cũ hết ready; chủ sở hữu cần Lưu lại thiết lập
   và mở chat mới. Request/version cũ bị409, không replay vô hạn sau lost ACK.
4. UI **Dùng Codex cho tôi → Chọn model từ Codex**: đọc danh mục, mã đang lưu,
   dropdown, dấu mặc định Client, xác nhận và Lưu rõ ràng. Phản hồi muộn theo
   SME/actor/connection bị bỏ; ACK chưa rõ khóa Lưu tới khi đọc lại. Hướng dẫn
   tiếng Việt, phân biệt đọc/lưu với inference và quota.
5. Audit adapter phát hiện `CliGateway.plan` chưa thay Chief system prompt bằng
   planner instructions/schema như gateway API. Đã thêm PLANNER_PROMPT, schema
   ExecutionPlan và yêu cầu raw JSON; JSON sai vẫn `cli_plan_invalid`, không
   giả kế hoạch thành công. Đây là sửa lỗi code có test, chưa phải lỗi đã được
   quan sát qua model được hỗ trợ trong lượt thật sau sửa.
6. Chat mới dùng personal Codex default không tự bật legacy memory khi request
   chưa opt-in. Tránh job trích xuất/Ollama ngầm; request opt-in rõ và chat cũ
   giữ nguyên. Không tuyên bố đã xóa Ollama hoặc hoàn tất P8.4-D/Knowledge.

## Kiểm thử và triển khai

- Candidate source-only1501file, backup `before-source.zip`, hash/preimage giữ lại.
- Backend đầu409/409 đạt. Sau bổ sung planner/memory default, lượt cuối độc lập
  **413passed,0failure/error/skip,248.05s**,6ARQ deprecation warnings có sẵn.
- **209Node**, TypeScript/typegen/build23trang đạt; declaration được typecheck
  và so hash riêng trước promotion. Frontend không đổi giữa proof build và cài.
- Đã cài đúng13file gồm backend/UI/tests/contracts; không cài dependency,
  đổi `.env`, runtime pin, CLI library/binary/image hoặc registry.
- **Schema0074/159bảng/423API**, không có schema migration mới. Sau cài ngay:
  hash các bảng cũ nguyên vẹn,3archive giữ hash, readonlyHTTP replay3/3;
  API health/ready/Web200, worker chạy. Snapshot này trước thao tác đổi model
  dự kiến, không phải cam kết primary đứng yên cả phiên.
- Không restore primary, xóa dữ liệu/volume, reboot, commit/push hoặc deployVPS.
  Không gọi các bài focused là full backend regression hoặc nghiệm thu toàn S6.

Giữ lịch sử rollout: gate đầu dừng trước mọi sửa nguồn vì còn Windows console
host ngoài Python child; xác minh đúng conhost hệ thống rồi giữ nguyên chúng.
Lượt sau gặp race launcher tự thoát khi Python child dừng; helper finally khôi
phục API cũ, worker cũ được giữ/khởi động đúng identity. Hai lần snapshot tiếp
theo khớp snapshot đã lưu trước restart. Sau xử lý HasExited/race “process not
found”, promotion đạt. Không bỏ kiểm tra exe/start-time/command, không kill
process lạ; kiểm tra sau cài mới là bằng chứng hệ thống phục hồi.

## Nghiệm thu còn cần làm sau đăng nhập PAO

1. Cài đặt và kết nối → AI và giọng nói → Kết nối qua Client → Dùng Codex cho tôi.
2. Đọc danh mục; chọn model Client hỗ trợ. Dự kiến dùng mặc định Client
   `gpt-6-astra` cho bài thử nhỏ, không phải silently đổi model job đã ghim.
3. Xác nhận/Lưu model; xác nhận/Lưu lại thiết lập cá nhân; tạo chat mới.
4. Tối đa một native test job ngắn, không business data, Brain/knowledge/tools
   hoặc legacy memory. Planner và final answer có thể là hai lượt suy luận
   trong cùng job; không gọi đó là một lần inference. Không automatic retry.
5. Chỉ khi Run/LlmAttempt/CliModelDispatch, phản hồi và usage/cleanup phù hợp mới
   đóng live gate. Token null vẫn unknown; usage không phải quota còn lại.

Live UI mới/chọn model/lưu consent và job sau sửa **pending authenticated owner
session**, không được suy từ build hay fixture. EA2.2/sharedCLI, EA3,
P8.4-D toàn phần, owner pilot và production vẫn chưa được nghiệm thu.

## Bằng chứng

Trong `.runtime/codex-repair-20261020/`:

- `diagnostic.json`, `catalog.json`, `before.json`, `before-source.zip`.
- Backend cuối `check-11186d1f77ef44f18c1ad42a3ce5def8/receipt.json` và JUnit.
- Backend409 trước planner `check-0ca28456822c42c09775d8ed1db3ad5b/receipt.json`.
- Frontend `check-486a62d058314fa6ae5ac266ee9170ac/receipt.json`.
- `source-plan.json`, `source-before/`, `install-before.json`, `installed-check.json`.
- `final-profile-state.json`, API/worker logs; helper guarded không replay
  diagnostic khi receipt đã có. Các helper là công cụ vận hành, không runner AI.

Đã đối chiếu [OpenAI Authentication](https://learn.chatgpt.com/docs/auth) và
[Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
ngày20/10. Ưu tiên quyền gói thuê bao chính chủ; không tự chuyển cách tính phí.
