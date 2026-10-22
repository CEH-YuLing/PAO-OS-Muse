"""Evidence helpers: never call a repaired-prefix coverage set a green full run."""
import json
from pathlib import Path
from xml.etree import ElementTree

ROOT=Path('F:/PAO-ACOS')
SCOPED_FIX='scripts/windows_candidate_restore.py'
def backend(values):return {k:v for k,v in values.items() if k.startswith(('apps/api/','packages/cli-runtime/','packages/contracts/','scripts/')) or k in ('requirements.lock','pyproject.toml','alembic.ini')}

def cases(folder):return list(ElementTree.parse(folder/'junit.xml').getroot().iter('testcase'))
def node_id(case,nodes):
    module=case.attrib['classname'];files={x.partition('::')[0] for x in nodes}
    modules={p[:-3].replace('/','.'):p for p in files}
    options=[m for m in modules if module==m or module.startswith(m+'.')]
    assert options,'Unknown JUnit module'
    selected=max(options,key=len)
    nested=module[len(selected):].strip('.').replace('.','::')
    return modules[selected]+'::'+(nested+'::' if nested else '')+case.attrib['name']

def prefix_manifest(folder,nodes,current):
    proof=json.loads((folder/'receipt.json').read_text())
    assert proof['pass'] is False and proof['full_backend_regression'] is True and proof['primary_source_env_unchanged'] and proof['candidate_unchanged_during_tests']
    before=backend(proof['candidate_source']);after=backend(current)
    assert {k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}=={SCOPED_FIX}
    entries=cases(folder);assert len(entries)==1417
    failures=[c for c in entries if c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None]
    assert len(failures)==1 and entries[-1] is failures[0]
    assert failures[0].attrib['name']=='test_populated_p7_restore_fresh_process_identity_and_no_resend'
    assert 'exact_windows_candidate_test_restore_required' in ''.join(failures[0].itertext())
    assert [node_id(c,nodes) for c in entries]==nodes[:len(entries)]
    return {'all_nodes':nodes,'passed_prefix_count':len(entries)-1,'selected_nodes':nodes[len(entries)-1:],
            'prior_folder':str(folder),'only_input_change':SCOPED_FIX}

def verified_coverage(folder,current):
    proof=json.loads((folder/'receipt.json').read_text())
    assert proof.get('kind')=='preserved_prefix_fixture_repair_suffix' and proof.get('pass') is True and proof.get('single_full_run_passed') is False
    first=Path(proof['prefix_folder']);second=Path(proof['suffix_folder'])
    for p in (first,second):assert p.parent==ROOT/'.runtime' and p.name.startswith('codex-login-tests-') and not p.is_symlink()
    manifest=json.loads((second/'resume-manifest.json').read_text())
    expected=prefix_manifest(first,manifest['all_nodes'],current)
    assert manifest==expected
    tail=json.loads((second/'receipt.json').read_text())
    assert tail['pass'] and tail['candidate_unchanged_during_tests'] and tail['primary_source_env_unchanged'] and not tail['full_backend_regression']
    assert backend(tail['candidate_source'])==backend(current)
    suffix=cases(second)
    assert [node_id(c,manifest['all_nodes']) for c in suffix]==manifest['selected_nodes']
    assert all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in suffix)
    total=manifest['passed_prefix_count']+len(suffix)
    assert total==len(manifest['all_nodes'])==2356 and len(set(manifest['all_nodes']))==total
    return {'tests':total,'failures':0,'errors':0,'skipped':0}
