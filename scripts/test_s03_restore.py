"""Pure tests for the deliberately narrow dump/reparse normalization."""
import unittest
from check_s03_restore import canonical_sql, definition_row, SUPPORTED_REVISIONS


class CanonicalSQLTests(unittest.TestCase):
    def test_verified_embedding_revision_is_explicitly_supported(self):
        self.assertIn('0057',SUPPORTED_REVISIONS)
        self.assertIn('0058',SUPPORTED_REVISIONS)
        self.assertIn('0056',SUPPORTED_REVISIONS)
        self.assertIn('0063',SUPPORTED_REVISIONS)
        self.assertIn('0064',SUPPORTED_REVISIONS)
        self.assertIn('0065',SUPPORTED_REVISIONS)
        self.assertIn('0070',SUPPORTED_REVISIONS)
        self.assertIn('0075',SUPPORTED_REVISIONS)
        self.assertNotIn('0076',SUPPORTED_REVISIONS)
        self.assertNotIn('9999',SUPPORTED_REVISIONS)

    def test_check_array_cast_equivalent(self):
        original = "CHECK (severity::text = ANY (ARRAY['info'::character varying, 'critical'::character varying]::text[]))"
        restored = "CHECK (severity::text = ANY (ARRAY['info'::character varying::text, 'critical'::character varying::text]))"
        self.assertEqual(canonical_sql(original), canonical_sql(restored))

    def test_index_parentheses_equivalent(self):
        original = "WHERE ((status)::text = ANY ((ARRAY['queued'::character varying, 'running'::character varying])::text[]))"
        restored = "WHERE ((status)::text = ANY (ARRAY[('queued'::character varying)::text, ('running'::character varying)::text]))"
        self.assertEqual(canonical_sql(original), canonical_sql(restored))

    def test_changed_values_not_equal(self):
        left = "ANY (ARRAY['queued'::character varying]::text[])"
        right = "ANY (ARRAY['failed'::character varying::text])"
        self.assertNotEqual(canonical_sql(left), canonical_sql(right))

    def test_all_cast_and_operator_preserved(self):
        original = "status::text <> ALL ((ARRAY['completed'::character varying])::text[])"
        restored = "status::text <> ALL (ARRAY[('completed'::character varying)::text])"
        self.assertEqual(canonical_sql(original), canonical_sql(restored))
        self.assertNotEqual(canonical_sql(original), canonical_sql(restored.replace('ALL', 'ANY')))

    def test_order_and_escaped_literal_preserved(self):
        original = "ANY (ARRAY['a,''b'::character varying, 'c'::character varying]::text[])"
        restored = "ANY (ARRAY['a,''b'::character varying::text, 'c'::character varying::text])"
        self.assertEqual(canonical_sql(original), canonical_sql(restored))
        self.assertNotEqual(canonical_sql(original), canonical_sql(
            "ANY (ARRAY['c'::character varying::text, 'a,''b'::character varying::text])"))

    def test_other_sql_unchanged(self):
        for value in ("ANY (ARRAY['a'::character varying(2)]::text[])",
                      "ANY (ARRAY[secret_function()::character varying]::text[])",
                      "ANY (ARRAY['a'::character varying])", "(a OR b) AND c", None):
            self.assertEqual(canonical_sql(value), value)

    def test_functions_and_defaults_never_normalized(self):
        row = ('object', 'field', "ANY (ARRAY['queued'::character varying]::text[])")
        for kind in ('functions', 'attributes', 'triggers'):
            self.assertEqual(definition_row(kind, row), row)
        self.assertNotEqual(definition_row('constraints', row), row)


if __name__ == '__main__':
    unittest.main()
