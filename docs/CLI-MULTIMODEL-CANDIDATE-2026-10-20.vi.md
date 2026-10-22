# Codex đa model và suy luận — nghiệm thu bản thử cách ly20/10

## Kết luận

Đã nối và kiểm thử **trên candidate cách ly** đường chọn tài nguyên → model/
suy luận theo hội thoại hoặc agent → snapshot → AccountingEngine → CLI dispatch
→ tham số transport. Không thêm runner, hàng đợi hay grant AI cá nhân.

**Chưa cài adapter dùng chung vào PAO đang chạy, chưa nghiệm thu quota thật.**
Schema chính vẫn0075/161bảng/API429; runtime, registry, hồ sơ đăng nhập và
cấu hình cũ giữ nguyên trong lượt này. Toàn đợt cơ cấu AI vẫn `in_progress`.

## Phần đã triển khai

- `packages/cli-runtime/candidates/installation-ai/backend/shared.py` tách
  nguồn CLI do quản trị bản cài giữ khỏi người gọi thực tế. Pin của volume/
  profile không bị đổi thành người dùng/SME của lượt chạy.
- Stager tạo bản nguồn riêng, dùng thay thế đúng một vị trí và từ chối nếu
  source đã lệch. Không có chế độ install. Backend đang phục vụ không import
  candidate; thư viện CLI đang phục vụ không bị ghi đè.
- Cấu hình qua API tài nguyên chung đi qua chốt danh tính. Chốt thật hiện
  luôn từ chối `installation_ai_cli_adapter_pending`. Test chỉ giả lập đúng
  danh tính nhà cung cấp tại chốt này; auth, role, SME, privacy, ledger, lease
  và kiểm tra SQL vẫn là code native.
- Model và effort của specialist độc lập với orchestrator; chat và profile
  gốc không đổi. Model ngoài catalog/effort không được công bố bị chặn trước
  dispatch. Nguồn cá nhân/grant cũ không được lén nhận model/effort mới.
- Candidate migration0076 chỉ ở cây staging, không nằm trong Alembic tree
  chính. Dispatch vẫn gắn attempt/workspace của người gọi, giữ khóa một
  dispatch chưa rõ kết quả cho mỗi profile và lịch sử bất biến.
- SQL kiểm tra resource/revision/catalog/effort, source profile/version/image,
  người giữ nguồn, người gọi, auth/lifecycle epoch, role và lease còn hoạt
  động. Lịch sử shared đã có dữ liệu chặn downgrade; không ép lịch sử về
  hình dạng personal cũ.
- Recheck trước gửi và trước trả kết quả. Hủy, thu hồi, nguồn bận hoặc cleanup
  chưa rõ không gây tự retry, fallback API trả phí hay trả kết quả trái quyền.

## Bằng chứng cuối

1. **220backend tests,0failure/error/skip**, bao gồm API cấu hình thực trong
   test, caller khác SME, operator/viewer, agent override, model/effort theo
   lượt, SQL guard, lease, hủy/thu hồi, lịch sử và tương thích Codex cũ.
   `.runtime/shared-cli-candidate-d01d6a256b644c1b81a6765d170e5219/receipt.json`.
   Đây là regression tập trung của candidate, không phải full backend mới.
2. Trên container PostgreSQL riêng: empty roundtrip0075↔0076; khôi phục backup
   đã kiểm SHA vào database clone rồi0074→0075→0076→0075→0076. Hash hàng cũ và
   cả3archive giữ nguyên. Không restore/migration primary. Container tự tạo
   đã xóa đúng ID/nhãn; dump và log giữ lại. Cùng receipt mục1.
3. **6/6ca binary Codex0.157.1 offline**: default, tool injection, High, Low,
   model A+High, model B+Low. Responder thật nhận hai ID và effort khác nhau;
   native không thực thi `apply_patch`, không có tệp bị tạo trái phép.
   `.runtime/installation-codex-protocol-c47778853b7748b4b6a0763404e56586/receipt.json`.
   Network-none/nonroot/readonly, không auth mount hoặc gọi OpenAI thật.
   Hai ID trong fixture không phải chứng nhận tài khoản được dùng hai model.
