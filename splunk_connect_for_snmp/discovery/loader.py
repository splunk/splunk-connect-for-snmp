import ipaddress
import logging
import os
import sys
from contextlib import suppress

import yaml

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.common.task_generator import DiscoveryTaskGenerator
from splunk_connect_for_snmp.poller import app

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

DISCOVERY_CONFIG_PATH = os.getenv(
    "DISCOVERY_CONFIG_PATH", "/app/discovery/discovery-config.yaml"
)
CHAIN_OF_TASKS_EXPIRY_TIME = os.getenv("CHAIN_OF_TASKS_EXPIRY_TIME", "60")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

formatter = CustomisedJSONFormatter()

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.addHandler(handler)


def autodiscovery_task_definition(discovery_record, app):
    discovery_definition = DiscoveryTaskGenerator(
        discovery_record=discovery_record, app=app
    )
    task_config = discovery_definition.generate_task_definition()
    return task_config


def check_ipv6(subnet):
    network = ipaddress.ip_network(subnet, strict=False)
    return isinstance(network, ipaddress.IPv6Network)


def load():
    try:
        with open(DISCOVERY_CONFIG_PATH, encoding="utf-8") as file:
            config_runtime = yaml.safe_load(file)
        ipv6_enabled = config_runtime.get("ipv6Enabled", False)
        autodiscovery = config_runtime.get("autodiscovery", {})
        periodic_obj = customtaskmanager.CustomPeriodicTaskManager()
        expiry_time_changed = periodic_obj.did_expiry_time_change(
            CHAIN_OF_TASKS_EXPIRY_TIME
        )
        if expiry_time_changed:
            logger.info(
                f"Task expiry time was modified, generating new tasks for discovery"
            )

        for key, value in autodiscovery.items():
            value["discovery_name"] = key
            discovery_record = DiscoveryRecord(**value)
            is_ipv6 = check_ipv6(value["network_address"])
            if not is_ipv6 or (is_ipv6 and ipv6_enabled):
                logger.info(f"Adding the task for {key}")
                task_config = autodiscovery_task_definition(
                    discovery_record=discovery_record, app=app
                )
                periodic_obj.manage_task(**task_config)
            else:
                logger.info(
                    f"Skipping task for the discovery: {key} because IPv6 is disabled."
                )
        return 0
    except Exception as e:
        logger.error("Error occured while creating the task : {e}")
        raise


if __name__ == "__main__":
    r = load()
    if r:
        sys.exit(0)
