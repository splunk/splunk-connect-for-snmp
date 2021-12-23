from unittest import TestCase

from splunk_connect_for_snmp.common.hummanbool import human_bool


class TestHumanBool(TestCase):
    def test_human_bool_true(self):
        self.assertEqual(human_bool("t"), True)
        self.assertEqual(human_bool("T"), True)
        self.assertEqual(human_bool("True"), True)
        self.assertEqual(human_bool("true"), True)
        self.assertEqual(human_bool("TrUe"), True)
        self.assertEqual(human_bool("y"), True)
        self.assertEqual(human_bool("yes"), True)
        self.assertEqual(human_bool("1"), True)
        self.assertEqual(human_bool(True), True)

    def test_human_bool_false(self):
        self.assertEqual(human_bool("f"), False)
        self.assertEqual(human_bool("F"), False)
        self.assertEqual(human_bool("False"), False)
        self.assertEqual(human_bool("fAlSe"), False)
        self.assertEqual(human_bool("n"), False)
        self.assertEqual(human_bool("no"), False)
        self.assertEqual(human_bool("0"), False)
        self.assertEqual(human_bool(False), False)

    def test_human_bool_none(self):
        self.assertEqual(human_bool(flag=None), False)

    def test_human_bool_default(self):
        self.assertEqual(human_bool("foo", True), True)
        self.assertEqual(human_bool("1foo", False), False)
        self.assertEqual(human_bool("1FoO"), False)
