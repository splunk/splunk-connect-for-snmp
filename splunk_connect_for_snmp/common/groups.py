import yaml
import os
from celery.utils.log import get_task_logger
try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass


CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
logger = get_task_logger(__name__)


def get_group(group_name):
    addresses = []
    try:
        with open(CONFIG_PATH, encoding="utf-8") as file:
            config_runtime = yaml.safe_load(file)
            if "groups" in config_runtime:
                groups = config_runtime.get("groups", {})
                group = groups[group_name]
                for address in group:
                    addr = address.split(":")
                    ip_add = addr[0]
                    port_no = "" if len(addr) == 1 else addr[1]
                    addresses.append({"ip": ip_add, "port": port_no})
    except FileNotFoundError:
        logger.info(f"File: {CONFIG_PATH} not found")
    return addresses