4. Image tái lập từ archive chính chủ đã ghim, build offline:
   `.runtime/p84-codex-image-4d308906b1544da890a540fa54bb7d66/image.json`.
   Image `sha256:3dd10065e179ca1c6fedb58a581191ca0f2980f243650df6e64fba1df7c7a10d`;
   candidate library `0bbdd1211e937d16f693f8d3801bf5cf9c032ddbddccbffc31d69223ef32be22`.
   Image này không phải image được chọn trong registry chính.
5. Phát hiện API/worker cũ đã thoát, log có Windows window-CLOSE. Preflight
   xác nhận PID cũ không còn, port trống, không worker/API không theo dõi và
   schema0075; khởi động đúng hai dịch vụ bằng cửa sổ ẩn, không dừng tiến trình
   lạ, không sửa Docker/schema/config. Log tại
   `.runtime/ai-service-recovery-efc30b63a96042c282d7ae36699d0ca8/`.
6. Sau phục hồi: API/ready/Web200, worker khỏe; source/live contract429 khớp,
   registry Codex hợp lệ, replay HTTP3/3 không chạy lại công cụ, dữ liệu chính
   không đổi trong lượt GET-only. Diagnostic bearer không phải owner consent.
   `.runtime/installation-ai-live-e2a0eb9a48634cb5875dd39b9dcdeb51/receipt.json`.

Giữ nguyên các failure trước: thiếu manifest trong stage, helper tạo Redis URL
bị che mật khẩu, fixture thiếu system message và helper giới hạn sai vị trí
dump. Đã sửa chuẩn bị test/fixture, không nới ACL/accounting/privacy hoặc khôi
phục dữ liệu chính để làm xanh. Receipt failure được giữ, không ghi lại thành pass.

## Phần còn lại và điều kiện mở tiếp

1. **Danh tính Codex dùng chung:** chưa có phương án được cấp quyền thực tế.
   Không suy ra tài khoản cá nhân đăng nhập một máy là danh tính cho mọi người.
   Không tự chuyển gói hoặc mua API. `shared.admit()` không có lối thành công
   production; không biến ACK khách hàng thành bằng chứng nhà cung cấp.
2. Sau khi có danh tính/phương thức được hỗ trợ, còn bước release riêng:
   checkpoint mới, idle/setup/dispatch gates, provision/auth hồ sơ đúng danh
   tính, chuyển pin host library/image/device/profile có rollback và xác minh
   lại nguồn. Không sửa/re-pin run hay lịch sử cá nhân cũ. **Executor chuyển
   pin và live admission chưa được triển khai/nghiệm thu trong lượt này.**
3. Sau release mới nghiệm thu model/quota thật, usage/cancel/revoke từ phiên
   owner thật và UI chat/agent/job. Không dùng diagnostic JWT để cấu hình,
   không coi fixture6ca hoặc220tests là bước nghiệm thu này.
4. Claude tiếp tục hoãn theo lựa chọn của user. Antigravity vẫn giữ chốt native
   tools60 của lượt trước; chưa có probe inference mới ở đây. Các adapter
   effort API ngoài OpenRouter vẫn chưa nghiệm thu. Không mở VPS/public/Ads.

Không chạy lại các baseline không đổi hoặc xây thêm runner vì các chốt trên.

## Tài liệu chính chủ đã đối chiếu20/10/2026

- [Codex App Server](https://learn.chatgpt.com/docs/app-server): model catalog,
  effort và auth. Tài liệu phân biệt local/open-source integration với dịch vụ
  thương mại/hosted; hướng thương mại được dẫn sang Sign in with ChatGPT, không
  được chứng nhận bằng việc tự dùng app-server OAuth của tài khoản cá nhân.
- [Service accounts](https://learn.chatgpt.com/docs/enterprise/service-accounts):
  danh tính phi con người cho shared integration/automation; hiện ghi điều kiện
  pay-as-you-go. Đây không phải quyền đã cấp cho PAO hay tự đổi gói tài khoản.
- [Codex iterative repair cookbook](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex):
  model và `model_reasoning_effort` là hai lựa chọn riêng. PAO chỉ truyền các
  mức model catalog đã công bố; không hardcode model trong ảnh chụp UI.
