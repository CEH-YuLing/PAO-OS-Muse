import unittest
from copy import deepcopy
from check_ux_restructure_readiness import verify_overlay
class Overlay(unittest.TestCase):
 def proof(self):
  binding={'sha256':'a'*64};front={'apps/web/a.tsx':'b'*64}
  return [{'pass':True,'binding':binding,'primary_unchanged':True,'env_unchanged':True,'installed_read_only':True,'api_mutations':0},
   {'pass':True,'binding':binding,'backend_changed':False,'database_changed':False,'env_changed':False,'node_tests':157,'frontend_files':front},binding,front]
 def test_exact_overlay(self):self.assertTrue(verify_overlay(*self.proof()))
 def test_source_mismatch(self):
  p=self.proof();p[-1]={};self.assertFalse(verify_overlay(*p))
 def test_backend_or_config_or_db_change_refused(self):
  for k in ('backend_changed','database_changed','env_changed'):
   p=deepcopy(self.proof());p[1][k]=True;self.assertFalse(verify_overlay(*p))
 def test_stale_binding(self):
  for i in (0,1):
   p=self.proof();p[i]['binding']={};self.assertFalse(verify_overlay(*p))
 def test_truthy_strings_refused(self):
  for i in (0,1):
   p=self.proof();p[i]['pass']='true';self.assertFalse(verify_overlay(*p))
 def test_partial_browser_not_acceptance(self):
  p=self.proof();p[0]['installed_read_only']=False;self.assertFalse(verify_overlay(*p))
if __name__=='__main__':unittest.main()
