# Codex — đăng nhập từ giao diện PAO

Ngày: 19/10/2026. Phạm vi: P8.4-C/E local cá nhân, không phải SaaS/production.

## Trạng thái hiện tại

Backend và giao diện đăng nhập **đã cài vào PAO đang phục vụ**, kiểm tra cài đặt đạt. Sau đó người dùng đã thực hiện đăng nhập: metadata profile Codex được chọn ghi nhận **connected, version5, auth_recorded=true, operation_pending=false**. Đây là kết quả đăng nhập, chưa chứng minh quyền model/quota/inference. Schema 0072, 155 bảng, hợp đồng 416 API. API/ready/Web trả 200, worker khỏe, dữ liệu cũ nguyên hash và 3 HTTP replay chỉ đọc đạt tại kiểm tra ngay sau cài. Python pin và CLI registry không đổi. Không có inference, grant hoặc job thật được trợ lý chạy.

## Luồng sử dụng trên bản cài

1. Đăng nhập PAO bằng tài khoản có quyền chủ doanh nghiệp/quản trị viên; chọn đúng doanh nghiệp.
2. Mở **Cài đặt và kết nối → AI và giọng nói → Nhà cung cấp mô hình → Kết nối qua Client → Codex → Kết nối**.
3. Nếu đã có đúng một hồ sơ riêng, PAO dùng lại ID đó, không tạo bản sao; xác nhận đăng nhập cá nhân. Nếu có nhiều hồ sơ thì chọn rõ; nếu chưa có hồ sơ thì cần mã model và xác nhận tạo trước. Lưu mã model không xác minh entitlement.
4. PAO chuẩn bị profile riêng và bắt đầu luồng mã thiết bị bằng Codex chính thức trong Docker. Mở trang OpenAI từ hộp thoại, đăng nhập/kiểm tra tài khoản của bạn và nhập mã một lần. Không nhập token hoặc mật khẩu PAO vào PowerShell; không gửi mã cho trợ lý trong chat.
5. PAO tự đọc kết quả. **Đã ghi nhận đăng nhập Codex** chỉ là kết quả đăng nhập profile: chưa nghiệm thu quota, quyền model, suy luận hoặc job thật. Quyền dùng mô hình và công cụ vẫn phải được cấp/kiểm tra riêng.

Điều kiện: Docker và runtime Codex được quản trị vận hành cài/pin; cổng `CLI_BROWSER_LOGIN_ENABLED` mặc định **false**, chỉ bật có chủ đích cho local. Bật đăng nhập mã thiết bị trong cài đặt bảo mật ChatGPT hoặc quyền workspace OpenAI theo hướng dẫn chính thức. Không tự tắt MFA hoặc kiểm soát của tổ chức.

## Bảo vệ dữ liệu và vòng đời

- Giữ provider `codex_cli` và các API/grants/ledger native đã có; không thêm business runner, queue, bảng hoặc migration. Schema vẫn 0072, hợp đồng candidate 416 operations.
- Mỗi profile gắn đúng workspace, PAO actor, connection và thiết bị. Docker volume phải có label/driver đúng và image/binary đúng pin; không mount home Windows, auth của Javis, thư mục doanh nghiệp khác hoặc Docker socket.
- Code chạy UID 65534, root filesystem chỉ đọc, bỏ capabilities, giới hạn RAM/CPU/PID và output. Bootstrap chỉ tạo thư mục Codex riêng, kiểm tra SHA binary và khởi động app-server; không nhận command/env/code tùy ý từ UI.
- RPC chỉ cho initialize, account/read và account/login/start. Không thread/turn/tool, API key hoặc token import. Cached API-key mode bị từ chối, không tự chuyển thành API có phí.
- Mã thiết bị chỉ nằm trong bộ nhớ phiên đăng nhập có thời hạn và gửi về đúng PAO bearer session; không log, đưa vào URL hoặc lưu trình duyệt. URL xác nhận phải đúng `https://auth.openai.com/codex/device`. Ẩn tab xóa mã khỏi UI; polling chỉ diễn ra khi tab hiển thị.
- Phiên có trần 10 phút, tối đa 4 phiên chạy/32 bản ghi tạm mỗi API instance, giới hạn bắt đầu theo user/SME. Kiểm tra lại session/membership/version/device trước thao tác và trong lúc chờ; thu hồi quyền sẽ dừng ceremony. Fencing dùng `setup_operation_id` hiện có và chặn model dispatch trong khi setup.
- Hủy/timeout dừng đúng container theo image/name/operation/scope labels. Cleanup không xác minh được thì giữ fence, không báo thành công. API restart không lưu lại code: trả **Phiên bị gián đoạn**, cho người dùng phục hồi có phiên bản và operation ID đúng.
- Ngắt PAO không tự logout/thu hồi tài khoản Codex của ứng dụng khác, không xóa profile volume. Kết nối lại không tự làm sống lại grant/job cũ.

