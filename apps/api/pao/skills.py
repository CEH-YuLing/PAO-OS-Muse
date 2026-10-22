"""Closed, operator-reviewed skill contracts. No external code or tools are executed."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import ROOT


class PeriodInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start_date: date
    end_date: date

    @model_validator(mode='after')
    def period(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
            raise ValueError('invalid_period')
        return self


class AdsInput(PeriodInput):
    platform: Literal['meta', 'google_ads']
    account_id: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')


class SkillResult(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    status: Literal['completed', 'insufficient_data']
    summary: str = Field(min_length=1, max_length=4000)
    source_references: list[str] = Field(max_length=50)
    missing_data: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def evidence(self):
        if any(not value.strip() or len(value) > 500 for value in self.source_references + self.missing_data):
            raise ValueError('invalid_reference')
        if self.status == 'completed' and (not self.source_references or self.missing_data):
            raise ValueError('completed_requires_sources_and_no_missing_data')
        if self.status == 'insufficient_data' and not self.missing_data:
            raise ValueError('missing_data_reason_required')
        return self


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(pattern=r'^[a-z][a-z0-9-]+$')
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$')
    intent: str = Field(min_length=1, max_length=500)
    input_contract: Literal['period-v1', 'ads-period-v1']
    output_contract: Literal['source-result-v1']
    allowed_agents: list[Literal['chief_of_staff', 'performance_analyst', 'researcher', 'marketing', 'editor']] = Field(min_length=1)
    allowed_tools: list[str] = Field(min_length=1)
    permission: Literal['workspace_read']
    approval_class: Literal['read_only']
    timeout_seconds: int = Field(ge=1, le=600)
    token_budget: int = Field(ge=32, le=8192)
    execution_mode: Literal['deterministic_read_only'] = 'deterministic_read_only'
    evaluator: Literal['source-result-v1']


INPUTS = {'period-v1': PeriodInput, 'ads-period-v1': AdsInput}
BUSINESS_TOOLS = frozenset({'business.kpi.read', 'business.tasks.read', 'business.attribution.read',
                            'business.ads.intelligence.read', 'business.creative.read'})
SKILL_IDS = ('daily-business-brief', 'investigate-ads-drop', 'creative-fatigue-review')


def load_registry():
    registry = {}
    for key in SKILL_IDS:
        path = ROOT / 'packages' / 'skill-config' / f'{key}.json'
        spec = SkillManifest.model_validate(json.loads(path.read_text(encoding='utf-8')))
        if spec.id != key or not set(spec.allowed_tools).issubset(BUSINESS_TOOLS):
            raise ValueError('invalid_reviewed_skill_manifest')
        registry[key] = spec
    return registry


REGISTRY = load_registry()


class SkillVersionMismatch(ValueError):
    pass


def _execution_digest():
    # Compute once per process, not from a Git SHA or mutable model arguments.
    # Conservative scope: any backend Python source change requires a new binding.
    root = Path(__file__).parent
    digest = hashlib.sha256()
    digest.update(f'python:{sys.version_info[:3]}'.encode())
    for path in sorted(root.rglob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode() + b'\0')
        digest.update(path.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return digest.hexdigest()


EXECUTION_DIGEST = _execution_digest()


def execution_binding():
    return {'policy': 'exact-backend-source-v1', 'sha256': EXECUTION_DIGEST}


def require_execution_binding(binding):
    if binding != execution_binding():
        raise SkillVersionMismatch('skill_version_incompatible')


def require_snapshot_integrity(skill_snapshot):
    if not isinstance(skill_snapshot, dict):
        raise SkillVersionMismatch('skill_version_incompatible')
    payload = {key: value for key, value in skill_snapshot.items() if key != 'hash'}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != skill_snapshot.get('hash'):
        raise ValueError('skill_snapshot_hash_mismatch')


def require_snapshot_execution(skill_snapshot):
    require_snapshot_integrity(skill_snapshot)
    require_execution_binding(skill_snapshot.get('execution_binding'))


def snapshot(skill_id):
    spec = REGISTRY[skill_id]
    payload = spec.model_dump(mode='json')
    payload['input_schema'] = INPUTS[spec.input_contract].model_json_schema()
    payload['output_schema'] = SkillResult.model_json_schema()
    payload['execution_binding'] = execution_binding()
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return {**payload, 'hash': hashlib.sha256(canonical.encode()).hexdigest()}


def validate_input(skill_id, agent, arguments, requested_tools=()):
    spec = REGISTRY[skill_id]
    if agent not in spec.allowed_agents:
        raise PermissionError('skill_agent_denied')
    if not set(requested_tools).issubset(spec.allowed_tools):
        raise PermissionError('skill_tool_denied')
    # Permission is enforced by the API's workspace membership check. Manifests
    # cannot grant access to another workspace or bypass domain-level guards.
    return INPUTS[spec.input_contract].model_validate(arguments).model_dump(mode='json')


def evaluate_result(skill_snapshot, result):
    require_snapshot_execution(skill_snapshot)
    if skill_snapshot.get('evaluator') != 'source-result-v1':
        raise ValueError('unsupported_pinned_evaluator')
    return SkillResult.model_validate(result).model_dump(mode='json')
