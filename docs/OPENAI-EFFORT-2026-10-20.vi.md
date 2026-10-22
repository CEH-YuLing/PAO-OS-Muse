# OpenAI API — chọn mức suy luận theo model, nghiệm thu local20/10

## Kết luận và phạm vi

Đã cài adapter OpenAI API trên PAO local. Schema0075/161bảng/API429 giữ nguyên;
binding mới `f596abc415cb9e97b18b7da6e5e1d937fe9194ac82896ea73badcc6d3ac1bf3a`.
Không đổi khóa, `.env`, registry/image/profile Codex hay provision Antigravity.
Không dùng quota/model/API thật, không bật provider, Ads, VPS/public.

Đây là một phần đã hoàn thiện của RAI3–RAI4/API, không phải toàn đợt RAI,
toàn bộ OpenAI model hay nghiệm thu thương mại. Gemini/Anthropic explicit effort
và ba CLI dùng chung vẫn giữ các chốt còn thiếu; không thêm grant cá nhân.

## Hành vi đã triển khai

Danh sách ID vẫn lấy từ `/v1/models` qua native admission. Do API này chỉ trả
metadata cơ bản, PAO bổ sung khả năng bằng bảng exact-ID đã đối chiếu tài liệu:

| Model được trả về từ kết nối | Mức có thể chọn | Mặc định được tài liệu xác nhận |
| --- | --- | --- |
| `gpt-6.1-sol` | low, medium, high, xhigh, max | medium |
| `gpt-6-astra` | low, medium, high, xhigh, max | Không tự đoán |
| `gpt-6-luna` | none, low, medium, high, xhigh, max | medium |

Bảng không tạo thêm model vào catalog, không chứng nhận entitlement/quota.
Không suy diễn theo prefix, alias mới, snapshot chưa đối chiếu hoặc fine-tune.
Model khác vẫn được giữ trong danh mục nhưng chỉ có Mặc định, không giả hiện
High hoạt động. Metadata `reasoning` lạ trong response OpenAI không được tin.

- `reasoning_effort` gửi đúng tham số Chat Completions, cho streaming và JSON
  structured dùng chung; không gửi schema OpenRouter `reasoning.effort` sang OpenAI.
- Với ba model đã đối chiếu, dùng `max_completion_tokens` bằng đúng giới hạn
  token trước đó; bỏ tham số sampling không tương thích. Không nhân ngân sách,
  tự tăng token, chọn service tier/pro mode hoặc gọi thêm lần để làm được High.
- Reasoning token nằm trong completion usage; native ledger dùng tổng completion
  được provider báo, không cộng lại reasoning để tính trùng. Usage thiếu không
  được suy ra là miễn phí. Ngân sách thấp có thể không đủ cho mức suy luận cao;
  chưa có quality/live-quota acceptance hoặc thay đổi ngân sách mặc định.
- Mặc định không gửi explicit effort. Model không được đối chiếu giữ nguyên
  payload cũ khi chưa chọn effort; explicit effort không hợp lệ bị chặn trước I/O.
- Backend kiểm cả khả năng adapter, không chỉ tin catalog đã lưu. Catalog bị
  sửa để gán High cho model lạ không vượt được chốt thực thi.
- Chat/orchestrator và agent có lựa chọn độc lập. Snapshot chốt lựa chọn theo
  lượt; đổi agent không sửa chat/profile/lịch sử. Tái dùng runner/AccountingEngine.
- Role/SME/Brain/privacy/lease/budget/revoke giữ nguyên. Các request của adapter
  chỉ text/JSON, không thêm native tools, function calling hay fallback trả phí.
- OpenRouter vẫn dùng schema cũ; Anthropic/Gemini chưa nhận effort tự suy diễn.

Code chính: `apps/api/pao/modules/installation_ai/openai_effort.py`,
`gateway.py`, `model_router.py`, `modules/installation_ai/service.py`.
37test mới nằm trong `apps/api/tests/test_openai_effort.py`, được phát hiện bởi
suite backend thông thường, không chỉ trong script nghiệm thu riêng.

