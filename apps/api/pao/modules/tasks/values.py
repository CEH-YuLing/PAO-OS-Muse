"""Pure Task value helpers, shared without importing HTTP adapters."""
import hashlib
import json


def bounded_json(value, limit=32_000):
    if len(json.dumps(value, ensure_ascii=False)) > limit:
        raise ValueError('Dữ liệu có cấu trúc quá lớn')
    return value


def clean_criteria(value):
    if value is None:
        return value
    cleaned = [item.strip() for item in value if item.strip()]
    if any(len(item) > 500 for item in cleaned):
        raise ValueError('Mỗi tiêu chí tối đa 500 ký tự')
    return cleaned


def attempt_fingerprint(input_data: dict, run_id) -> str:
    raw = json.dumps({'input': input_data, 'run_id': str(run_id) if run_id else None},
                     sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()
