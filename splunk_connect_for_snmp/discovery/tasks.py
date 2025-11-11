from celery import shared_task
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.discovery.discovery_manager import Discovery

logger = get_task_logger(__name__)


@shared_task(bind=True, base=Discovery)
def discovery(self, **kwargs) -> dict:
    discovery_record = DiscoveryRecord(**kwargs)
    result = self.do_work(discovery_record)
    return {"snmp_device_details": result}
