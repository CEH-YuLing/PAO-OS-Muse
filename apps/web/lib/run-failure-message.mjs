// Server error codes remain identifiers; never reflect an arbitrary error body.
const CLIENT_ERRORS = new Map([
  ['engine_output_budget_exhausted','Lượt cũ vượt ngân sách đầu ra đã ghim. Lượt mới ở chế độ theo mô hình không dùng trần token PAO này.'],
  ['engine_budget_exhausted','Đã đạt số lần gọi chống vòng lặp hoặc ngân sách của lượt cũ. Kiểm tra nhật ký trước khi tạo lượt mới.'],
  ['context_transport_limit','Dữ liệu vượt dung lượng vận chuyển an toàn của ứng dụng. Hãy chia tài liệu/yêu cầu thành các phần nhỏ; đây không phải giới hạn token của mô hình.'],
  ['engine_provider_context_exceeded','Nhà cung cấp từ chối vì vượt cửa sổ ngữ cảnh của mô hình. Hãy chia tài liệu hoặc chọn mô hình có cửa sổ ngữ cảnh lớn hơn.'],
  ['engine_provider_limits_unknown','Chưa đọc được khả năng đầu ra của mô hình từ nhà cung cấp. Kiểm tra kết nối; PAO không tự đoán một trần token.'],
  ['engine_provider_rate_limited', 'Nhà cung cấp đang giới hạn số yêu cầu. Hãy chờ rồi kiểm tra hạn mức tại tài khoản nhà cung cấp.'],
  ['engine_provider_authentication', 'Nhà cung cấp từ chối xác thực. Quản trị viên hãy kiểm tra kết nối đã lưu trong Cài đặt và kết nối.'],
  ['engine_provider_temporary', 'Dịch vụ AI tạm thời không đáp ứng. Hãy chờ và kiểm tra trạng thái trước khi chủ động chạy lại.'],
  ['engine_resource_cooling_down', 'PAO tạm ngừng gửi thêm đến model này sau nhiều lỗi liên tiếp. Hãy chờ khoảng một phút rồi kiểm tra lại; không cần đổi khóa hoặc cấp quyền AI mới.'],
  ['engine_timeout', 'Yêu cầu AI vượt thời gian cho phép. Kiểm tra lượt chạy và hạn mức trước khi chủ động thử lại.'],
  ['cli_provider_failed', 'Codex chưa trả về kết quả hợp lệ. Kiểm tra trạng thái Client, model và thông tin chẩn đoán; chưa xác định được nguyên nhân từ mã lỗi này.'],
  ['cli_access_denied', 'Quyền dùng Codex hoặc phiên đăng nhập không còn hợp lệ. Kiểm tra lại thiết lập Codex của bạn.'],
  ['cli_timeout', 'Codex không hoàn tất trong thời gian cho phép. Kiểm tra trạng thái lượt chạy trước khi thử lại.'],
  ['cli_profile_busy', 'Hồ sơ Codex đang có lượt chạy chưa kết thúc. Chờ hoặc kiểm tra lượt chạy đó trước.'],
  ['cli_cleanup_failed', 'Chưa xác minh dọn dẹp tiến trình Codex. Cần kiểm tra vận hành trước khi chạy tiếp.'],
  ['cli_binary_changed', 'Phiên bản Client Codex không khớp bản đã xác minh. Cần kiểm tra cấu hình vận hành.'],
  ['cli_tool_event_denied', 'Codex yêu cầu công cụ ngoài phạm vi cho phép. PAO đã chặn kết quả.'],
  ['cli_plan_invalid', 'Codex đã trả nội dung nhưng chưa đúng định dạng kế hoạch PAO yêu cầu.'],
  ['cli_runtime_failed', 'Không hoàn tất được Client Codex. Kiểm tra trạng thái Client và nhật ký vận hành.'],
]);
const NO_AUTOMATIC_RETRY = ' PAO không tự thử lại hoặc chuyển sang API trả phí. Hạn mức đã sử dụng có thể chưa xác định.';

export function runFailureMessage(code) {
  if (code == null || code === '') return '';
  const hint = CLIENT_ERRORS.get(code);
  if (hint) return `Lượt chạy thất bại (${code}). ${hint}${NO_AUTOMATIC_RETRY}`;
  return 'Lượt chạy chưa hoàn tất. Xem trạng thái và nhật ký vận hành để xác định nguyên nhân; không suy ra lỗi thuộc Ollama hoặc một nhà cung cấp cụ thể.';
}
