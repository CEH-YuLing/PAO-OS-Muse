// Presentation only: never changes backend enums, permissions or execution state.
export function featureLabel(value){return value===true?'Đã bật':value===false?'Đang tắt':'Chưa xác minh'}
export function coverageLabel(report){
 if(!report)return 'Chưa có dữ liệu';
 return Number.isInteger(report.coverage_days)&&Number.isInteger(report.expected_days)&&report.expected_days>0&&report.coverage_days===report.expected_days?'Đủ dữ liệu':'Cần kiểm tra';
}
export function connectionLabel(value){return ({connected:'Đã kết nối',configured:'Đã cấu hình',not_configured:'Chưa cấu hình','not configured':'Chưa cấu hình',expired:'Đã hết hạn',revoked:'Đã thu hồi',disconnected:'Đã ngắt kết nối',disabled:'Đang tắt',error:'Cần kiểm tra',draft:'Bản nháp'})[value]||`Trạng thái: ${value||'chưa xác minh'}`}
export function runtimeLabel(value){return ({standby:'Đang chờ',idle:'Đang chờ',thinking:'Đang xử lý',reasoning:'Đang suy luận',executing:'Đang thực hiện',running:'Đang chạy',responding:'Đang trả lời',error:'Có lỗi',cancelled:'Đã hủy',completed:'Đã hoàn thành',listening:'Đang nghe',processing:'Đang xử lý',speaking:'Đang đọc'})[value]||value}
