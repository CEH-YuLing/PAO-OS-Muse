"""Conservative v1 command router; only full user commands, never history."""
import re
import json
import unicodedata
from pydantic import ValidationError
from .skills import validate_input

LABELS = {'bao cao doanh nghiep': 'daily-business-brief',
          'daily business brief': 'daily-business-brief',
          'dieu tra hieu qua quang cao giam': 'investigate-ads-drop',
          'danh gia creative fatigue': 'creative-fatigue-review'}

SKILL_TOOLS = {'daily-business-brief': ('business.tasks.read', 'business.kpi.read'),
               'investigate-ads-drop': ('business.kpi.read', 'business.ads.intelligence.read'),
               'creative-fatigue-review': ('business.creative.read', 'business.ads.intelligence.read')}


def tool_plan(selection):
    tools = SKILL_TOOLS[selection['skill_id']]
    validate_input(selection['skill_id'], 'chief_of_staff', selection['input'], tools)
    return tools


def analysis_response(selection, results):
    args = selection['input']
    lines = [f"Bản xem trước {selection['skill_id']}: {args['platform']} {args['account_id']} · {args['start_date']} → {args['end_date']}",
             'Chưa đủ dữ liệu để xác minh nguyên nhân. Tín hiệu đã lưu không chứng minh quan hệ nhân quả.']
    missing, references, displayed_sources = [], [], []
    def known(value):
        return 'chưa biết' if value is None else str(value)
    for result in results:
        lines.append(result['tool'])
        missing.extend(result['missing_data'])
        references.extend(result['source_references'])
        data = result['data']
        if data.get('snapshot'):
            saved = data['snapshot']
            lines.append(f"Snapshot {saved['id']}, cập nhật {saved['source_updated_at']}; số đếm: " + json.dumps(saved['counts'], ensure_ascii=False))
        for row in data.get('reports', [])[:10]:
            displayed_sources.append(f"ad-report:{row['report_id']}")
            spend = row['spend'] if row['spend'] is not None else 'chưa biết'
            revenue = row['platform_reported_revenue'] if row['platform_reported_revenue'] is not None else 'chưa biết'
            lines.append(f"{row['account_id']}: spend {spend}, doanh thu do Ads báo cáo {revenue} {row['currency']}; "
                         f"nguồn ad-report:{row['report_id']}, cập nhật {row['source_updated_at']}")
        for row in data.get('anomalies', [])[:10]:
            displayed_sources.append(f"ad-anomaly:{row['id']}")
            deviation = 'chưa biết' if row['deviation_pct'] is None else f"{row['deviation_pct']}%"
            lines.append(f"Anomaly {row['kind']}: current {known(row['current_value'])}, baseline {known(row['baseline_value'])}, "
                         f"deviation {deviation}; nguồn ad-anomaly:{row['id']}")
        for row in data.get('features', [])[:10]:
            displayed_sources.append(f"creative-feature:{row['id']}")
            lines.append(f"Creative {row['asset_id']}: tín hiệu {row['fatigue_status']}, confidence {row['confidence']}; nguồn creative-feature:{row['id']}")
        if len(data.get('anomalies', [])) > 10 or len(data.get('features', [])) > 10:
            lines.append('Câu trả lời chỉ hiển thị 10 tín hiệu mỗi tool; chi tiết ở trace Tool Gateway.')
    missing = list(dict.fromkeys(missing))
    if len(missing) > 18:
        missing = missing[:18] + ['additional_missing_data: xem trace Tool Gateway']
    missing.append('causal_validation: chưa đối chiếu dữ liệu/baseline để xác minh nguyên nhân')
    references = list(dict.fromkeys(references))
    # Keep each contributing snapshot/report before child records when capped.
    roots = [ref for ref in references if not ref.startswith(('ad-anomaly:', 'creative-feature:'))]
    preferred = roots + [ref for ref in displayed_sources if ref in references]
    references = list(dict.fromkeys(preferred + references))
    lines += missing + ['Nguồn: ' + ', '.join(references[:50]), 'Chỉ đọc dữ liệu; không sửa Ads hoặc gửi báo cáo.']
    response = '\n'.join(lines)
    return response, {'status': 'insufficient_data', 'summary': response[:4000],
                      'source_references': references[:50], 'missing_data': missing}


def select_skill(prompt):
    text = ''.join(char for char in unicodedata.normalize('NFD', prompt.lower())
                   if unicodedata.category(char) != 'Mn').replace('đ', 'd')
    text = re.sub(r'\s+', ' ', text).strip().rstrip('.!?')
    text = re.sub(r'^(?:hay |giup toi |cho toi )', '', text)
    for label, skill_id in LABELS.items():
        if text != label and not text.startswith(label + ' '):
            continue
        suffix = text[len(label):].strip()
        expression = r'(?:tu |from )?(\d{4}-\d{2}-\d{2}) (?:den|to|-) (\d{4}-\d{2}-\d{2})'
        if skill_id != 'daily-business-brief':
            expression = r'(meta|google_ads) (act_[0-9]{1,32}|[0-9-]{1,32}) (?:tu |from )?' + r'(\d{4}-\d{2}-\d{2}) (?:den|to|-) (\d{4}-\d{2}-\d{2})'
        dates = re.fullmatch(expression, suffix)
        if not dates:
            return {'skill_id': skill_id, 'status': 'needs_input', 'input': {},
                    'message': ('Hãy dùng: Báo cáo doanh nghiệp từ YYYY-MM-DD đến YYYY-MM-DD.' if skill_id == 'daily-business-brief'
                                else 'Hãy dùng tên kỹ năng + meta act_123 từ YYYY-MM-DD đến YYYY-MM-DD.') + ' Không tự đoán account hoặc kỳ báo cáo.'}
        keys = ('start_date', 'end_date') if skill_id == 'daily-business-brief' else ('platform', 'account_id', 'start_date', 'end_date')
        arguments = dict(zip(keys, dates.groups()))
        if arguments.get('platform') == 'meta' and not arguments['account_id'].startswith('act_'):
            return {'skill_id': skill_id, 'status': 'needs_input', 'input': {}, 'message': 'Tài khoản Meta cần dạng act_123.'}
        try:
            arguments = validate_input(skill_id, 'chief_of_staff', arguments)
        except ValidationError:
            return {'skill_id': skill_id, 'status': 'needs_input', 'input': {},
                    'message': 'Kỳ báo cáo không hợp lệ: ngày kết thúc phải sau hoặc bằng ngày bắt đầu, tối đa 366 ngày chênh lệch.'}
        return {'skill_id': skill_id, 'status': 'ready', 'input': arguments,
                'message': 'Chỉ đọc dữ liệu đã lưu; không thực hiện hành động ngoài.'}
    return None