## Hướng dẫn sử dụng

1. Trong Cài đặt và kết nối → AI và giọng nói → Nhà cung cấp mô hình → API,
   quản trị bản cài cấu hình OpenAI bằng luồng hiện có. Không gửi API key vào
   chat. Key chỉ được lưu mã hóa; UI chỉ hiện trạng thái/hint, không trả key.
2. Sau khi chủ động đọc danh mục bằng kết nối hợp lệ, tài nguyên chung mới có
   metadata cập nhật. Các catalog đã lưu không bị refresh ngầm trong đợt cài này.
3. Lưu/bật tài nguyên và chọn mặc định là các bước riêng; không suy ra đã nghiệm
   thu inference từ việc lưu key hoặc đọc được model. Mọi thành viên dùng theo
   vai trò PAO, không cấp grant AI riêng cho từng nhân sự.
4. Ở đầu hội thoại, chọn model rồi Mức suy luận, bấm Áp dụng model. Đổi sang
   model khác xóa bản nháp effort cũ; model chưa xác minh vô hiệu hóa bộ chọn.
   Các agent/step/job có lựa chọn riêng/kế thừa qua cơ chế đã có.
5. Xoay/xóa key/ngắt kết nối bằng luồng gốc; source stamp/revision chặn lượt
   đã ghim bị cũ. Không lén dùng key hoặc provider khác khi nguồn mất quyền.

Phạm vi xác thực: OpenAI API project key/Bearer tới endpoint chính chủ cố định
`https://api.openai.com/v1`; không dùng thuê bao Codex làm API key. Không OAuth
redirect/webhook/app review mới trong adapter này. Rate limit/auth/rotation và
quyền project vẫn do tài khoản OpenAI và native connection flow quyết định.
Lỗi400/401/403/429/timeout được trả theo đường lỗi hiện có; không có vòng retry
hoặc tự đổi API. Tiền API nếu khách hàng chủ động bật/gọi thật là phần riêng,
không phải miễn phí theo gói Codex/ChatGPT.

## Bằng chứng và các failure được giữ nguyên

1. Candidate mở rộng: **325test chức năng đạt,0failed/error/skip**,4ARQ warnings,
   241.04s. Test HTTP dùng `MockTransport`, key tổng hợp; có native API lựa chọn,
   Run/Accounting, operator/viewer/SME khác, usage, invalid effort, revoke,
   agent override và hồi quy engine/Studio/business/CLI cũ.
   `.runtime/openai-effort-tests-b2e37efeb54345618dfd325eaec661ea/receipt.json`.
   **Aggregate receipt này vẫn FAIL** vì primary có thay đổi trong lúc test;
   không gọi nó là một lượt kiểm tra toàn xanh hoặc chứng minh primary bất biến.
2. Bổ sung37test adapter đạt,0failed/error/skip. Helper đã giữ hash trước/sau;
   chỉ `tenant_metadata_leases` thay đổi. Aggregate cũng giữ FAIL, không viết lại.
   `.runtime/openai-effort-tests-f44eaf15128e4e7aa3268682e8b0a8b5/receipt.json`.
   Không cộng37vào325vì các ca trùng nhau, không full regression mới.
3. Audit riêng: so với checkpoint14:27 chỉ `login_sessions` và
   `tenant_metadata_leases` thay đổi; archive không đổi. Log ghi nhận POST login
   lúc21:32 và connect Antigravity lúc21:33 giờ Việt Nam, ngoài test mock. Đây
   là bằng chứng hoạt động đồng thời, không xác nhận ai thao tác. Snapshot chính
   xác đầu lượt325không được giữ bởi helper cũ; không bịa lại được. Clone chỉ
   đọc/so sánh đã xóa đúng tên, không restore/overwrite primary.
   `.runtime/openai-effort-drift-856646a49be241a9b4fbcf78dd8a0459/receipt.json`.
