import asyncio
import copy
import fnmatch
import ipaddress
import os
import re

from celery import Task
from celery.utils.log import get_task_logger
from filelock import FileLock
from pysnmp.hlapi.asyncio import (
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    get_cmd,
)

from splunk_connect_for_snmp.common.csv_record_manager import CSVRecordManager
from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.discovery.exceptions import DiscoveryError
from splunk_connect_for_snmp.snmp.auth import get_discovery_auth, setup_transport_target

logger = get_task_logger(__name__)

DISCOVERY_FOLDER_PATH = os.getenv("DISCOVERY_FOLDER_PATH", "/app/discovery")
DISCOVERY_CSV_PATH = os.path.join(DISCOVERY_FOLDER_PATH, "discovery_devices.csv")
DISCOVERY_LOCK_PATH = os.path.join(DISCOVERY_FOLDER_PATH, "discovery_devices.lock")
DISCOVERY_SUBNET_CHECK_CONCURRENCY = int(
    os.getenv("DISCOVERY_SUBNET_CHECK_CONCURRENCY", 10)
)
DEFAULT_GROUP_NAME = "default_group"


class Discovery(Task):
    @staticmethod
    def close_snmp_engine(snmp_engine: SnmpEngine):
        """Release transport resources held by a discovery SNMP engine."""
        try:
            snmp_engine.close_dispatcher()
        except Exception as e:
            logger.debug(f"Error while closing discovery SNMP engine: {e}")

    def get_host_list(self, subnet):
        """Get host list"""
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            return [str(ip) for ip in network.hosts()]
        except Exception as e:
            err_msg = (
                f"Error occurred while finding active hosts for subnet {subnet}: {e}"
            )
            raise DiscoveryError(err_msg)

    def find_device_group(self, varbinds, device_rules) -> str:
        """
        Find the device group based on varbind's value matching rules.

        :param varbinds: SNMP varbinds.
        :param device_rules: List of rules with patterns and groups

        :returns: Group name (defaults to DEFAULT_GROUP_NAME if no match)
        """
        device_rules_errors = []  # type: ignore
        if not isinstance(device_rules, list):
            return DEFAULT_GROUP_NAME

        value = varbinds[0][1].prettyPrint()

        for device_rule in device_rules:
            try:
                pattern = device_rule.get("patterns")
                if not pattern:
                    continue

                regex_pattern = fnmatch.translate(pattern)
                if re.search(regex_pattern, value, re.IGNORECASE):
                    group_name = device_rule.get("group", DEFAULT_GROUP_NAME)
                    if device_rules_errors:
                        logger.warning(
                            f"Invalid device rules found for: {device_rules_errors} and continue with {group_name}"
                        )
                    return group_name
            except Exception as e:
                device_rules_errors.append(
                    {"device_rule": device_rule, "error": str(e)}
                )
                continue

        if device_rules_errors:
            logger.warning(
                f"Invalid device rules found: {device_rules_errors} and continue with {DEFAULT_GROUP_NAME}"
            )

        return DEFAULT_GROUP_NAME

    async def check_snmp_device(
        self,
        ip: str,
        discovery_record: DiscoveryRecord,
        snmp_engine: SnmpEngine,
    ) -> dict | None:
        """
        Check if an SNMP device responds at the given IP.
        :param ip: IP address of target device.
        :param discovery_record: A Discovery Record object.
        :param snmp_engine: SNMP engine to use for this check.

        :return: A dictionary containing discovery_record with group_name.
        """
        discovery_record.address = ip
        transport_target = await setup_transport_target(discovery_record)
        auth_data = await get_discovery_auth(logger, discovery_record, snmp_engine)

        error_indication, error_status, error_index, var_binds = await get_cmd(
            snmp_engine,
            auth_data,
            transport_target,
            ContextData(),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
        )

        if error_indication:
            logger.debug(f"SNMP error for {ip}: {error_indication}")
            return None

        if error_status != 0:
            logger.debug(
                f"SNMP error status for {ip}: {error_status} at index {error_index}"
            )
            return None

        group_name = self.find_device_group(var_binds, discovery_record.device_rules)

        return {
            "key": discovery_record.discovery_name,
            "ip": ip,
            "subnet": discovery_record.network_address,
            "group": group_name,
            "version": discovery_record.version,
            "port": discovery_record.port,
            "secret": discovery_record.secret,
            "community": discovery_record.community,
        }

    async def _scan(
        self,
        ip: str,
        discovery_record: DiscoveryRecord,
        snmp_engine: SnmpEngine,
        semaphore: asyncio.Semaphore,
    ) -> dict | None:
        """
        Perform an SNMP check for a single IP address with concurrency control.

        :param ip: IP address to check the snmp device.
        :param discovery_record: Discovery configuration record.
        :param snmp_engine: SNMP engine to reuse for this Celery task.
        :param semaphore: Semaphore used to limit concurrent SNMP checks.
        """
        async with semaphore:
            try:
                result = await self.check_snmp_device(
                    ip,
                    copy.deepcopy(discovery_record),
                    snmp_engine,
                )
                if result:
                    logger.debug(
                        f"SNMP device found: {result}. From discovery: {discovery_record.discovery_name}"
                    )
                return result
            except Exception as e:
                logger.error(f"SNMP check failed for {ip}: {e}")
                return None

    def discover_snmp_devices(
        self,
        ip_list: list[str],
        discovery_record: DiscoveryRecord,
    ) -> list[dict[str, str]]:
        """
        Synchronous wrapper for the async discovery scan.
        This calls asyncio.run() ONCE per task, creating a single event loop
        that handles all SNMP queries concurrently.

        :param ip_list: List of IP addresses to scan
        :param discovery_record: Discovery configuration record

        :return list: A list of dictionaries containing discovered device information
        """
        return asyncio.run(self._discover_snmp_devices(ip_list, discovery_record))

    async def _discover_snmp_devices(
        self,
        ip_list: list[str],
        discovery_record: DiscoveryRecord,
    ) -> list[dict[str, str]]:
        """
        Create one SNMP engine for this discovery run and close it before
        asyncio.run() tears down the event loop used by PySNMP transports.

        :param ip_list: List of IP addresses to scan
        :param discovery_record: Discovery configuration record

        :return list: A list of dictionaries containing discovered device information
        """
        snmp_engine = SnmpEngine()
        try:
            devices_detail = []
            semaphore = asyncio.Semaphore(DISCOVERY_SUBNET_CHECK_CONCURRENCY)

            results = await asyncio.gather(
                *[
                    self._scan(
                        ip,
                        discovery_record,
                        snmp_engine,
                        semaphore,
                    )
                    for ip in ip_list
                ],
                return_exceptions=True,
            )

            for idx, result in enumerate(results):
                if isinstance(result, BaseException):
                    logger.error(
                        f"Snmp check for device {ip_list[idx]} generated an exception : {result}"
                    )
                    continue
                elif result:
                    logger.debug(
                        f"SNMP device found for {ip_list[idx]}: {result}. Device is from discovery: {discovery_record.discovery_name}"
                    )
                    devices_detail.append(result)

            return devices_detail
        finally:
            self.close_snmp_engine(snmp_engine)

    def add_devices_detail_to_csv(
        self, snmp_devices_detail, delete_flag, discovery_name
    ):
        """Add snmp devices detail to CSV"""
        lock = FileLock(DISCOVERY_LOCK_PATH)
        with lock:
            csv_service = CSVRecordManager(DISCOVERY_CSV_PATH)
            if delete_flag is True:
                csv_service.delete_rows_by_key(discovery_name)
            csv_service.create_rows(snmp_devices_detail, delete_flag)

    def do_work(self, discovery_record: DiscoveryRecord) -> list:
        try:
            logger.info(
                f"Starting SNMP discovery for '{discovery_record.discovery_name}' "
                f"on subnet {discovery_record.network_address} with "
                f"DISCOVERY_SUBNET_CHECK_CONCURRENCY: {DISCOVERY_SUBNET_CHECK_CONCURRENCY}"
            )
            host_list = self.get_host_list(discovery_record.network_address)
            logger.info(f"Number of Active hosts: {len(host_list)}")

            snmp_devices_detail = self.discover_snmp_devices(
                host_list, discovery_record
            )

            self.add_devices_detail_to_csv(
                snmp_devices_detail,
                discovery_record.delete_already_discovered,
                discovery_record.discovery_name,
            )
            logger.info(
                f"SNMP discovery completed for '{discovery_record.discovery_name}'. "
                f"Discovered {len(snmp_devices_detail)} devices"
            )
            return snmp_devices_detail
        except Exception as e:
            raise DiscoveryError(
                f"Error occurred while finding SNMP enabled device: {e}"
            )
