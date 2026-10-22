"""Bounded SELECT-only tools. No connector calls, report creation or delivery."""
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import select, func
from .access import membership
from .models import (AdReport, MetaConnection, Task, AdIntelligenceRun, AdAnomaly,
                     CreativeAnalysisRun, CreativeFeature, AttributionRun, AttributionMetric,
                     AttributionSource, now)
from .skills import validate_input, snapshot, evaluate_result

DAILY_TOOLS = ('business.kpi.read', 'business.tasks.read')


async def read_attribution(db, who, workspace_id, arguments):
    """Saved attribution only. Never analyze, ingest, acknowledge or aggregate currencies."""
    await membership(db, workspace_id, who)
    args = validate_input('investigate-ads-drop', 'chief_of_staff', arguments, ['business.attribution.read'])
    result = {'tool': 'business.attribution.read', 'status': 'insufficient_data',
              'data': {'snapshot': None, 'metrics': [], 'totals_combined': False,
                       'verified_business_revenue': False}, 'source_references': [], 'missing_data': []}
    missing = result['missing_data']
    if args['platform'] != 'meta':
        missing.append('platform: chưa hỗ trợ Google Ads attribution wrapper')
        return result
    conn = await db.scalar(select(MetaConnection).where(
        MetaConnection.workspace_id == workspace_id, MetaConnection.user_id == who.id))
    if not conn or conn.status != 'connected' or (conn.expires_at and conn.expires_at <= now()):
        missing.append('meta_connection: kết nối của bạn chưa sẵn sàng')
        return result
    saved = await db.scalar(select(AttributionRun).where(
        AttributionRun.connection_id == conn.id, AttributionRun.connection_version == conn.version,
        AttributionRun.workspace_id == workspace_id, AttributionRun.user_id == who.id,
        AttributionRun.account_id == args['account_id'],
        AttributionRun.period_start == date.fromisoformat(args['start_date']),
        AttributionRun.period_end == date.fromisoformat(args['end_date']))
        .order_by(AttributionRun.created_at.desc(), AttributionRun.id.desc()).limit(1))
    if not saved:
        missing.append('attribution_snapshot: chưa có snapshot đúng account/kỳ/phiên bản kết nối; không tự phân tích')
        return result
    sources = list(await db.scalars(select(AttributionSource).where(
        AttributionSource.connection_id == conn.id, AttributionSource.connection_version == conn.version,
        AttributionSource.workspace_id == workspace_id, AttributionSource.account_id == args['account_id'],
        AttributionSource.enabled.is_(True)).order_by(AttributionSource.id).limit(51)))
    if len(sources) > 50:
        missing.append('source_limit: chỉ kiểm tối đa 50 nguồn hiện bật')
    sources = {item.id: item for item in sources[:50]}
    rows = list(await db.scalars(select(AttributionMetric).where(AttributionMetric.run_id == saved.id)
                                 .order_by(AttributionMetric.id).limit(50)))
    summary = saved.summary if isinstance(saved.summary, dict) else {}
    count = summary.get('campaigns_analyzed')
    if len(rows) > 49 or type(count) is not int or count != len(rows) or not rows:
        missing.append('metric_coverage: snapshot thiếu mẫu, số đếm không khớp hoặc vượt 49 metrics')
    unattributed = summary.get('unattributed', {})
    unattributed = unattributed if isinstance(unattributed, dict) else {}
    counts = {key: value if type(value := unattributed.get(key)) is int and value >= 0 else None
              for key in ('analytics', 'leads', 'orders')}
    if any(value is None or value > 0 for value in counts.values()):
        missing.append('unattributed_coverage: có record chưa phân bổ hoặc chưa biết số lượng')
    result['data']['snapshot'] = {'id': saved.id, 'account_id': saved.account_id,
        'period_start': saved.period_start.isoformat(), 'period_end': saved.period_end.isoformat(),
        'analyst_version': saved.analyst_version, 'source_updated_at': saved.source_updated_at.isoformat(),
        'created_at': saved.created_at.isoformat(), 'unattributed_counts': counts}
    result['source_references'] = [f'attribution-run:{saved.id}']
    for row in rows[:49]:
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        ids = evidence.get('source_ids')
        valid_sources = (isinstance(ids, list) and 0 < len(ids) <= 50 and
                         all(isinstance(key, str) and key in sources and
                             sources[key].updated_at <= saved.created_at and sources[key].currency == row.currency
                             for key in ids))
        order_known = (valid_sources and evidence.get('order_source_connected') is True and
                       any(sources[key].kind == 'orders' and sources[key].currency == row.currency for key in ids))
        if not order_known:
            missing.append(f'order_source:{row.id}: nguồn orders chưa chứng minh; không diễn giải zero là doanh thu thật')
        result['data']['metrics'].append({'id': row.id, 'campaign_id': row.campaign_id,
            'currency': row.currency, 'saved_spend': str(row.spend),
            'platform_reported_revenue': str(row.platform_revenue),
            'attributed_paid_order_revenue': str(row.actual_revenue) if order_known else None,
            'attributed_paid_order_count': row.actual_orders if order_known else None,
            'revenue_discrepancy_pct': str(row.revenue_discrepancy_pct) if order_known and row.revenue_discrepancy_pct is not None else None,
            'tracking_status': row.tracking_status, 'source_ids': list(dict.fromkeys(ids)) if valid_sources else [],
            'interpretation': 'saved_deterministic_campaign_allocation_not_verified_total_revenue'})
        result['source_references'].append(f'attribution-metric:{row.id}')
    if saved.source_updated_at < now() - timedelta(days=1):
        missing.append('source_freshness: snapshot nguồn quá 24 giờ')
    missing = list(dict.fromkeys(missing))
    if len(missing) > 15:
        missing = missing[:15] + ['additional_missing_data: có thêm metric thiếu nguồn; xem trạng thái dữ liệu']
    missing += ['source_version_history: snapshot không pin version từng nguồn ingest hoặc chứng minh đã đối soát',
                'saved_aggregate_quality: analyst cũ có thể coalesce metric thiếu thành 0; không xác minh coverage platform',
                'verified_business_revenue: doanh thu được phân bổ không phải tổng doanh thu doanh nghiệp đã xác minh']
    result['missing_data'] = missing
    return result


