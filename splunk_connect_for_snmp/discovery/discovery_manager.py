from celery import Task
import os
import fnmatch
import copy
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.common.csv_record_manager import CSVRecordManager
from splunk_connect_for_snmp.snmp.auth import get_auth, setup_transport_target

import nmap
from celery.utils.log import get_task_logger
from pysnmp.hlapi import (
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    getCmd,
)

logger = get_task_logger(__name__)

DISCOVERY_PATH = os.getenv("DISCOVERY_PATH", "/app/discovery/discovery_devices.csv")

class Discovery(Task):
    def __init__(self):
        self.snmp_engine = SnmpEngine()
        pass

    def discover_active_hosts(self, subnet, is_ipv6):
        """Scan subnet for active host using nmap"""
        nm = nmap.PortScanner()
        try:
            nm.scan(hosts=subnet, arguments= ("-6 " if is_ipv6 else "") + "-sn -Pn -T4 --min-rate 1000")
            return nm.all_hosts() 
        except Exception as e:
            logger.error(f"Error occured running nmap scan: {e}")
            raise
    
    def get_host_list(self, subnet, skip_active_check: bool, is_ipv6: bool):
        """Get host list based on the active check flag"""
        try:
            logger.debug(f"Skip active check : {skip_active_check}")
            if skip_active_check:
                network = ipaddress.ip_network(subnet)
                return list(str(ip) for ip in network.hosts())
            else:
                hosts = self.discover_active_hosts(subnet, is_ipv6)
                return hosts
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
            group_name = "Default_group"
            _, value = var_binds[0]
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


    def discover_snmp_devices_details(self, ip_list: list, discovery_record: DiscoveryRecord, max_threads=5):
        """Scan subnet for SNMP-enabled devices using multithreading."""
        devices_detail = []

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_ip = {
                executor.submit(self.check_snmp_device, ip=ip, discovery_record=copy.deepcopy(discovery_record)): ip
                for ip in ip_list
            }

            for count, future in enumerate(as_completed(future_to_ip), start=10):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        devices_detail.append(result)
                        logger.debug(f"SNMP device found: {result}. Device is from discovery: {discovery_record.discovery_name}")
                except Exception as e:
                    logger.error(f"Snmp check for device {ip} generated an exception : {e}")

        return devices_detail
        
    def add_devices_detail_to_csv(self, snmp_devices_detail, delete_flag):
        """Add snmp devices detail to CSV"""
        csv_service = CSVRecordManager(DISCOVERY_PATH)
        if delete_flag == True:    
            csv_service.delete_rows_by_key(snmp_devices_detail[0]['key'])
        csv_service.create_rows(snmp_devices_detail)
        csv_service.dataframe_to_csv(csv_service.df)

    def do_work(self, discovery_record: DiscoveryRecord) -> list:
        try:
            host_list = self.get_host_list(discovery_record.network_address, discovery_record.skip_active_check, discovery_record.is_ipv6)
            logger.debug(f"Number of Active hosts: {len(host_list)}")
            snmp_devices_detail = self.discover_snmp_devices_details(host_list, discovery_record, max_threads=10)
            self.add_devices_detail_to_csv(snmp_devices_detail, discovery_record.delete_already_discovered)
            
            return snmp_devices_detail
        except Exception as e:
            logger.error(f"Error occurred while finding SMNP enabled device: {e}")
            raise
    
