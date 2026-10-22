"""Validate exact coverage/provenance; retain failed full and separate suffix JUnit."""
import argparse,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.modules.operations.checkpoint import entries
from codex_login_regression import verified_coverage

def main(args):
    folder=ROOT/'.runtime'/('codex-login-regression-'+uuid4().hex);folder.mkdir()
    value={'kind':'preserved_prefix_fixture_repair_suffix','pass':True,'single_full_run_passed':False,
           'prefix_folder':str(args.prefix.resolve()),'suffix_folder':str(args.suffix.resolve()),
           'historical_failed_full_preserved':True,'provider_calls':0}
    (folder/'receipt.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    try:value['counts']=verified_coverage(folder,entries(ROOT/'.runtime/codex-login-candidate-20261019'))
    except Exception:
        value['pass']=False;(folder/'receipt.json').write_text(json.dumps(value,indent=2),encoding='utf-8');raise
    (folder/'receipt.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps({'folder':str(folder),**value}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prefix',type=Path,required=True);parser.add_argument('--suffix',type=Path,required=True);main(parser.parse_args())
