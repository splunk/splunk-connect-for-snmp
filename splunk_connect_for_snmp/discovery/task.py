from celery import shared_task
import time
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(bind=True, expires=60)
def autodiscover(self):
    logger.info("🚀 Autodiscover task started")
    print("🔍 Running autodiscovery task...")
    time.sleep(1)  # Simulate discovery
    discovered_hosts = ["192.168.1.1", "192.168.1.2"]
    print(f"✅ Discovered hosts: {discovered_hosts}")
    return {"hosts": discovered_hosts}
