from unittest import TestCase

from splunk_connect_for_snmp.common.hummanbool import human_bool


class TestHumanBool(TestCase):
    def test_human_bool_true(self):
        self.assertTrue(human_bool("t"))
        self.assertTrue(human_bool("T"))
        self.assertTrue(human_bool("True"))
        self.assertTrue(human_bool("true"))
        self.assertTrue(human_bool("TrUe"))
        self.assertTrue(human_bool("y"))
        self.assertTrue(human_bool("yes"))
        self.assertTrue(human_bool("1"))
        self.assertTrue(human_bool(True))

    def test_human_bool_false(self):
        self.assertFalse(human_bool("f"))
        self.assertFalse(human_bool("F"))
        self.assertFalse(human_bool("False"))
        self.assertFalse(human_bool("fAlSe"))
        self.assertFalse(human_bool("n"))
        self.assertFalse(human_bool("no"))
        self.assertFalse(human_bool("0"))
        self.assertFalse(human_bool(False))

    def test_human_bool_none(self):
        self.assertFalse(human_bool(flag=None))

    def test_human_bool_default(self):
        self.assertTrue(human_bool("foo", True))
        self.assertFalse(human_bool("1foo", False))
        self.assertFalse(human_bool("1FoO"))
