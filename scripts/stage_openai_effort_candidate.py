"""Source-only staging for OpenAI effort. No CLI overlay/migration/auth copy."""
from pathlib import Path
import shutil
from stage_installation_cli_candidate import replace

ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'packages/client-adapters/openai-effort'


def stage(folder):
    folder=folder.resolve()
    if not folder.is_relative_to(ROOT/'.runtime') or folder.exists():
        raise RuntimeError('new_scoped_candidate_directory_required')
    folder.mkdir(parents=True)
    for name in ('pao','migrations','tests'):
        shutil.copytree(ROOT/'apps/api'/name,folder/'apps/api'/name,
            ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc'))
    for name in ('skill-config','agent-config','cli-runtime/pao_cli_runtime'):
        shutil.copytree(ROOT/'packages'/name,folder/'packages'/name,
            ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('alembic.ini','pyproject.toml'):
        shutil.copyfile(ROOT/name,folder/name)
    target=folder/'apps/api/pao/modules/installation_ai/openai_effort.py'
    if target.is_file():
        # After promotion, test the current native source as-is. Do not reapply
        # the historical patch or overwrite a newer reviewed capability table.
        return folder
    shutil.copyfile(CANDIDATE/'openai_effort.py',target)
    gateway=folder/'apps/api/pao/gateway.py'
    replace(gateway,
        "    def _reasoning(self,payload):\n        if self.reasoning_effort is not None:",
        "    def _reasoning(self,payload):\n        if self.provider_name=='openai':\n"
        "            from .modules.installation_ai.openai_effort import payload as prepare\n"
        "            try:return prepare(self.model_name,self.reasoning_effort,payload)\n"
        "            except ValueError as exc:raise CloudProviderError(str(exc)) from None\n"
        "        if self.reasoning_effort is not None:")
    replace(gateway,
        "    if reasoning_effort is not None and provider!='openrouter':",
        "    if reasoning_effort is not None and provider not in ('openai','openrouter'):")
    replace(gateway,
        "    if provider == 'openai': return OpenAICompatibleGateway(provider,api_key,model,'https://api.openai.com/v1')",
        "    if provider == 'openai':\n        from .modules.installation_ai.openai_effort import validate\n"
        "        try:validate(model,reasoning_effort)\n        except ValueError as exc:raise CloudProviderError(str(exc)) from None\n"
        "        return OpenAICompatibleGateway(provider,api_key,model,'https://api.openai.com/v1',reasoning_effort)")
    replace(folder/'apps/api/pao/model_router.py',
        "                        item={'model':value}\n                        # IDs remain dynamic.",
        "                        item={'model':value}\n                        if provider=='openai':\n"
        "                            from .modules.installation_ai.openai_effort import metadata\n"
        "                            item.update(metadata(value))\n                        # IDs remain dynamic.")
    replace(folder/'apps/api/pao/modules/installation_ai/service.py',
        "        chosen = selection(row.catalog, model or row.default_model, effort)",
        "        chosen = selection(row.catalog, model or row.default_model, effort)\n"
        "        if row.provider == 'openai':\n            from .openai_effort import validate\n"
        "            validate(chosen['model'], chosen['reasoning_effort'])")
    return folder