async def read_analysis(db, who, workspace_id, arguments, creative=False):
    """Saved analysis snapshots only; never trigger analyze/sync/configuration."""
    await membership(db, workspace_id, who)
    skill_id = 'creative-fatigue-review' if creative else 'investigate-ads-drop'
    tool = 'business.creative.read' if creative else 'business.ads.intelligence.read'
    data = validate_input(skill_id, 'chief_of_staff', arguments, [tool])
    result = {'tool': tool, 'status': 'insufficient_data', 'data': {'snapshot': None},
              'source_references': [], 'missing_data': []}
    if data['platform'] != 'meta':
        result['missing_data'] = ['platform: wrapper hiện chỉ đọc snapshot Meta; chưa hỗ trợ Google Ads']
        return result
    conn = await db.scalar(select(MetaConnection).where(
        MetaConnection.workspace_id == workspace_id, MetaConnection.user_id == who.id))
    if not conn or conn.status != 'connected' or (conn.expires_at and conn.expires_at <= now()):
        result['missing_data'] = ['meta_connection: kết nối của bạn chưa sẵn sàng']
        return result
    start, end = date.fromisoformat(data['start_date']), date.fromisoformat(data['end_date'])
    model = CreativeAnalysisRun if creative else AdIntelligenceRun
    conditions = [model.connection_id == conn.id, model.connection_version == conn.version,
                  model.workspace_id == workspace_id, model.user_id == who.id,
                  model.account_id == data['account_id']]
    if creative:
        conditions += [model.as_of == end, model.as_of - (model.current_days - 1) == start]
    else:
        conditions += [model.period_start == start, model.period_end == end,
                       model.granularity == 'daily', model.hour.is_(None)]
    saved = await db.scalar(select(model).where(*conditions).order_by(model.created_at.desc(), model.id.desc()).limit(1))
    if not saved:
        result['missing_data'] = ['analysis_snapshot: chưa có snapshot đúng account/kỳ/phiên bản kết nối; không tự chạy phân tích']
        return result
    ref = f'{"creative-analysis" if creative else "ads-intelligence"}:{saved.id}'
    fields = ('creative_count', 'fatigued_count', 'watch_count', 'insufficient_count') if creative else (
        'campaigns_analyzed', 'anomalies_detected', 'recommendations_active')
    counts = {key: saved.summary.get(key) for key in fields}
    if any(type(value) is not int or value < 0 for value in counts.values()):
        result['missing_data'].append('snapshot_summary: số đếm thiếu hoặc không hợp lệ')
        counts = {key: value if type(value) is int and value >= 0 else None for key, value in counts.items()}
    if counts.get('creative_count' if creative else 'campaigns_analyzed') == 0:
        result['missing_data'].append('analysis_sample: không có đối tượng đủ dữ liệu để phân tích')
    result['data'] = {'snapshot': {'id': saved.id, 'account_id': saved.account_id,
        'period_start': start.isoformat(), 'period_end': end.isoformat(),
        'analyst_version': saved.analyst_version, 'counts': counts,
        'source_updated_at': saved.source_updated_at.isoformat(), 'created_at': saved.created_at.isoformat()},
        'interpretation': 'saved_analysis_signals_not_verified_causation'}
    result['source_references'] = [ref]
    if not creative:
        result['data']['snapshot']['currency'] = str(saved.summary.get('currency', 'unknown'))[:20]
        result['data']['snapshot']['timezone'] = str(saved.summary.get('timezone', 'unknown'))[:80]
        anomalies = list(await db.scalars(select(AdAnomaly).where(
            AdAnomaly.run_id == saved.id, AdAnomaly.connection_id == conn.id,
            AdAnomaly.connection_version == conn.version, AdAnomaly.workspace_id == workspace_id,
            AdAnomaly.account_id == data['account_id']).order_by(AdAnomaly.id).limit(51)))
        if len(anomalies) > 50 or counts.get('anomalies_detected') != len(anomalies):
            result['missing_data'].append('anomaly_coverage: giới hạn 50 hoặc record đã thay đổi từ lúc tạo snapshot')
        anomalies = anomalies[:50]
        result['data']['anomalies'] = [{'id': item.id, 'resource_id': item.resource_id,
            'kind': item.kind, 'severity': item.severity,
            'current_value': str(item.current_value) if item.current_value is not None else None,
            'baseline_value': str(item.baseline_value) if item.baseline_value is not None else None,
            'deviation_pct': str(item.deviation_pct) if item.deviation_pct is not None else None,
            'resolved': item.resolved} for item in anomalies]
        result['source_references'] += [f'ad-anomaly:{item.id}' for item in anomalies[:49]]
    if creative:
        features = list(await db.scalars(select(CreativeFeature).where(CreativeFeature.run_id == saved.id)
                        .order_by(CreativeFeature.id).limit(51)))
        if len(features) > 50:
            result['missing_data'].append('feature_limit: chỉ đọc 50 creative features')
        features = features[:50]
        if counts.get('insufficient_count', 0) or counts.get('creative_count') != len(features):
            result['missing_data'].append('creative_coverage: snapshot thiếu mẫu hoặc danh sách feature chưa đủ')
        if not features or any(item.fatigue_status == 'insufficient' for item in features):
            result['missing_data'].append('creative_evidence: không có feature hoặc có feature thiếu mẫu')
        result['data']['features'] = [{'id': item.id, 'asset_id': item.asset_id,
            'fatigue_status': item.fatigue_status, 'fatigue_score': str(item.fatigue_score),
            'confidence': str(item.confidence), 'age_days': item.age_days} for item in features]
        result['source_references'] += [f'creative-feature:{item.id}' for item in features[:49]]
    if saved.source_updated_at < now() - timedelta(days=1):
        result['missing_data'].append('source_freshness: dữ liệu nguồn quá 24 giờ; snapshot lịch sử, không xác nhận trạng thái hiện tại')
    result['status'] = 'insufficient_data' if result['missing_data'] else 'completed'
    return result