Đây là auth ceremony trong một API local, không phải bộ điều phối model mới hoặc giải pháp auth nhiều replica. Không tự thay default Ollama/model, gỡ local model hoặc bật Ads/Telegram/API fallback.

## Bằng chứng đang theo dõi

- Checkpoint nguồn/DB trước phát triển: `.runtime/codex-login-checkpoint-fdf781535d1c43f09f6de7c0f6cff9ef/checkpoint.json`.
- Native RPC trên binary Codex 0.157.1 thật, profile thử trống và `network=none`: `.runtime/codex-login-rpc-e1504964898e432a8fd41ba2bbf6e084/receipt.json`. Đã dọn đúng volume/container thử; không mount profile chính, không đăng nhập hoặc suy luận thật.
- 167 Node, typegen/TypeScript/build23 trên bản sao nguồn: `.runtime/model-provider-tabs-frontend-7218f9b629f44b1cb2a38a180c49de42/receipt.json`. Ba cảnh báo hook mới đã sửa, không tắt lint; cảnh báo cũ ngoài phạm vi giữ nguyên.
- Browser auth fixture: `.runtime/codex-login-browser-1792400315760/receipt.json`; cached profile, mở trang chính thức, complete/cancel/recovery, mất ACK không retry, không lưu code, SME/viewer, sáng/tối 320/390 đạt. Mã trong ảnh chỉ là fixture không sử dụng được.
- Hồi quy UI các ô API/Client: `.runtime/model-provider-tabs-browser-1792399521657/receipt.json`, API/provider thật không được chuyển tiếp.
- Full backend đầu tiên: `.runtime/codex-login-tests-bbff12f771ca45c589283243288d58de/receipt.json`: **1416 passed/1 failed**, 1802.24 giây. Lỗi `exact_windows_candidate_test_restore_required` vì helper chỉ cho tên candidate cũ; không phải bằng chứng full pass.
- Sửa duy nhất helper restore trong candidate: thêm đúng thư mục `codex-login-candidate-20261019`; root và PAO_ROOT phải khớp nhau. Giữ nguyên pao_test, host/port/user/driver/container-ID và owned-clone constraints. 9 unit guards đạt.
- Phần tiếp diễn: `.runtime/codex-login-tests-bc1b901c995746938f67a357921a161b/`. Manifest đối chiếu collection đủ 2356 node IDs, giữ prefix 1416 pass và chạy 940 bài còn lại gồm bài restore lỗi. Backend/CLI/contract/locks không đổi; delta input chỉ helper đường dẫn. Chỉ được ghép khi JUnit và nguồn khớp; không ghép log để gọi là một pipeline xanh.

