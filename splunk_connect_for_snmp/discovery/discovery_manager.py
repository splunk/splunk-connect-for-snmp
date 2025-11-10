import copy
import fnmatch
import ipaddress
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import nmap
from celery import Task
from celery.utils.log import get_task_logger
from filelock import FileLock
from pysnmp.hlapi import ContextData, ObjectIdentity, ObjectType, SnmpEngine, getCmd

from splunk_connect_for_snmp.common.csv_record_manager import CSVRecordManager
from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.snmp.auth import get_auth, setup_transport_target

logger = get_task_logger(__name__)

DISCOVERY_FOLDER_PATH = os.getenv("DISCOVERY_FOLDER_PATH", "/app/discovery")
DISCOVERY_CSV_PATH = os.path.join(DISCOVERY_FOLDER_PATH, "discovery_devices.csv")
DISCOVERY_LOCK_PATH = os.path.join(DISCOVERY_FOLDER_PATH, "discovery_devices.lock")


class Discovery(Task):
    def __init__(self):
        self.snmp_engine = SnmpEngine()

    def get_host_list(self, subnet):
        """Get host list"""
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            return list(str(ip) for ip in network.hosts())
        except Exception as e:
            logger.error(f"Error occured while finding active hosts: {e}")
            raise

    def check_snmp_device(self, ip, discovery_record: DiscoveryRecord):
        """Check if an SNMP device responds at the given IP."""
        discovery_record.address = ip
        auth_data = get_auth(logger, discovery_record, SnmpEngine())
        transport_target = setup_transport_target(discovery_record)
        iterator = getCmd(
            SnmpEngine(),
            auth_data,
            transport_target,
            ContextData(),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
        )

        error_indication, error_status, error_index, var_binds = next(iterator)

        if not error_indication and error_status == 0:
            group_name = "default_group"
            _, value = var_binds[0]
            if isinstance(discovery_record.device_rules, list):
                for device_rule in discovery_record.device_rules:
                    regex_pattern = fnmatch.translate(device_rule["patterns"])
                    if re.search(regex_pattern, value.prettyPrint(), re.IGNORECASE):
                        group_name = device_rule["group"]
                        break
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
        return None

    def discover_snmp_devices_details(
        self, ip_list: list, discovery_record: DiscoveryRecord, max_threads=5
    ):
        """Scan subnet for SNMP-enabled devices using multithreading."""
        devices_detail = []

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_ip = {
                executor.submit(
                    self.check_snmp_device,
                    ip=ip,
                    discovery_record=copy.deepcopy(discovery_record),
                ): ip
                for ip in ip_list
            }

            for _, future in enumerate(as_completed(future_to_ip), start=1):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        devices_detail.append(result)
                        logger.debug(
                            f"SNMP device found: {result}. Device is from discovery: {discovery_record.discovery_name}"
                        )
                except Exception as e:
                    logger.error(
                        f"Snmp check for device {ip} generated an exception : {e}"
                    )

        return devices_detail

    def add_devices_detail_to_csv(
        self, snmp_devices_detail, delete_flag, dicovery_name
    ):
        """Add snmp devices detail to CSV"""
        lock = FileLock(DISCOVERY_LOCK_PATH)
        with lock:
            csv_service = CSVRecordManager(DISCOVERY_CSV_PATH)
            if delete_flag is True:
                csv_service.delete_rows_by_key(dicovery_name)
            csv_service.create_rows(snmp_devices_detail, delete_flag)

    def do_work(self, discovery_record: DiscoveryRecord) -> list:
        try:
            host_list = self.get_host_list(
                discovery_record.network_address,
            )
            logger.debug(f"Number of Active hosts: {len(host_list)}")
            snmp_devices_detail = self.discover_snmp_devices_details(
                host_list, discovery_record, max_threads=10
            )
            self.add_devices_detail_to_csv(
                snmp_devices_detail,
                discovery_record.delete_already_discovered,
                discovery_record.discovery_name,
            )

            return snmp_devices_detail
        except Exception as e:
            logger.error(f"Error occurred while finding SMNP enabled device: {e}")
            raise
