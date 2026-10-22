'use client';
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { usePao } from '@/lib/PaoRuntimeContext';
import BusinessModelPicker from './BusinessModelPicker';
import {businessJobLabel, businessProgress, pollBusinessOperations} from '@/lib/business-operations.mjs';
type Job = {
    id: string;
    item_key: string;
    status: string;
    model: string;
    provider: string;
    artifact: unknown;
    artifact_hash: string | null;
    content_approved: boolean;
    content_decision: string | null;
    error_code: string | null;
    cancel_requested: boolean;
};
type Budget = {
    id: string;
    currency: string;
    minor_digits: number;
    cap_minor: number;
    available_minor: number;
    reserved_minor: number;
    spent_minor: number;
    released_minor: number;
    stale: boolean;
    account_id: string;
    campaign_id: string;
};
type Action = {
    id: string;
    job_id: string;
    budget_id: string;
    kind: string;
    status: string;
    decision: string | null;
    amount_minor: number;
};
type Report = {
    id: string;
    report: {
        window_from: string;
        window_to: string;
        planned_tasks: number;
        not_started: number;
        tasks: {
            id: string;
            item_key: string;
            status: string;
            model: string;
        }[];
        model_usage: {
            input_tokens: number | null;
            output_tokens: number | null;
            unknown_attempts: number;
        };
        missing_data: string[];
        kpis: {
            name: string;
            target: string | null;
            unit: string;
            measured: null;
        }[];
    };
};
type State = {
    stopped: boolean;
    jobs: Job[];
    budgets: Budget[];
    actions: Action[];
    reports: Report[];
    restricted_jobs: number;
    schedule: {
        enabled: boolean;
        cadence: string;
    } | null;
};
type Routing = {
    item: {
        revision: number;
        content: {
            targets: {
                key: string;
                provider: string;
                model: string;
            }[];
        };
    } | null;
};
const status: Record<string, string> = { queued: 'Đang chờ hàng đợi', running: 'Đang chạy', completed: 'Đã tạo bản nháp', failed: 'Không hoàn tất', cancelled: 'Đã hủy', unknown: 'Kết quả chưa rõ — đang giữ hạn mức', success: 'Mô phỏng thành công', failure: 'Đã đối soát mô phỏng thất bại', awaiting_execution: 'Đã duyệt mô phỏng', awaiting_approval: 'Chờ duyệt hành động mô phỏng' };
const amount = (value: number, budget: Budget) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: budget.minor_digits }).format(value / 10 ** budget.minor_digits) + ' ' + budget.currency;
export default function BusinessOperationsPanel({ plan, draftDirty, onDirty, refreshRevision, brandId=null, onRework, view='jobs' }: {
    view?:'jobs'|'review'|'report';
    onRework: () => void;
    brandId?: string|null;
    plan: {
        id: string;
        revision: number;
        currency: string;
        content: {
            deliverables: {
                key: string;
                title: string;
            }[];
        };
    };
    draftDirty: boolean;
    onDirty: (value: boolean) => void;
    refreshRevision: number;
}) {
    const { api, activeWorkspace: member } = usePao(), base = `/v1/workspaces/${member?.id || ''}/business-planning`, path = base + '/plans/' + plan.id;
    const epoch = useRef(0), lock = useRef(false), [state, setState] = useState<State | null>(null), [routing, setRouting] = useState<Routing['item']>(null), [busy, setBusy] = useState(false), [unknown, setUnknown] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
    const [item, setItem] = useState(''), [target, setTarget] = useState(''), [grant, setGrant] = useState(''), [cap, setCap] = useState(''), [headroom, setHeadroom] = useState(''), [opening, setOpening] = useState(''), [account, setAccount] = useState('mock:account'), [campaign, setCampaign] = useState('mock:campaign'), [budgetId, setBudgetId] = useState(''), [jobId, setJobId] = useState(''), [charge, setCharge] = useState(''), [cadence, setCadence] = useState('hourly'), [dirty, setDirty] = useState(false);
    const mark = useCallback((value: boolean) => { setDirty(value); onDirty(value); }, [onDirty]);
    const [readAt, setReadAt] = useState<number|null>(null);
    const load = useCallback(async (automatic=false) => { if (lock.current)
        return; lock.current = true; const ticket = ++epoch.current; setBusy(true); setError(''); try {
        const [result, configuration] = await Promise.all([api<State>(path + '/operations'), automatic ? Promise.resolve(null) : api<Routing>(base + '/routing')]);
        if (ticket === epoch.current) {
            setState(result);
            if(configuration) setRouting(configuration.item);
            setReadAt(Date.now());
            setItem(previous => result.jobs.some(job => job.item_key === previous) ? '' : previous);
            setUnknown(false);
        }
    }
    catch {
        if (ticket === epoch.current) {
            setUnknown(true);
            setState(null);
            setError('Chưa đọc được vận hành S5. Có thể máy chủ chưa phát hành hoặc quyền đã thay đổi. Không gửi lại hành động khi chưa đối soát.');
        }
    }
    finally {
        if (ticket === epoch.current) {
            lock.current = false;
            setBusy(false);
        }
    } }, [api, base, path]);
    useEffect(() => { const e = epoch, l = lock; void load(); return () => { e.current++; l.current = false; }; }, [load, refreshRevision]);
    useEffect(() => {
        // A read observer, not a scheduler or execution runner. No writes/retry.
        if (!state) return;
        const timer=window.setInterval(()=>{
            if(pollBusinessOperations(state.jobs,{visible:document.visibilityState==='visible',online:navigator.onLine,unknown,busy:lock.current})) void load(true);
        },5000);
        return ()=>window.clearInterval(timer);
    },[state,unknown,load]);
    useEffect(() => { if (!dirty)
        return; const leave = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; }; window.addEventListener('beforeunload', leave); return () => window.removeEventListener('beforeunload', leave); }, [dirty]);
    async function act(url: string, body: unknown, confirmation: string) { if (lock.current || unknown || draftDirty || !window.confirm(confirmation))
        return; lock.current = true; const ticket = epoch.current; setBusy(true); setError(''); setMessage(''); try {
        await api(url, 'POST', body);
        if (ticket === epoch.current) {
            setMessage('Đã ghi nhận. Đọc lại trạng thái để theo dõi; không suy ra hành động bên ngoài đã xảy ra.');
            const observed = await api<State>(path + '/operations');
            if(ticket !== epoch.current) return;
            setState(observed);
            setReadAt(Date.now());
            setItem(previous => observed.jobs.some(job => job.item_key === previous) ? '' : previous);
            mark(false);
        }
    }
    catch {
        if (ticket === epoch.current) {
            setUnknown(true);
            setError('Chưa xác nhận kết quả. Đọc lại trạng thái trước khi làm tiếp. Kiểm tra phê duyệt, phụ thuộc, phiên bản, hạn mức, dữ liệu cũ hoặc model chưa sẵn sàng. Không tự gửi lại.');
        }
    }
    finally {
        if (ticket === epoch.current) {
            lock.current = false;
            setBusy(false);
        }
    } }
    const disabled = busy || unknown || draftDirty || !state;
    const [legacyModelOpen,setLegacyModelOpen]=useState(false);
    const progress = businessProgress(state?.jobs);
    function makeBudget(e: FormEvent) { e.preventDefault(); void act(path + '/budgets', { request_key: crypto.randomUUID(), plan_revision: plan.revision, account_id: account, campaign_id: campaign, currency: plan.currency, cap, headroom, opening_spent: opening, observed_at: new Date().toISOString(), max_age_seconds: 3600, confirm_simulation: true }, 'Tạo ngân sách MÔ PHỎNG cho đúng SME/kế hoạch/tài khoản này? Không phải số dư hoặc chi tiêu thật.'); }
    function propose(e: FormEvent) { e.preventDefault(); const job = state?.jobs.find(j => j.id === jobId); if (!job?.artifact_hash)
        return; void act(base + '/actions', { request_key: crypto.randomUUID(), job_id: job.id, budget_id: budgetId, kind: 'mock_ads_budget', amount: charge, artifact_hash: job.artifact_hash, confirm_simulation: true }, 'Giữ hạn mức và tạo đề xuất MÔ PHỎNG từ đúng bản nháp đã duyệt? Chưa chạy hoặc sửa quảng cáo thật.'); }
    return <section id="bp-run" tabIndex={-1} aria-label="Vận hành kế hoạch S5"><h2>{view==='report'?'Báo cáo vận hành':view==='review'?'Duyệt kết quả và hành động mô phỏng':'Công việc AI'}</h2><p className="bp-warning">AI soạn văn bản có thể gọi model đã chọn khi bạn xác nhận. Hành động đăng bài/quảng cáo bên dưới chỉ MÔ PHỎNG, không gọi nền tảng thật. Token/chi phí model theo sổ tài nguyên hiện có; ngân sách chiến dịch mô phỏng không phải phí API.</p>
  <button disabled={busy} onClick={() => void load()}>Đọc lại vận hành kế hoạch</button>{error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
  <p className="bp-observation" role="note">{readAt ? 'Đọc trạng thái lúc '+new Date(readAt).toLocaleTimeString('vi-VN')+'. ' : 'Chưa xác minh trạng thái. '}Khi có job đang chờ/chạy, tự đọc lại mỗi 5 giây trong tab đang mở và có mạng. Lỗi đọc dừng tự cập nhật; bấm Đọc lại để đối soát. Không tự gửi lại lệnh hoặc gọi AI.</p>
  {state&&<dl className="bp-progress" aria-label="Tiến độ vận hành đã xác minh"><div><dt>Đang chờ/chạy</dt><dd>{progress.active}</dd></div><div><dt>Chờ duyệt nội dung</dt><dd>{progress.waitingReview}</dd></div><div><dt>Nội dung được duyệt còn hiệu lực</dt><dd>{progress.approved}</dd></div><div><dt>Cần xem xét làm lại</dt><dd>{progress.needsRework}</dd></div></dl>}
  {unknown&&<p role="note">Không xác nhận được kết quả gửi/lần đọc gần nhất. Tải lại đúng liên kết kế hoạch rồi đối chiếu job, bản nháp, đề xuất và báo cáo đã lưu. Không bấm chạy lại để vượt trạng thái chưa rõ.</p>}
  {draftDirty && <p role="note">Lưu hoặc đọc lại hồ sơ/kế hoạch trước khi thực hiện. Chỉ phiên bản đã duyệt mới được chạy.</p>}
  {state && <><p role="status">{state.stopped ? 'ĐÃ DỪNG S5 của doanh nghiệp — không khởi chạy hoặc công bố kết quả mới.' : 'S5 chưa dừng khẩn cấp. Mỗi công việc vẫn cần đủ điều kiện riêng.'}</p>
   {member?.role === 'owner' && <button disabled={disabled} onClick={() => void act(base + '/control', { request_key: crypto.randomUUID(), stopped: !state.stopped, confirm: true }, state.stopped ? 'Mở lại S5? Mọi quyền và phê duyệt vẫn phải còn hiệu lực.' : 'Dừng S5 của SME này? Không tự hủy/hoàn tác hành động bên ngoài đã xảy ra. Không tự giải phóng khoản chưa rõ.')}>{state.stopped ? 'Mở lại S5' : 'Dừng khẩn cấp S5'}</button>}
   <div hidden={view!=='jobs'}><h3>Chạy AI soạn bản nháp</h3><p>Kế hoạch phải được duyệt và đã tạo công việc nháp. Công việc phụ thuộc chỉ chạy khi kết quả nguồn được chủ doanh nghiệp duyệt. Kỹ năng cần nhận trường văn bản “text”; hồ sơ/brief/phụ thuộc do máy chủ ghép và kiểm giới hạn, không tự cắt dữ liệu. Một lần khởi chạy không tự thử lại khi lỗi.</p>
   <fieldset disabled={disabled || state.stopped || !routing}><div className="bp-grid"><label>Công việc<select aria-label="Công việc chạy AI S5" value={item} onChange={e => setItem(e.target.value)}><option value="">Chọn công việc chưa chạy</option>{plan.content.deliverables.filter(d => !state.jobs.some(j => j.item_key === d.key)).map(d => <option key={d.key} value={d.key}>{d.title}</option>)}</select></label><label>Model cho lần chạy<select aria-label="Model chạy AI S5" value={target} onChange={e => {setTarget(e.target.value);setGrant('')}}><option value="">Kế thừa cấu hình</option>{routing?.content.targets.map(t => <option key={t.key} value={t.key}>{t.key} · {t.provider} · {t.model}</option>)}</select></label></div>
    <details onToggle={event=>setLegacyModelOpen(event.currentTarget.open)}><summary>Kết nối model cũ (nâng cao)</summary><p>Tài nguyên AI dùng chung và model trên máy không cần chọn quyền AI riêng. Chỉ dùng mục này để tương thích cấu hình kết nối cũ.</p>{legacyModelOpen&&<label>Quyền model cũ<BusinessModelPicker mode="grant" brand={brandId} label="Quyền chạy AI S5" value={grant} onChange={setGrant}/></label>}</details>
    <button disabled={!item} onClick={() => void act(path + '/jobs', { request_key: crypto.randomUUID(), routing_revision: routing!.revision, plan_revision: plan.revision, item_key: item, confirm_model_call: true, job: target ? { target } : {}, grant_id: grant || null }, 'Gọi AI đã chọn để soạn bản nháp từ hồ sơ và đầu việc đã duyệt? Có thể tiêu tốn token/phí model. Không đăng bài hoặc chạy quảng cáo.')}>Chạy AI soạn bản nháp</button>
   </fieldset>
   </div>
   {state.restricted_jobs > 0 && <p>Có công việc bị giới hạn bởi quyền Brain; quyền chủ SME không tự cho phép đọc Brain riêng tư.</p>}
   <div hidden={view==='report'}>{state.jobs.filter(job=>view!=='review'||Boolean(job.artifact_hash)).map(job => <article className="bp-deliverable" key={job.id} aria-label={'Lượt chạy '+job.item_key}><h4>{plan.content.deliverables.find(d => d.key === job.item_key)?.title || job.item_key}</h4><p>{businessJobLabel(job)} · {job.provider} / {job.model} · {job.content_approved ? 'Nội dung đã duyệt' : job.content_decision === 'reject' ? 'Nội dung bị từ chối' : 'Chưa duyệt nội dung'}</p>{job.error_code && <p role="note">Lượt chạy không đạt. Kiểm tra quyền, nguồn, hạn mức và model; không tự chạy lại. Mã đối soát: {job.error_code}</p>}
    <details><summary>Thông tin đối soát lượt chạy</summary><p>Mã job: {job.id}. Model {job.provider}/{job.model}. Kết quả duyệt áp dụng riêng cho hash {job.artifact_hash||'chưa có'}, không phải quyền đăng bài hoặc chạy Ads.</p></details>
    {(['failed','cancelled'].includes(job.status)||job.content_decision==='reject')&&<div><p>Muốn làm lại: chuẩn bị kế hoạch mới, giữ lịch sử cũ và duyệt/chạy riêng. Không tự retry hoặc sao chép phê duyệt/khoản tiền.</p><button disabled={disabled||dirty||state.jobs.some(j=>['queued','running'].includes(j.status))} onClick={onRework}>Chuẩn bị kế hoạch làm lại</button></div>}
    {job.artifact != null && <details><summary>Xem bản nháp — nội dung AI chưa là bằng chứng</summary><pre>{JSON.stringify(job.artifact, null, 2)}</pre></details>}
    {view==='review' && member?.role === 'owner' && job.artifact_hash && !job.content_decision && <><button disabled={disabled} onClick={() => void act(base + '/jobs/' + job.id + '/review', { request_key: crypto.randomUUID(), decision: 'approve', artifact_hash: job.artifact_hash, confirm_review: true }, 'Tôi đã kiểm tra nội dung bản nháp này và duyệt đúng hash kết quả? Đây không phải quyền thực hiện hành động bên ngoài.')}>Duyệt bản nháp</button><button disabled={disabled} onClick={() => void act(base + '/jobs/' + job.id + '/review', { request_key: crypto.randomUUID(), decision: 'reject', artifact_hash: job.artifact_hash, confirm_review: true }, 'Từ chối bản nháp này? Không tự chạy AI sửa hoặc đăng bản nháp.')}>Từ chối bản nháp</button></>}
    {['queued', 'running'].includes(job.status) && <button disabled={disabled||job.cancel_requested} onClick={() => void act(base + '/jobs/' + job.id + '/cancel', { request_key: crypto.randomUUID() }, 'Yêu cầu hủy lượt chạy? Chi phí đã phát sinh không được hoàn tác.')}>{job.cancel_requested?'Đang chờ xác nhận hủy':'Hủy lượt chạy'}</button>}
   </article>)}</div>
   <div hidden={view!=='review'}><details><summary>Ngân sách chiến dịch và hành động mô phỏng</summary><p>Dùng mã mock:… để tách hoàn toàn tài khoản thử. Nhập số thập phân chính xác, không dùng dấu phân cách hàng nghìn. VND/JPY không có phần lẻ. Tiền chưa rõ được giữ lại; dữ liệu quan sát quá 1 giờ chặn đề xuất mới.</p>
    {state.budgets.map(b => <article className="bp-deliverable" key={b.id}><h4>{b.account_id} / {b.campaign_id}</h4><p>Trần {amount(b.cap_minor, b)} · Khả dụng {amount(b.available_minor, b)} · Đang giữ {amount(b.reserved_minor, b)} · Chi mô phỏng {amount(b.spent_minor, b)} · Đã giải phóng {amount(b.released_minor, b)}{b.stale ? ' · Dữ liệu đã cũ' : ''}</p></article>)}
    {member?.role === 'owner' && <form onSubmit={makeBudget}><fieldset disabled={disabled || state.stopped} onChange={() => mark(true)}><div className="bp-grid"><label>Tài khoản mô phỏng<input aria-label="Tài khoản ngân sách S5" required pattern="mock:[a-zA-Z0-9_-]{1,60}" value={account} onChange={e => setAccount(e.target.value)}/></label><label>Chiến dịch mô phỏng<input aria-label="Chiến dịch ngân sách S5" required pattern="mock:[a-zA-Z0-9_-]{1,60}" value={campaign} onChange={e => setCampaign(e.target.value)}/></label>{([['Trần ngân sách', cap, setCap], ['Dự phòng an toàn', headroom, setHeadroom], ['Đã chi lúc quan sát', opening, setOpening]] as const).map(([label, value, setter]) => <label key={label}>{label} ({plan.currency})<input aria-label={label + ' S5'} required inputMode="decimal" value={value} onChange={e => setter(e.target.value)}/></label>)}</div><button type="submit">Tạo ngân sách mô phỏng</button></fieldset></form>}
    <form onSubmit={propose}><fieldset disabled={disabled || state.stopped} onChange={() => mark(true)}><div className="bp-grid"><label>Bản nháp đã duyệt<select aria-label="Bản nháp đề xuất S5" required value={jobId} onChange={e => setJobId(e.target.value)}><option value="">Chọn bản nháp</option>{state.jobs.filter(j => j.content_approved).map(j => <option key={j.id} value={j.id}>{j.item_key}</option>)}</select></label><label>Ngân sách sử dụng<select aria-label="Ngân sách đề xuất S5" required value={budgetId} onChange={e => setBudgetId(e.target.value)}><option value="">Chọn ngân sách</option>{state.budgets.map(b => <option key={b.id} value={b.id}>{b.account_id}/{b.campaign_id} · {b.currency}</option>)}</select></label><label>Số tiền mô phỏng<input aria-label="Số tiền đề xuất S5" required inputMode="decimal" value={charge} onChange={e => setCharge(e.target.value)}/></label></div><button type="submit">Tạo đề xuất và giữ hạn mức mô phỏng</button></fieldset></form>
    {state.actions.map(action => <article className="bp-deliverable" key={action.id}><h4>Đề xuất mô phỏng · {action.id.slice(0, 8)}</h4><p>{status[action.status] || 'Chưa rõ'} · {action.decision === 'reject' ? 'Đã từ chối' : action.decision === 'approve' ? 'Đã duyệt riêng hành động' : 'Chưa duyệt hành động'}</p>{member?.role === 'owner' && <fieldset disabled={disabled}>{!action.decision && <><button onClick={() => void act(base + '/actions/' + action.id + '/review', { request_key: crypto.randomUUID(), decision: 'approve', confirm_simulation: true }, 'Duyệt riêng hành động MÔ PHỎNG và khoản tiền đã giữ này? Không duyệt quảng cáo thật.')}>Duyệt hành động mô phỏng</button><button onClick={() => void act(base + '/actions/' + action.id + '/review', { request_key: crypto.randomUUID(), decision: 'reject', confirm_simulation: true }, 'Từ chối đề xuất và giải phóng khoản mô phỏng?')}>Từ chối và giải phóng hạn mức</button></>}{action.decision === 'approve' && action.status === 'awaiting_execution' && <><button disabled={state.stopped} onClick={() => void act(base + '/actions/' + action.id + '/simulate', { request_key: crypto.randomUUID(), outcome: 'success', confirm_simulation: true }, 'Ghi nhận mô phỏng thành công? Không có lời gọi dịch vụ bên ngoài.')}>Mô phỏng thành công</button><button disabled={state.stopped} onClick={() => void act(base + '/actions/' + action.id + '/simulate', { request_key: crypto.randomUUID(), outcome: 'unknown', confirm_simulation: true }, 'Mô phỏng kết quả chưa rõ và tiếp tục giữ hạn mức, không tự chạy lại?')}>Mô phỏng kết quả chưa rõ</button></>}{action.status === 'unknown' && <><button onClick={() => void act(base + '/actions/' + action.id + '/reconcile', { request_key: crypto.randomUUID(), outcome: 'success', note: 'Chủ doanh nghiệp xác nhận kết quả mô phỏng thành công.', confirm_simulation: true }, 'Đối soát mô phỏng thành công và chuyển khoản đang giữ thành chi mô phỏng?')}>Đối soát thành công</button><button onClick={() => void act(base + '/actions/' + action.id + '/reconcile', { request_key: crypto.randomUUID(), outcome: 'failure', note: 'Chủ doanh nghiệp xác nhận mô phỏng không thực hiện, giải phóng hạn mức.', confirm_simulation: true }, 'Đối soát mô phỏng không thực hiện và giải phóng hạn mức? Không gọi lại dịch vụ.')}>Đối soát không thực hiện</button></>}</fieldset>}</article>)}
    {member?.role==='owner'&&state.actions.filter(a=>['awaiting_execution','awaiting_approval'].includes(a.status)&&a.decision!=='reject').map(a=><button key={'cancel:'+a.id} disabled={disabled} onClick={()=>void act(base+'/actions/'+a.id+'/cancel',{request_key:crypto.randomUUID(),confirm_simulation:true},'Hủy đề xuất chưa mô phỏng và giải phóng đúng khoản đang giữ? Khoản có kết quả chưa rõ phải đi qua đối soát, không được hủy để chạy lại.')}>Hủy đề xuất chưa thực hiện · {a.id.slice(0,8)}</button>)}
   </details>
   </div><div hidden={view!=='report'}><h3 id="bp-report" tabIndex={-1}>Báo cáo và lịch nội bộ</h3><p>Báo cáo ghim nguồn, khoảng thời gian, model/usage và dữ liệu còn thiếu. Chưa có số liệu doanh thu/quảng cáo thật thì giữ “chưa rõ”, không coi là 0. Lịch dùng bộ lập lịch P6 hiện có, không tự gửi Telegram/email.</p>
   <fieldset disabled={disabled}><button onClick={() => { const end = new Date(); void act(path + '/reports', { request_key: crypto.randomUUID(), window_from: new Date(end.getTime() - 86400000).toISOString(), window_to: end.toISOString() }, 'Lưu báo cáo tiến độ 24 giờ từ dữ liệu nội bộ? Không gọi AI hoặc dịch vụ bên ngoài.'); }}>Tạo báo cáo tiến độ 24 giờ</button><label>Chu kỳ báo cáo<select aria-label="Chu kỳ báo cáo S5" value={cadence} onChange={e => setCadence(e.target.value)}><option value="hourly">Hàng giờ</option><option value="daily">Hàng ngày theo múi giờ hồ sơ</option></select></label><button disabled={state.stopped} onClick={() => void act(path + '/report-schedule', { request_key: crypto.randomUUID(), enabled: true, cadence, confirm_internal_only: true }, 'Bật lịch báo cáo nội bộ qua bộ lập lịch hiện có? Không tự gửi ra kênh bên ngoài.')}>Bật lịch báo cáo nội bộ</button><button onClick={() => void act(path + '/report-schedule', { request_key: crypto.randomUUID(), enabled: false, cadence, confirm_internal_only: true }, 'Tắt lịch báo cáo nội bộ của kế hoạch này?')}>Tắt lịch báo cáo nội bộ</button></fieldset><p>{state.schedule?.enabled ? 'Đã đặt lịch ' + (state.schedule.cadence === 'hourly' ? 'hàng giờ' : 'hàng ngày') + '; chỉ chạy khi worker, quyền và phê duyệt còn hiệu lực.' : 'Chưa bật lịch báo cáo.'}</p>
   {state.reports.map(row => <details key={row.id}><summary>Báo cáo {new Date(row.report.window_to).toLocaleString('vi-VN')}</summary><p>Đầu việc dự kiến: {row.report.planned_tasks} · Chưa chạy: {row.report.not_started}. Token vào: {row.report.model_usage.input_tokens ?? 'Chưa rõ'} · Token ra: {row.report.model_usage.output_tokens ?? 'Chưa rõ'}.</p><p>Nguồn: sổ vận hành nội bộ · {new Date(row.report.window_from).toLocaleString('vi-VN')} → {new Date(row.report.window_to).toLocaleString('vi-VN')}. Không phải dữ liệu quảng cáo trực tiếp.</p><p>Chưa có chi tiêu quảng cáo thật, KPI kinh doanh đã đo hoặc quota nhà cung cấp còn lại.</p><ul aria-label="Chỉ số chưa có dữ liệu đo">{row.report.kpis.map((k,i)=><li key={i}>{k.name} · mục tiêu {k.target??'Chưa xác định'} {k.unit} · thực tế: Chưa có dữ liệu</li>)}</ul>{row.report.missing_data.length>0&&<p role="note">Còn thiếu {row.report.missing_data.length} nhóm dữ liệu. Không suy ra số 0 hoặc hiệu quả kinh doanh từ báo cáo này.</p>}<ul>{row.report.tasks.map(t => <li key={t.id}>{t.item_key} · {status[t.status] || 'Chưa rõ'} · {t.model}</li>)}</ul></details>)}
  </div></>}
 </section>;
}
