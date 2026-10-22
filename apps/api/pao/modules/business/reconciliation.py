"""Compare user-supplied export totals with one saved report; never sync Ads."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExportTotals(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account_id: str = Field(pattern=r'^act_[0-9]{1,32}$')
    period_start: date
    period_end: date
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    timezone: str = Field(min_length=1, max_length=80)
    attribution: str = Field(min_length=1, max_length=120)
    exported_at: datetime
    file_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    spend: Decimal | None = Field(ge=0, max_digits=24, decimal_places=6)
    clicks: int | None = Field(ge=0, strict=True)
    platform_reported_purchases: Decimal | None = Field(ge=0, max_digits=24, decimal_places=6)

    @field_validator('spend', 'platform_reported_purchases', mode='before')
    @classmethod
    def explicit_decimal(cls, value):
        if value is not None and not isinstance(value, (str, Decimal)):
            raise ValueError('Use decimal strings, not floating-point or boolean values')
        return value

    @model_validator(mode='after')
    def scope(self):
        if self.period_end < self.period_start or (self.period_end-self.period_start).days >= 30:
            raise ValueError('Compare at most 30 inclusive days')
        if self.exported_at.utcoffset() is None:
            raise ValueError('exported_at requires timezone')
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError('Unknown account timezone') from None
        return self


class MetricDifference(BaseModel):
    metric: str
    saved: str | None
    supplied: str | None
    difference: str | None
    status: Literal['match', 'mismatch', 'unknown']


class ReconciliationOut(BaseModel):
    report_id: str
    status: Literal['values_match', 'mismatch', 'incomparable', 'insufficient_data']
    read_only: Literal[True] = True
    business_verified: Literal[False] = False
    provenance: Literal['user_supplied_not_authenticated'] = 'user_supplied_not_authenticated'
    file_sha256: str
    source_updated_at: datetime
    scope_issues: list[str]
    metrics: list[MetricDifference]
    next_steps: list[str]


def compare_report(report, export: ExportTotals):
    scope = []
    for field in ('account_id', 'period_start', 'period_end', 'currency', 'timezone', 'attribution'):
        if getattr(report, field) != getattr(export, field):
            scope.append(field)
    days = (export.period_end-export.period_start).days + 1
    if report.coverage_days != days or report.expected_days != days or report.data_through != export.period_end:
        scope.append('report_coverage')
    metrics = []
    if not scope:
        for label, saved in [('spend', report.spend), ('clicks', report.clicks),
                             ('platform_reported_purchases', report.purchases)]:
            supplied = getattr(export, label)
            delta = Decimal(saved)-Decimal(supplied) if saved is not None and supplied is not None else None
            metrics.append(MetricDifference(metric=label, saved=str(saved) if saved is not None else None,
                supplied=str(supplied) if supplied is not None else None,
                difference=str(delta) if delta is not None else None,
                status='unknown' if delta is None else 'match' if delta == 0 else 'mismatch'))
    status = ('incomparable' if scope else 'insufficient_data' if any(m.status == 'unknown' for m in metrics)
              else 'mismatch' if any(m.status == 'mismatch' for m in metrics) else 'values_match')
    return ReconciliationOut(report_id=str(report.id), status=status, file_sha256=export.file_sha256,
        source_updated_at=report.source_updated_at, scope_issues=scope, metrics=metrics,
        next_steps=['Đối chiếu account, kỳ, timezone, currency, attribution và coverage trước so số.',
                    'Purchases là chỉ số mua hàng Meta báo cáo, không phải mọi conversion hay doanh thu doanh nghiệp.',
                    'Hash/totals do người dùng cung cấp chưa xác thực file chính thức. Không coi values_match là M3 đã đạt.'])