Kết quả phần tiếp diễn: **940 passed, 1416 deselected, 0 fail/error/skip**, 1009.47 giây, 29 cảnh báo ARQ cũ. Bao phủ đủ 2356 node IDs khác nhau sau đối chiếu JUnit/collection và hash nguồn; đây **không phải một lượt full xanh mới**. Receipt kiểm chứng phạm vi: `.runtime/codex-login-regression-4b6e9ef611fc4093ac254b2b0e0ea73f/receipt.json`. Lượt full thất bại không bị thay thế hoặc sửa lại.

Kế hoạch cài 17 tệp và kiểm chứng: `.runtime/codex-login-install-99c13e0f331d49919c4cb90890a86aea/source-plan.json`, `installed-check.json`, `health.log`. Binding mới: `4406204f56921e05b6492e36bc4f3594fb4f549683df712fbdcd0cb6287cd1a5`. Chỉ thêm dòng `CLI_BROWSER_LOGIN_ENABLED=true`; bản sao môi trường riêng được giữ để phục hồi, không hiển thị giá trị. Không sửa hoặc phục hồi database chính, không chép auth Windows/Javis.

Browser fixture trên Web3200 sau cài: `.runtime/codex-login-browser-1792402023800/receipt.json` và `.runtime/model-provider-tabs-browser-1792402070272/receipt.json` đều đạt; mọi API/provider thật bị chặn trong các bài này. Không dùng fixture làm bằng chứng tài khoản thật.

Lượt kiểm tra snapshot tiếp theo **không đạt so sánh dữ liệu đứng yên**; giữ `post-browser-check.log`, không sửa snapshot gốc. Người dùng xác nhận đang thao tác. Log API có POST prepare/login200 lúc 16:28:50/53; so sánh chỉ đọc ghi nhận thay đổi `cli_model_connections` và thêm một `tenant_metadata_leases`. Không quy toàn bộ thay đổi cho một nguyên nhân chỉ từ hash. Metadata profile connected được đọc riêng, không lấy mã thiết bị/token. Evidence: `.runtime/codex-login-user-activity-e6fe60b498c1404eae55be1372ca89db/receipt.json`. Không phục hồi/xóa dữ liệu để làm kiểm tra đạt. Hash nguyên dữ liệu chỉ áp dụng thời điểm kiểm tra cài ban đầu, không phải toàn thời gian người dùng sử dụng.

Completion tổng hợp: `.runtime/codex-login-completion.json`; tách rõ cài local, quan sát đăng nhập người dùng, fixture và gate job/quota/production. Helper tổng hợp đầu tiên đã chặn do so generated schema với file cũ trong candidate; sửa để đối chiếu đúng digest schema từ build đã duyệt trong source-plan, không đổi ứng dụng hoặc receipt cũ.

Các lượt focused lỗi do kỳ vọng số API 412 cũ, RPC đầu tiên thiếu khởi tạo CODEX_HOME và build bị Windows EPERM được giữ nguyên trong runtime. Không sửa hash/receipt thất bại hoặc restore primary để làm test đạt. 59 focused cũ là bằng chứng lịch sử trước bootstrap cuối, không cộng vào tổng backend hoặc dùng thay toàn coverage.

## Nguồn chính thức và chốt còn lại

Đã đọc OpenAI Docs ngày 19/10/2026 và schema được sinh offline từ đúng binary 0.157.1:

- [App Server](https://learn.chatgpt.com/docs/app-server): initialize/account/login/read/cancel và managed device auth; phân biệt hỗ trợ local với commercial/hosted.
- [Authentication](https://learn.chatgpt.com/docs/auth): bật device login, MFA, cache và profile. Không sử dụng hướng sao chép auth cache cho PAO nhiều SME.
- [Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart): hướng đăng nhập riêng cần đánh giá cho SaaS tương lai.

App-server auth local này chưa được duyệt làm dịch vụ SaaS/hosted. Đã quan sát đăng nhập profile sau thao tác người dùng; bước tiếp theo là nghiệm thu model/grant/một native job có phạm vi được duyệt. Chưa đóng toàn P8.4-C/E/G, S6, pilot hoặc production; Claude/Antigravity vẫn chưa kết nối.
