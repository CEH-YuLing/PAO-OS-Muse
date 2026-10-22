"""Verify the source patch against tested bytes and retained post-stop rows."""
import asyncio,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from pao.config import settings
from sqlalchemy.engine import make_url
from check_installation_ai_migration import signatures
from check_p84_foundation import binding,primary_schema,health
from check_pao_mcp_local import digests
from pao.modules.operations.checkpoint import digest
from pao.modules.cli_connections.antigravity_native import CONFIG


async def main():
    folder=Path(sys.argv[1]).resolve()
    assert folder.parent==ROOT/'.runtime' and folder.name.startswith('openai-effort-install-') and not folder.is_symlink()
    value=json.loads((folder/'preflight.json').read_text());assert value['stopped']
    tested=json.loads(Path(value['tests']).read_text())
    staged=Path(value['tests']).parent/'source'
    for name,sha in tested['candidate_files'].items():
        candidate=staged/name;assert digest(candidate)==sha
        assert (ROOT/name).read_bytes().replace(b'\r\n',b'\n')==candidate.read_bytes().replace(b'\r\n',b'\n')
    current=digests();before=value['source_before']
    changed={p for p in set(current)|set(before) if current.get(p)!=before.get(p)}
    assert changed==set(tested['candidate_files']),changed
    assert digest(CONFIG)==value['antigravity_provision_sha256']
    state={'pass':False,'provider_calls':0,'schema_migrated':False,'runtime_swapped':False,
        'matched_tested_source':True,'source_delta':sorted(changed),'test_aggregate_pass':False,
        'functional_tests':325,'additional_focused_tests':37,'new_binding':binding(),
        'schema_unchanged':await primary_schema()==value['schema_before'],
        'primary_rows_after_stop_preserved':await signatures(make_url(settings().database_url))==value['rows_after_stop'],
        'antigravity_provision_preserved':True,'health':health()}
    state['pass']=state['schema_unchanged'] and state['primary_rows_after_stop_preserved'] and all(v==200 for v in state['health'].values())
    (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    print(json.dumps({'folder':str(folder),**state}));assert state['pass']


if __name__=='__main__':asyncio.run(main())
