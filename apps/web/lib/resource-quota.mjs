// Presentation only: the API remains the admission and permission authority.
export const resourcePools = {
  models: {title: 'AI và embeddings', policy: 'model_policy', fields: {
    daily_model_calls: ['Lượt AI mỗi ngày (UTC)', 10000],
    daily_model_tokens: ['Token giữ chỗ hoặc được báo cáo mỗi ngày', 10000000],
    concurrent_models: ['Lượt AI chạy đồng thời', 8],
  }, usage: {
    calls: 'Lượt đã được tiếp nhận hôm nay', reserved_or_reported_tokens: 'Token giữ chỗ / được báo cáo hôm nay',
    unknown_usage_calls: 'Lượt hôm nay chưa có mức sử dụng chính xác', active_models: 'Lượt đang giữ suất xử lý',
  }, help: 'Gồm chat, kiểm tra mô hình và embeddings bộ nhớ/tri thức. Embeddings giữ chỗ theo byte UTF-8; đây không phải số token chính xác của mô hình. Khi embeddings bị chặn, tìm kiếm có thể dùng từ khóa nếu vẫn đủ quyền.'},
  reads: {title: 'Đọc MCP và Ads', policy: 'read_policy', fields: {
    daily_read_jobs: ['Việc đọc mỗi ngày (UTC)', 10000], queued_read_jobs: ['Việc được xếp hàng', 100], concurrent_reads: ['Việc đọc chạy đồng thời', 8],
  }, usage: {daily_jobs: 'Việc đã tiếp nhận hôm nay', queued_jobs: 'Việc đang chờ', running_jobs: 'Việc đang chạy'},
  help: 'Gồm MCP chỉ đọc, Meta và Google Ads đồng bộ. Một việc PAO có thể gọi nhiều HTTP yêu cầu. Hủy việc không hoàn lại lượt đã tiếp nhận; công việc chờ vẫn cần kiểm tra quyền khi chạy.'},
  metadata: {title: 'Danh mục và cấu hình kết nối', policy: 'metadata_policy', fields: {
    daily_metadata_requests: ['Lượt danh mục mỗi ngày (UTC)', 1000], concurrent_metadata: ['Lượt danh mục chạy đồng thời', 8],
  }, usage: {daily_requests: 'Lượt đã tiếp nhận hôm nay', active_requests: 'Lượt đang giữ suất xử lý', expired_unknown_requests: 'Lease hết hạn chưa xác định kết quả (toàn lịch sử)'},
  help: 'Gồm kết nối, tải/chọn mô hình và tìm danh mục MCP. Một lượt có thể gọi nhiều HTTP yêu cầu. Lease hết hạn không chứng minh nhà cung cấp chưa xử lý; không tự gửi lại.'},
};

const integer = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
export function validateResourceSnapshot(pool, data, workspace) {
  const spec = resourcePools[pool], policy = data?.[spec?.policy];
  if (!spec || !policy || !integer(policy.version) || !data.usage || !data.host_ceilings ||
      data.grants_authorized !== false || (pool !== 'models' && data.workspace_id !== workspace))
    throw new Error('quota_snapshot_invalid');
  for (const [key, [, maximum]] of Object.entries(spec.fields)) {
    const ceiling = data.host_ceilings[key];
    if (!integer(ceiling) || ceiling < 1 || ceiling > maximum || !integer(policy[key]) || policy[key] < 1 || policy[key] > ceiling)
      throw new Error('quota_snapshot_invalid');
  }
  for (const key of Object.keys(spec.usage)) if (!integer(data.usage[key])) throw new Error('quota_snapshot_invalid');
  return data;
}

export function resourceDraft(pool, data) {
  return Object.fromEntries(Object.keys(resourcePools[pool].fields).map(key => [key, String(data[resourcePools[pool].policy][key])]));
}
export function resourcePayload(pool, data, draft) {
  const spec = resourcePools[pool], result = {expected_version: data[spec.policy].version};
  for (const key of Object.keys(spec.fields)) {
    const raw = draft[key];
    if (typeof raw !== 'string' || !/^[0-9]+$/.test(raw) || !Number.isSafeInteger(Number(raw)) || Number(raw) < 1 || Number(raw) > data.host_ceilings[key])
      throw new Error('quota_form_invalid');
    result[key] = Number(raw);
  }
  return result;
}

export function resourceErrorHelp(code) {
  if (/^tenant_(resource|read_policy|metadata_policy)_.*version_conflict$/.test(code))
    return 'Chính sách đã đổi ở phiên khác. Bấm “Tải lại hạn mức” để đọc phiên bản mới (bỏ bản nháp), kiểm tra rồi lưu lại; PAO không tự ghi đè.';
  if (/^tenant_(model_daily_(calls|tokens)|read_daily_jobs|metadata_daily)_exhausted$/.test(code))
    return 'Đã hết hạn mức ngày UTC. Chờ kỳ mới (00:00 UTC, 07:00 Việt Nam) hoặc nhờ chủ doanh nghiệp/quản trị viên xem lại giới hạn trong trần hệ thống. Không tự gửi lại tác vụ.';
  if (/^tenant_(model|read|metadata)_concurrency_exhausted$/.test(code))
    return 'Các suất xử lý đang bận. Chờ việc hiện tại kết thúc rồi kiểm tra lại; tăng giới hạn không cấp thêm quyền hoặc năng lực máy chủ.';
  if (code === 'tenant_read_queue_exhausted') return 'Hàng đợi doanh nghiệp đã đầy. Xem việc đang chờ, hủy nếu không còn cần rồi kiểm tra lại. Không tự chạy lại hoặc chuyển sang doanh nghiệp khác.';
  if (code === 'quota_form_invalid') return 'Nhập số nguyên dương trong trần hệ thống. Không dùng số thập phân, số âm hay dạng 1e3.';
  if (code === 'quota_snapshot_invalid') return 'Trạng thái hạn mức không hợp lệ hoặc không đúng doanh nghiệp; biểu mẫu bị khóa. Tải lại và kiểm tra API trước khi lưu.';
  if (['tenant_resource_manager_required','connection_inventory_manager_required'].includes(code)) return 'Quyền quản lý đã thay đổi. Chỉ chủ doanh nghiệp/quản trị viên của doanh nghiệp được xem và sửa hạn mức; tải lại quyền thành viên.';
  return 'Không xác nhận được trạng thái. Nếu vừa lưu, có thể máy chủ đã nhận: bấm “Tải lại hạn mức” để đối chiếu trước khi gửi lại. Không tự gửi lại.';
}
