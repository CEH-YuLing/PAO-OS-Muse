"""Existing six command guards plus exact new-candidate/mismatched-root checks."""
import importlib.util
from pathlib import Path,PureWindowsPath
import sys
import unittest
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'.runtime/codex-login-candidate-20261019'
sys.path[:0]=[str(ROOT/'packages/cli-runtime'),str(ROOT/'scripts')]
spec=importlib.util.spec_from_file_location('windows_candidate_restore',CANDIDATE/'scripts/windows_candidate_restore.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
from test_windows_candidate_restore import CandidateRestoreTests

class BrowserLoginRestoreTests(unittest.TestCase):
    def setUp(self):
        self.url=make_url('postgresql+asyncpg://pao:synthetic@127.0.0.1:15432/pao_test')
        self.env={'PAO_WINDOWS_CANDIDATE_RESTORE':'1','PAO_ROOT':str(CANDIDATE),'PAO_WINDOWS_CANDIDATE_PG_CONTAINER':'a'*64}
    def test_new_exact_candidate_only(self):
        self.assertEqual(module.PgTools(CANDIDATE,self.url,self.env,True,None,'win32').container,'a'*64)
        for root in (ROOT,ROOT/'.runtime/other',CANDIDATE/'child'):
            with self.subTest(root=root),self.assertRaises(ValueError):module.PgTools(root,self.url,{**self.env,'PAO_ROOT':str(root)},True,None,'win32')
    def test_candidate_roots_cannot_borrow_other_environment(self):
        with self.assertRaises(ValueError):module.PgTools(CANDIDATE,self.url,{**self.env,'PAO_ROOT':str(module.EXPECTED)},True,None,'win32')
    def test_primary_database_remains_denied_on_new_candidate(self):
        with self.assertRaises(ValueError):module.PgTools(CANDIDATE,self.url.set(database='pao_acos_local'),self.env,True,None,'win32')

if __name__=='__main__':unittest.main(verbosity=2)
