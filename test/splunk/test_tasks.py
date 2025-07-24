from unittest import TestCase

from splunk_connect_for_snmp.splunk.tasks import value_as_best


class TestValueAsBest(TestCase):
    def test_float_string(self):
        self.assertEqual(value_as_best("123.45"), 123.45)

    def test_int_string(self):
        self.assertEqual(value_as_best("42"), 42.0)

    def test_serial_number_like_string(self):
        # Should not be interpreted as scientific notation, should return as string
        self.assertEqual(value_as_best("849867E9"), "849867E9")
        self.assertEqual(value_as_best("260E3100"), "260E3100")
        self.assertEqual(value_as_best("123E"), "123E")
        self.assertEqual(value_as_best("E123"), "E123")

    def test_non_numeric_string(self):
        self.assertEqual(value_as_best("not_a_number"), "not_a_number")

    def test_float(self):
        self.assertEqual(value_as_best(3.14), 3.14)

    def test_int(self):
        self.assertEqual(value_as_best(7), 7.0)

    def test_none(self):
        self.assertIsNone(value_as_best(None))

    def test_list(self):
        self.assertEqual(value_as_best([1,2,3]), [1,2,3])