4. UI fixture OpenAI: dark/light1600/1024/768/390/320, bàn phím/popover, High
   lưu đúng body, `none` chỉ xuất hiện ở model hỗ trợ, model lạ bị vô hiệu hóa,
   đổi model reset effort, message không dịch. Không forward backend/provider.
   `.runtime/chat-controls-browser-1792506849444/receipt.json`.
5. Checkpoint mới giữ cả thay đổi hợp lệ ở phiên/metadata, có backup/clone-restore:
   `.runtime/checkpoints/p0-20261020T143814-3397bcd2/manifest.json`.
   Chỉ dừng API/worker đã xác minh executable/start-time/command; idle, không
   setup/dispatch/metadata lease đang hoạt động. Không migration, không xóa dữ
   liệu để làm khớp snapshot cũ.
6. Cài đặt có bằng chứng riêng: đúng4file backend trùng source candidate đã
   test, source/env/runtime khác không đổi; hash toàn bảng sau khi dừng giữ
   nguyên qua cài/restart. Provision Antigravity giữ nguyên. Receipt cài đặt PASS
   không sửa aggregate FAIL ở mục1–2.
   `.runtime/openai-effort-install-9562b2f0c79c4e059eacace31b4b2d97/receipt.json`.
7. Installed GET-only PASS: API/ready/Web200, contract429, schema0075/161bảng,
   pin CLI hợp lệ, replayHTTP3/3 không thực thi lại tool, primary giữ nguyên
   trong cửa sổ kiểm tra này. Diagnostic bearer không phải owner consent/pilot.
   `.runtime/installation-ai-live-3316f2f37b4345ff8650b9cd04386064/receipt.json`.

Recovery script có một failure do kiểm health quá sớm khi API còn cold-import;
log startup và kiểm tiếp theo xác nhận API200/worker khỏe. Không gọi lần đầu
đó là pass. Helper đã có chờ readiness giới hạn trước phép kiểm cuối; thay đổi
operator script được kiểm cú pháp, không lặp restart chỉ để làm đẹp receipt.

Không sửa frontend source/contracts nên không chạy/nhận một frontend build mới;
bằng chứng build213Node/build23 ở đợt trước chỉ là lịch sử, không test mới này.

## Các chốt còn lại

- Chưa gọi API/model thật hoặc chứng minh tài khoản có các ID trên; không tự
  đọc lại provider bằng key đã lưu, không tự bật nguồn.
- Codex shared identity, chuyển pin/runtime và live quota còn chờ; Claude CLI
  theo user đã hoãn; Antigravity còn chốt native tools60 của lượt trước.
- Cache danh mục Antigravity là in-memory: restart API có thể hiện Chưa kiểm
  tra; người dùng bấm Kết nối/Đọc lại khi cần. Đăng nhập/keyring của CLI không
  bị đọc, thay đổi hoặc đăng xuất bởi việc cài OpenAI.
- Gemini/Anthropic explicit effort cần adapter riêng và nguồn chính chủ trước
  khi bật. Không diễn dịch mọi mức High thành cùng một tham số giữa nhà cung cấp.
- Chưa owner/live-data pilot, commercial, production, VPS/public acceptance.

## Nguồn chính chủ đối chiếu20/10/2026

- [Models list](https://developers.openai.com/api/reference/resources/models/methods/list):
  danh mục cơ bản, không phải danh sách effort/entitlement inference đã thử.
- [Chat Completions](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create):
  `reasoning_effort`, `max_completion_tokens` gồm reasoning và visible output.
- [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
  [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
  [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna): mức
  hỗ trợ theo model; không dùng công cụ native trong Chat Completions adapter PAO.
- [Deployment checklist](https://developers.openai.com/api/docs/guides/deployment-checklist):
  khác biệt mức suy luận/sampling và phạm vi hỗ trợ công cụ theo endpoint.
