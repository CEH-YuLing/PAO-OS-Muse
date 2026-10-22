// Presentation only. Never grants authority, retries a job or treats a cancel request as ACK.
export const ACTIVE_JOB_STATES = ['queued', 'running'];
export function activeBusinessJobs(jobs = []) {
  return jobs.some(job => ACTIVE_JOB_STATES.includes(job.status));
}
export function businessJobLabel(job) {
  if (job.cancel_requested === true && ACTIVE_JOB_STATES.includes(job.status)) return 'Đã yêu cầu hủy — đang chờ xác nhận';
  return ({queued:'Đang chờ hàng đợi',running:'Đang chạy',completed:'Đã tạo bản nháp',failed:'Không hoàn tất',cancelled:'Đã hủy'})[job.status] || 'Trạng thái chưa xác minh';
}
export function businessProgress(jobs = []) {
  return {
    active: jobs.filter(j => ACTIVE_JOB_STATES.includes(j.status)).length,
    pendingCancel: jobs.filter(j => ACTIVE_JOB_STATES.includes(j.status) && j.cancel_requested === true).length,
    waitingReview: jobs.filter(j => j.status === 'completed' && !j.content_decision).length,
    approved: jobs.filter(j => j.content_approved === true).length,
    needsRework: jobs.filter(j => ['failed','cancelled'].includes(j.status) || j.content_decision === 'reject').length,
  };
}
export function pollBusinessOperations(jobs, {visible, online, unknown, busy}) {
  return visible === true && online === true && unknown === false && busy === false && activeBusinessJobs(jobs);
}
