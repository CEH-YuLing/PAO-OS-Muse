import json
from pathlib import Path


FIXTURES = Path(__file__).parents[3] / 'evals' / 'stage2_quality.json'


def test_stage2_quality_fixture_is_machine_readable_and_complete():
    suite = json.loads(FIXTURES.read_text(encoding='utf-8'))
    assert suite['version'] == 1
    cases = {case['id']: case for case in suite['cases']}
    assert {case['category'] for case in cases.values()} == {
        'metric_definition', 'missing_data', 'source_conflict', 'permission'
    }
    assert all(case['expected']['status'] for case in cases.values())
    assert all(case['expected'].get('forbidden_claims') or
               case['expected'].get('forbidden_side_effects') for case in cases.values())

    metric = cases['metric-order-to-view']
    calculated = metric['input']['orders'] / metric['input']['views'] * 100
    assert calculated == metric['expected']['facts']['order_to_view_rate_pct']

    conflict = cases['conflicting-purchase-sources']
    platform = conflict['input']['platform']['purchases']
    orders = conflict['input']['orders']['paid']
    assert platform - orders == conflict['expected']['facts']['absolute_difference']
    assert round((platform - orders) / platform * 100, 4) == conflict['expected']['facts']['platform_difference_pct']
