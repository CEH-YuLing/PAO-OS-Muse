"""Secret-free S5 routing policy. A preview is never inference authority."""
from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from .contracts import Closed


class Target(Closed):
    key: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    provider: Literal['ollama', 'openai', 'anthropic', 'gemini', 'openrouter', 'codex_cli','muse']
    model: str = Field(min_length=1, max_length=120, pattern=r'^[^\s\x00-\x1f\x7f]+$')
    reference_id: UUID | None = None
    installation_resource_id: UUID | None = None
    reasoning_effort: str | None = Field(default=None,pattern=r'^[a-z][a-z0-9_-]{0,23}$')

    @model_validator(mode='after')
    def reference(self):
        if self.installation_resource_id:
            if self.provider=='ollama' or self.reference_id is not None:
                raise ValueError('An installation resource cannot also be a tenant reference or local model')
        elif (self.provider == 'ollama') != (self.reference_id is None) or self.reasoning_effort is not None:
            raise ValueError('Cloud requires an SME model reference; local has no reference')
        return self


class Limits(Closed):
    token_budget: int = Field(default=4096, ge=128, le=65536, strict=True)
    output_tokens: int = Field(default=256, ge=16, le=512, strict=True)
    timeout_seconds: int = Field(default=45, ge=1, le=120, strict=True)


class Override(Closed):
    target: str | None = Field(default=None, pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    allowed_targets: list[str] | None = Field(default=None, min_length=1, max_length=20)
    cloud_allowed: bool | None = Field(default=None, strict=True)
    token_budget: int | None = Field(default=None, ge=128, le=65536, strict=True)
    output_tokens: int | None = Field(default=None, ge=16, le=512, strict=True)
    timeout_seconds: int | None = Field(default=None, ge=1, le=120, strict=True)

    @model_validator(mode='before')
    @classmethod
    def no_explicit_null(cls, value):
        if isinstance(value, dict) and any(v is None for v in value.values()):
            raise ValueError('Omit an inherited field instead of null')
        return value


class Layer(Closed):
    kind: Literal['brand', 'agent', 'step']
    scope_id: UUID
    step_id: str | None = Field(default=None, pattern=r'^[a-z][a-z0-9-]{1,39}$')
    settings: Override

    @model_validator(mode='after')
    def step(self):
        if (self.kind == 'step') != (self.step_id is not None):
            raise ValueError('Only a workflow step has a step ID')
        return self


class Specialist(Closed):
    kind: Literal['content', 'creative', 'ads', 'analyst']
    skill_version_id: UUID


class RoutingContent(Closed):
    targets: list[Target] = Field(min_length=1, max_length=20)
    default_target: str
    limits: Limits = Field(default_factory=Limits)
    cloud_allowed: bool = Field(default=False, strict=True)
    specialists: list[Specialist] = Field(default_factory=list, max_length=4)
    layers: list[Layer] = Field(default_factory=list, max_length=80)

    @model_validator(mode='after')
    def unique(self):
        keys = [t.key for t in self.targets]
        identities = [(t.provider, t.model, t.reference_id,t.installation_resource_id,t.reasoning_effort) for t in self.targets]
        scopes = [(t.kind, t.scope_id, t.step_id) for t in self.layers]
        kinds = [s.kind for s in self.specialists]
        if (len(set(keys)) != len(keys) or len(set(identities)) != len(identities)
                or self.default_target not in keys or len(set(scopes)) != len(scopes)
                or len(set(kinds)) != len(kinds)):
            raise ValueError('Duplicate routing identity or missing default')
        if not self.cloud_allowed and next(t for t in self.targets if t.key == self.default_target).provider != 'ollama':
            raise ValueError('Cloud is not permitted by the SME policy')
        # Check each layer against the SME ceiling here; the exact inherited
        # combination is checked again when resolving a concrete job.
        for layer in self.layers:
            merge(initial(self), layer.settings)
        return self


class RoutingSave(Closed):
    request_key: UUID
    expected_revision: int = Field(ge=0, strict=True)
    content: RoutingContent


class RoutingPreview(Closed):
    routing_revision: int = Field(ge=1, strict=True)
    plan_revision: int = Field(ge=1, strict=True)
    item_key: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    workflow_version_id: UUID | None = None
    step_id: str | None = Field(default=None, pattern=r'^[a-z][a-z0-9-]{1,39}$')
    job: Override = Field(default_factory=Override)
    grant_id: UUID | None = None

    @model_validator(mode='after')
    def step(self):
        if (self.workflow_version_id is None) != (self.step_id is None):
            raise ValueError('Workflow and step must be selected together')
        return self


def initial(content):
    return {'target': content.default_target, 'allowed_targets': [t.key for t in content.targets],
            'cloud_allowed': content.cloud_allowed, **content.limits.model_dump()}


def merge(parent, override):
    """A child may select inside inherited authority, never expand its ceilings."""
    changes = override.model_dump(exclude_unset=True, exclude_none=True)
    value = {**parent, **changes}
    allowed = value['allowed_targets']
    if len(set(allowed)) != len(allowed) or not set(allowed) <= set(parent['allowed_targets']):
        raise ValueError('Routing allowlist escalation')
    if value['target'] not in allowed:
        raise ValueError('Selected target is outside inherited allowlist')
    if value['cloud_allowed'] and not parent['cloud_allowed']:
        raise ValueError('Cloud privacy escalation')
    for field in ('token_budget', 'output_tokens', 'timeout_seconds'):
        if value[field] > parent[field]:
            raise ValueError('Routing resource escalation')
    return value


def resolve(content, *, brand_id=None, agent_id=None, workflow_id=None, step_id=None, job=None):
    value = initial(content)
    trace = [{'scope': 'enterprise', 'settings': value.copy()}]
    for kind, scope, step in (('brand', brand_id, None), ('agent', agent_id, None), ('step', workflow_id, step_id)):
        for layer in content.layers:
            if layer.kind == kind and str(layer.scope_id) == str(scope) and layer.step_id == step:
                value = merge(value, layer.settings)
                trace.append({'scope': kind, 'id': str(scope), 'step_id': step, 'settings': value.copy()})
    value = merge(value, job or Override())
    trace.append({'scope': 'job', 'settings': value.copy()})
    target = next(t for t in content.targets if t.key == value['target'])
    if target.provider != 'ollama' and not value['cloud_allowed']:
        raise ValueError('Cloud privacy denied')
    return value, target, trace