async def read_intelligence(db, who, workspace_id, arguments):
    return await read_analysis(db, who, workspace_id, arguments)


async def read_creative(db, who, workspace_id, arguments):
    return await read_analysis(db, who, workspace_id, arguments, creative=True)


async def read_tasks(db, who, workspace_id, arguments):
    await membership(db, workspace_id, who)
    period = validate_input('daily-business-brief', 'chief_of_staff', arguments, ['business.tasks.read'])
    start = datetime.combine(date.fromisoformat(period['start_date']), time.min, timezone.utc)
    end = datetime.combine(date.fromisoformat(period['end_date']) + timedelta(days=1), time.min, timezone.utc)
    rows = (await db.execute(select(Task.status, func.count(Task.id)).where(
        Task.workspace_id == workspace_id, Task.created_at >= start, Task.created_at < end
    ).group_by(Task.status))).all()
    return {'tool': 'business.tasks.read', 'status': 'completed',
            'data': {'created_in_period': sum(count for _, count in rows),
                     'current_status_counts': dict(rows), 'date_basis': 'created_at_utc',
                     'status_basis': 'current_not_historical'},
            'source_references': [f'tasks-query:{workspace_id}:{period["start_date"]}:{period["end_date"]}:created-utc'],
            'missing_data': []}


