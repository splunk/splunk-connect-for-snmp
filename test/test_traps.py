from unittest import TestCase

from splunk_connect_for_snmp.traps import decode_security_context


class TestDecodeSecurityContext(TestCase):
    def test_valid_snmpv3_message(self):
        hexstr = b'0\x81\xb2\x02\x01\x030\x11\x02\x04UL\x84\xc0\x02\x03\x00\xff\xe3\x04\x01\x03\x02\x01\x03\x04806\x04\t\x80\x00\x00\xc1\x01\n\x01\x0f\xc4\x02\x01\x00\x02\x01\x00\x04\x0bsnmp-poller\x04\x0c\x106X\x9cE0\xb8o/\xa5"*\x04\x08#\x1e\x83\xf0m\xbbf6\x04`\xc7E\x9f\xe5\x14\x92\xd85\xdf\xf7\xb4Z\xf5\xfc*\x960B\xcd\x07\xef\xb8A\x14G\xeb\x13\x00\xcb\x07\xc0F\x13-\x9f\x12\xc0\xfe\xd4\x7f{\xec\xc5\xc4\xfd\xf0\xcd\x92V\xa6\xfd\xac\x16L\xd1\xbc{P\xd7\x8f\xfek\x0e\xb6\xe0\xb3X\xca&\xd4\xfd\xa37\t\x8e\x14\xcc\xd7C\x10\xb9\xd9!\'#6aZ\x87N\xfe*$i\x1bl'
        result = decode_security_context(hexstr)
        self.assertIsInstance(result, str)
        self.assertEqual(result, "800000c1010a010fc4")

    def test_invalid_version(self):
        # SNMPv2 message (version 1)
        hexstr = bytes.fromhex("3081a702010102104080003a8c04")
        result = decode_security_context(hexstr)
        self.assertIsNone(result)

    def test_asn1_error(self):
        # Invalid ASN.1 bytes
        hexstr = b"\x00\x01\x02"
        result = decode_security_context(hexstr)
        self.assertIsNone(result)

    def test_exception(self):
        # Pass None to trigger exception
        result = decode_security_context(None)
        self.assertIsNone(result)