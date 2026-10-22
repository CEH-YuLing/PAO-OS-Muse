"""Data-only result validation. A valid fixture is not evidence of a model run.

Callers must separately verify the version pin and execution authorization.
No database, queue, provider, shell, or workflow state changes occur here.
"""
from copy import deepcopy
import re

from .contracts import canonical, digest, safe_schema, validate_value


def verify_result(contract, input_value, output_value):
    """Validate both schemas and every exit criterion; return content hashes only.

    Schema-only checks deliberately make no claims about model weights, tool
    evidence, semantic quality, or successful execution of a business task.
    """
    if not isinstance(contract, dict):
        raise ValueError('studio_result_contract')
    for name, value in (('input_schema', input_value), ('output_schema', output_value)):
        schema = safe_schema(contract.get(name))
        if schema['type'] != 'object':
            raise ValueError('studio_result_root_object')
        validate_value(schema, value)
    criteria = contract.get('exit_criteria', [])
    if not isinstance(criteria, list) or len(criteria) > 5:
        raise ValueError('studio_exit_criteria')
    checks = []
    for criterion in criteria:
        match = re.fullmatch(r'(non_empty|equals_input):([a-zA-Z][a-zA-Z0-9_]{0,59})', criterion) if isinstance(criterion, str) else None
        if not match:
            raise ValueError('studio_exit_criteria_subset')
        rule, field = match.groups()
        schema = contract['output_schema']
        if field not in schema.get('required', []) or schema['properties'].get(field, {}).get('type') != 'string':
            raise ValueError('studio_exit_criteria_field')
        if rule == 'equals_input' and field not in contract['input_schema'].get('required', []):
            raise ValueError('studio_exit_criteria_input')
        if rule == 'non_empty' and not output_value[field].strip():
            raise ValueError('studio_exit_criteria_failed')
        if rule == 'equals_input' and output_value[field] != input_value[field]:
            raise ValueError('studio_exit_criteria_failed')
        checks.append(criterion)
    # Bound canonical JSON independently from field-level limits, including
    # optional nested arrays. Never include supplied values in error messages.
    if any(len(canonical(value).encode()) > 24576 for value in (input_value, output_value)):
        raise ValueError('studio_result_too_large')
    receipt = {
        'format': 'p62-schema-receipt-v1',
        'contract_hash': digest(contract),
        'input_hash': digest(input_value),
        'output_hash': digest(output_value),
        'checks': checks,
        'mode': 'schema_only',
        'model_executed': False,
        'model_weights_verified': False,
    }
    return {**receipt, 'receipt_hash': digest(receipt)}


def fixture_echo(contract, input_value):
    """Synthetic adapter only: copy input, validate output, never invent content.

    Incompatible input/output schemas fail closed instead of fabricating a
    successful result. This helper is not registered as a live executor.
    """
    output = deepcopy(input_value)
    receipt = verify_result(contract, input_value, output)
    return {'output': output, 'receipt': receipt, 'origin': 'fixture_echo', 'dry_run': True}
