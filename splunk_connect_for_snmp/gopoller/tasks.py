from splunk_connect_for_snmp.gopoller.run_walk_no_celery import GosnmpPoller
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
import os
from celery import shared_task
from celery.utils.log import get_task_logger
from mongolock import MongoLockLocked
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError
import re

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
WALK_RETRY_MAX_INTERVAL = int(os.getenv("WALK_RETRY_MAX_INTERVAL", "180"))
WALK_MAX_RETRIES = int(os.getenv("WALK_MAX_RETRIES", "5"))
SPLUNK_SOURCETYPE_TRAPS = os.getenv("SPLUNK_SOURCETYPE_TRAPS", "sc4snmp:traps")
OID_VALIDATOR = re.compile(r"^([0-2])((\.0)|(\.[1-9][0-9]*))*$")

@shared_task(
    bind=True,
    base=GosnmpPoller,
    retry_backoff=30,
    retry_backoff_max=WALK_RETRY_MAX_INTERVAL,
    max_retries=WALK_MAX_RETRIES,
    autoretry_for=(
        MongoLockLocked,
        SnmpActionError,
    ),
    throws=(
        SnmpActionError,
        SnmpActionError,
    ),
)
def go_poller_celery(self, **kwargs):
    ir = InventoryRecord(address="3.22.240.75", port=1162, version="2c", community="public", secret="",
                         security_engine="", walk_interval=1800, profiles=[], smart_profiles=False,
                         delete=False, group=None)

    print("Star walk")
    retry, remotemibs, metrics = self.do_work(ir, True, [])
    print(f"Result metrics:\n{metrics}")
