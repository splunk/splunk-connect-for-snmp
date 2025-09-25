import asyncio
from queue import Empty
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError
from splunk_connect_for_snmp.snmp.manager import Poller
from splunk_connect_for_snmp.snmp.varbinds_resolver import ProfileCollection

inventory_record = InventoryRecord(
    **{
        "address": "192.168.0.1",
        "port": "34",
        "version": "2c",
        "community": "public",
        "secret": "secret",
        "securityEngine": "ENGINE",
        "walk_interval": 1850,
        "profiles": "",
        "SmartProfiles": True,
        "delete": False,
    }
)


class TestDoWork(IsolatedAsyncioTestCase):
    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    async def test_do_work_no_work_to_do(self, setup_transport, get_auth):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.profiles_manager = MagicMock()
        poller.profiles_collection = MagicMock()
        poller.refresh_snmp_engine = MagicMock()
        poller.profiles_collection.process_profiles = MagicMock()
        poller.already_loaded_mibs = set()
        varbinds_bulk, varbinds_get = set(), set()
        get_mapping, bulk_mapping = {}, {}

        poller.get_varbinds = MagicMock(
            return_value=(varbinds_get, get_mapping, varbinds_bulk, bulk_mapping)
        )
        result = await poller.do_work(inventory_record)
        self.assertEqual(result, (False, {}))

    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.bulk_walk_cmd")
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.common.collection_manager.ProfilesManager")
    async def test_do_work_bulk_varbinds(
        self, load_profiles, get_cmd, bulk_walk_cmd, setup_transport_target, get_auth
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.profiles_manager = MagicMock()
        poller.refresh_snmp_engine = MagicMock()
        poller.process_snmp_data = MagicMock(return_value=(False, [], {}))

        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()

        def bulk_walk_cmd_mock(*args, **kwargs):
            async def _gen():
                yield (None, 0, 0, ["Oid1"])
                yield (None, 0, 0, ["Oid2"])
                yield (None, 0, 0, ["Oid3"])

            return _gen()

        bulk_walk_cmd.side_effect = bulk_walk_cmd_mock
        get_auth.return_value = MagicMock()
        setup_transport_target.return_value = MagicMock()

        # Call the async do_work
        await poller.do_work(inventory_record, profiles=requested_profiles)

        # Assertions
        self.assertEqual(poller.process_snmp_data.call_count, 9)
        get_cmd.assert_not_called()
        self.assertEqual(bulk_walk_cmd.call_count, 3)

    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.bulk_walk_cmd", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd")
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    async def test_do_work_get(
        self, load_profiles, get_cmd, bulk_walk_cmd, setup_transport_target, get_auth
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.refresh_snmp_engine = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr", 1], ["IF-MIB", "ifSpeed", 2]],
            },
            "profile2": {
                "frequency": 20,
                "varBinds": [["UDP-MIB", "udpOutDatagrams", 1]],
            },
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        get_cmd.side_effect = [
            (None, 0, 0, ["Oid1"]),
            (None, 0, 0, ["Oid2"]),
            (None, 0, 0, ["Oid3"]),
        ]
        await poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 1)
        self.assertEqual(get_cmd.call_count, 1)
        self.assertEqual(bulk_walk_cmd.call_count, 0)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.bulk_walk_cmd", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    async def test_do_work_errors(
        self,
        load_profiles,
        get_cmd_mock,
        bulk_walk_cmd_mock,
        setup_transport_target,
        get_auth,
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.refresh_snmp_engine = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1"]
        poller.profiles = {
            "profile1": {"frequency": 20, "varBinds": [["IF-MIB", "ifDescr", 1]]}
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()

        async def get_cmd_failure(*args, **kwargs):
            return (True, True, 2, [])

        get_cmd_mock.side_effect = get_cmd_failure
        with self.assertRaises(SnmpActionError):
            await poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 0)
        self.assertEqual(get_cmd_mock.call_count, 1)
        self.assertEqual(bulk_walk_cmd_mock.call_count, 0)