async def read_kpi(db, who, workspace_id, arguments):
    await membership(db, workspace_id, who)
    period = validate_input('investigate-ads-drop' if 'platform' in arguments else 'daily-business-brief',
                            'chief_of_staff', arguments, ['business.kpi.read'])
    if period.get('platform') not in (None, 'meta'):
        return {'tool': 'business.kpi.read', 'status': 'insufficient_data', 'data': {'reports': []},
                'source_references': [], 'missing_data': ['platform: chưa hỗ trợ Google Ads KPI wrapper']}
    conn = await db.scalar(select(MetaConnection).where(
        MetaConnection.workspace_id == workspace_id, MetaConnection.user_id == who.id))
    missing = []
    if not conn or conn.status != 'connected' or (conn.expires_at and conn.expires_at <= now()):
        return {'tool': 'business.kpi.read', 'status': 'insufficient_data', 'data': {'reports': []},
                'source_references': [], 'missing_data': ['meta_connection: kết nối của bạn chưa sẵn sàng; không tự kết nối hoặc đồng bộ']}
    # Latest exact-period report per account. Never add overlapping snapshots or
    # combine currencies. Personal connection visibility matches report_api.
    query = select(AdReport).where(
        AdReport.workspace_id == workspace_id, AdReport.user_id == who.id,
        AdReport.connection_id == conn.id, AdReport.connection_version == conn.version,
        AdReport.period_start == date.fromisoformat(period['start_date']),
        AdReport.period_end == date.fromisoformat(period['end_date'])
    )
    if period.get('account_id'):
        query = query.where(AdReport.account_id == period['account_id'])
    rows = list(await db.scalars(query.distinct(AdReport.account_id).order_by(
        AdReport.account_id, AdReport.created_at.desc(), AdReport.id.desc()).limit(51)))
    if len(rows) > 50:
        missing.append('report_limit: chỉ hiển thị 50 tài khoản; chưa phải toàn bộ dữ liệu')
    rows = rows[:50]
    if not rows:
        missing.append('ads_report: chưa có báo cáo khớp chính xác kỳ yêu cầu; tạo báo cáo qua workflow đã có')
    reports = []
    expected = (date.fromisoformat(period['end_date']) - date.fromisoformat(period['start_date'])).days + 1
    for row in rows:
        if row.coverage_days != expected or row.expected_days != expected or row.data_through != row.period_end:
            missing.append(f'report_coverage:{row.id}: chưa đủ ngày dữ liệu')
        if row.spend is None or row.revenue is None or row.purchases is None:
            missing.append(f'report_metrics:{row.id}: có chỉ số chưa biết, không thay bằng 0')
        reports.append({'report_id': row.id, 'account_id': row.account_id, 'currency': row.currency,
                        'timezone': row.timezone, 'attribution': row.attribution,
                        'spend': str(row.spend) if row.spend is not None else None,
                        'platform_reported_revenue': str(row.revenue) if row.revenue is not None else None,
                        'platform_reported_purchases': str(row.purchases) if row.purchases is not None else None,
                        'coverage_days': row.coverage_days, 'expected_days': expected,
                        'data_through': row.data_through.isoformat() if row.data_through else None,
                        'source_updated_at': row.source_updated_at.isoformat(),
                        'report_created_at': row.created_at.isoformat()})
    return {'tool': 'business.kpi.read', 'status': 'insufficient_data' if missing else 'completed',
            'data': {'reports': reports, 'scope': 'saved_meta_reports_owned_by_requester',
                     'totals_combined': False},
            'source_references': [f'ad-report:{row.id}' for row in rows], 'missing_data': missing}


async def daily_brief_preview(db, who, workspace_id, arguments):
    await membership(db, workspace_id, who)
    validated = validate_input('daily-business-brief', 'chief_of_staff', arguments, DAILY_TOOLS)
    pinned = snapshot('daily-business-brief')
    tasks = await read_tasks(db, who, workspace_id, validated)
    kpi = await read_kpi(db, who, workspace_id, validated)
    # The enterprise brief is intentionally incomplete until verified business
    # revenue is connected. Platform-attributed revenue is not business revenue.
    missing = list(dict.fromkeys(kpi['missing_data'] + [
        'verified_business_revenue: chưa nối nguồn doanh thu doanh nghiệp đã xác minh']))
    references = tasks['source_references'] + kpi['source_references']
    result = {'status': 'insufficient_data',
              'summary': f"Bản xem trước: {tasks['data']['created_in_period']} task tạo trong kỳ (UTC), "
                         f"{len(kpi['data']['reports'])} báo cáo Meta đã lưu khớp kỳ. "
                         'Chưa đủ dữ liệu cho báo cáo doanh nghiệp hoàn chỉnh; không có hành động được thực hiện.',
              'source_references': references, 'missing_data': missing}
    # Bounded tools can report more than evaluator's 20 reasons. Collapse rather
    # than drop the fact that the underlying data is incomplete.
    if len(result['missing_data']) > 20:
        result['missing_data'] = result['missing_data'][:18] + [
            'additional_missing_data: xem chi tiết trong tools', missing[-1]]
    # 50 report refs plus one query ref: keep result bounded, details in tools.
    result['source_references'] = references[:50]
    return {'skill': pinned, 'input': validated, 'read_only': True,
            'result': evaluate_result(pinned, result), 'tools': [tasks, kpi],
            'retrieved_at': now().isoformat()}
