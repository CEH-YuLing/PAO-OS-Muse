"""Versioned, bounded historical result replay. Never invoke tools or models.

Keep the v1 reader available when adding later formats. This is a data archive,
not an executable archive or authorization to resume an interrupted job.
"""
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .skills import require_snapshot_integrity

MAX_ARCHIVE_BYTES = 256000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


class ArchivedResultV1(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['completed', 'insufficient_data']
    summary: str = Field(min_length=1, max_length=4000)
    source_references: list[str] = Field(max_length=50)
    missing_data: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def evidence(self):
        if not self.summary.strip() or any(not s.strip() or len(s) > 500
                for s in self.source_references + self.missing_data):
            raise ValueError('invalid_archived_evidence')
        if self.status == 'completed' and (not self.source_references or self.missing_data):
            raise ValueError('invalid_archived_completion')
        if self.status == 'insufficient_data' and not self.missing_data:
            raise ValueError('invalid_archived_missing_data')
        return self


class SkillReplay(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    format: Literal['pao-skill-result-v1']
    kind: Literal['run', 'attempt']
    record_id: str
    workspace_id: str
    skill_snapshot: dict
    input: dict
    resource_guard: dict
    tools: list[dict] = Field(max_length=2)
    result: ArchivedResultV1
    response: str = Field(max_length=32000)
    evidence: list = Field(max_length=100)
    hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    read_only: Literal[True] = True
    tools_reexecuted: Literal[False] = False
    business_verified: Literal[False] = False


def read_artifact(artifact, kind, record_id, workspace_id):
    if not isinstance(artifact, dict) or len(canonical(artifact)) > MAX_ARCHIVE_BYTES:
        raise ValueError('invalid_skill_archive')
    payload = {key: value for key, value in artifact.items() if key != 'hash'}
    if hashlib.sha256(canonical(payload)).hexdigest() != artifact.get('hash'):
        raise ValueError('skill_archive_hash_mismatch')
    value = SkillReplay.model_validate(artifact)
    if (value.kind, value.record_id, value.workspace_id) != (kind, record_id, workspace_id):
        raise ValueError('skill_archive_scope_mismatch')
    pinned = value.skill_snapshot
    require_snapshot_integrity(pinned)  # Intentionally no current-code binding check.
    if pinned.get('evaluator') != 'source-result-v1':
        raise ValueError('unsupported_archive_evaluator')
    if value.kind == 'run':
        guard = value.resource_guard
        if (guard.get('execution_mode') != 'deterministic_read_only' or
                type(guard.get('llm_generated_tokens')) is not int or
                guard['llm_generated_tokens'] != 0 or guard.get('max_tools') != 2):
            raise ValueError('invalid_archive_resource_guard')
        if (type(guard.get('token_budget')) is not int or
                guard['token_budget'] != pinned.get('token_budget') or
                not 32 <= guard['token_budget'] <= 8192):
            raise ValueError('invalid_archive_token_budget')
        names = [tool.get('tool') for tool in value.tools]
        if len(names) != 2 or len(set(names)) != 2 or not set(names).issubset(pinned['allowed_tools']):
            raise ValueError('invalid_archive_tools')
        sources = {ref for tool in value.tools for ref in tool['source_references']}
        if not set(value.result.source_references).issubset(sources):
            raise ValueError('archive_sources_not_read')
        # v1 command workflows deliberately cannot claim verified business completion.
        if value.result.status != 'insufficient_data':
            raise ValueError('unsupported_business_claim')
    return value


def build_artifact(kind, record_id, workspace_id, pinned, arguments, result,
                   response='', tools=(), guard=None, evidence=()):
    payload = {'format': 'pao-skill-result-v1', 'kind': kind,
               'record_id': record_id, 'workspace_id': workspace_id,
               'skill_snapshot': pinned, 'input': arguments,
               'resource_guard': guard or {}, 'tools': list(tools),
               'result': ArchivedResultV1.model_validate(result).model_dump(),
               'response': response, 'evidence': list(evidence),
               'read_only': True, 'tools_reexecuted': False, 'business_verified': False}
    payload['hash'] = hashlib.sha256(canonical(payload)).hexdigest()
    return read_artifact(payload, kind, record_id, workspace_id).model_dump(mode='json')
