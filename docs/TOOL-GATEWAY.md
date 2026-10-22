# Tool Gateway — Phase 5

PAO dùng chung một gateway cho đề xuất của planner và thao tác trên giao diện. Mỗi tool call thuộc một run, workspace và chủ hội thoại. Bảng **Công cụ và phê duyệt** nằm dưới hội thoại đã có run; cập nhật mỗi 3 giây và tách trạng thái khỏi hoạt động agent.

| Công cụ | Agent được phép | Quyền workspace | Thực thi |
|---|---|---|---|
| web.search | Chief, Researcher, Marketing | owner/admin/operator/analyst | Tìm kiếm thật qua SearXNG |
| email.mock_send | Chief | owner/admin/operator | Mô phỏng sau khi người dùng duyệt |
| calendar.mock_create | Chief | owner/admin/operator | Mô phỏng sau khi người dùng duyệt |

Viewer không đề xuất/thực thi. Quyền sở hữu run luôn được kiểm tra: có role trong workspace không cho phép xem hay duyệt hội thoại của người khác. Quyền và trạng thái run được kiểm tra lại trước và sau thực thi. Run thất bại hoặc bị hủy làm đề xuất chưa chạy chuyển cancelled trong lần dispatch tiếp theo.

## Duyệt và thực thi

1. Planner hoặc người dùng tạo đề xuất với nội dung cụ thể. Backend kiểm tra schema, agent và role. Tối đa 2 đề xuất từ planner, 4 tool calls/run, 20 yêu cầu thủ công/phút/người dùng.
2. Search được xếp hàng hoặc chạy trong lượt AI. Email/lịch chuyển pending; chưa gọi adapter. Nội dung bất biến, muốn sửa phải tạo đề xuất mới.
3. Người dùng xem người nhận, tiêu đề, nội dung hoặc thời gian rồi duyệt/từ chối đúng version. Duyệt hết hạn sau 24 giờ. Mô hình không có endpoint tự cấp approval.
4. Worker lấy queued job bằng khóa hàng PostgreSQL. Khóa idempotency theo run và hash payload ngăn gửi trùng hoặc dùng lại khóa với nội dung khác. Gửi lại approval đã nhận không thực thi thêm lần nữa.
5. Kết quả xuất hiện trong bảng công cụ. Chat không giữ worker chờ phê duyệt và không tự tiếp tục kế hoạch cũ; lượt chat tiếp theo có thể dùng tối đa 4 kết quả đã hoàn tất trong cùng hội thoại.

Adapter có thời hạn 20 giây; tìm kiếm giới hạn HTTP 15 giây, payload 1 MB, tối đa 5 kết quả. Search chỉ gửi query đến endpoint quản trị cấu hình; không tải URL do model đưa vào. Snippet là dữ liệu chưa xác minh, không được xem như chỉ dẫn. Kết quả ít/rỗng hoặc engine lỗi được thể hiện; không suy diễn là đã xác minh nguồn.

Worker mất sau khi claim dẫn đến `unknown` sau 90 giây, không tự phát lại. Cần xem nhật ký trước khi tạo yêu cầu mới. Email/lịch hiện không gọi dịch vụ ngoài; kết quả luôn ghi `simulated=true`, `delivered=false` hoặc `external_event_created=false`.

Audit ghi đề xuất, từ chối quyền tại gateway, quyết định và chuyển trạng thái. Không có API sửa/xóa audit; đây là append-only ở lớp ứng dụng, không phải nhật ký chống sửa bởi DBA. Yêu cầu bị từ chối trước khi tới gateway (xác thực/schema HTTP) không nhất thiết có ToolAudit. Không lưu raw exception hay credentials vào audit.

## Vận hành local

`scripts/start_local.ps1` tạo riêng secret SearXNG nếu thiếu và khởi động profile search cùng PostgreSQL/Redis. Không ghi đè thông tin đăng nhập hiện có. SearXNG bind `127.0.0.1:8888`, giới hạn RAM 384 MB; model tiếp tục Ollama local trên CPU. Tìm kiếm cần Internet vì query gửi tới các máy tìm kiếm bên ngoài.

```powershell
.venv/Scripts/python.exe scripts/setup_search.py
docker compose --env-file .env -f infra/compose.yaml --profile search up -d search
```

Backend native dùng `SEARXNG_URL=http://127.0.0.1:8888`; Docker app dùng `http://search:8080` và cần bật cả profile `app` và `search`. `TOOLS_ENABLED=false` khóa đề xuất/thực thi toàn bộ công cụ. Container dùng digest cố định của image đã nghiệm thu; cấu hình ở `infra/searxng/settings.yml`. Không mở cổng công khai với cấu hình local này.

SearXNG yêu cầu bật JSON trong search.formats; nếu thiếu sẽ trả 403. [Search API chính thức](https://docs.searxng.org/dev/search_api.html). Secret được truyền bằng SEARXNG_SECRET. [Cấu hình server chính thức](https://docs.searxng.org/admin/settings/settings_server.html).

## API và dữ liệu

- `GET /v1/tools`: registry và schema đầu vào.
- `GET /v1/runs/{id}/tools`: calls và audit của run sở hữu.
- `POST /v1/runs/{id}/tools`: đề xuất gồm name, agent, arguments, request_key.
- `POST /v1/tools/calls/{id}/decision`: approve/reject và version.

Migration 0004 thêm tool_calls/tool_audits, không sửa nội dung hội thoại. Backup trước khi nâng cấp; downgrade 0004 sẽ xóa dữ liệu hai bảng này. Không downgrade database thật để chạy thử. `scripts/test_backend.py --roundtrip` chỉ dùng pao_test; guard Phase 4 vẫn từ chối downgrade khi còn lịch sử nhiều agent. Chạy fixture test trước roundtrip nếu pao_test đang giữ ca nghiệm thu nhiều agent.

`scripts/verify_tools_local.py` kiểm chứng model/search thật và approval mô phỏng trong pao_test. Không chạy đồng thời với pytest vì fixture làm sạch database kiểm thử. Chưa triển khai email/lịch thật, trình duyệt tùy ý, connector Ads hoặc workflow tự động sau approval.
