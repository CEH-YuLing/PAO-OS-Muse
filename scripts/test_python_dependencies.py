import unittest
from check_python_dependencies import assess

class AuditTests(unittest.TestCase):
    def test_missing_or_skipped_report_is_rejected(self):
        for report in ({},{'dependencies':[]},{'dependencies':[{'name':'unscanned','skip_reason':'unknown'}]}):
            with self.assertRaises(ValueError):assess(report)
    def test_any_runtime_advisory_blocks(self):
        result=assess({'dependencies':[{'name':'lib','version':'1','vulns':[{'id':'example','fix_versions':['2']}]}]})
        self.assertFalse(result['runtime_clean']);self.assertEqual(len(result['affected_packages']),1)
    def test_complete_clean_scan_is_recorded_without_production_authority(self):
        result=assess({'dependencies':[{'name':'lib','version':'2','vulns':[]}]})
        self.assertTrue(result['runtime_clean']);self.assertNotIn('production_accepted',result)

if __name__=='__main__':unittest.main()
