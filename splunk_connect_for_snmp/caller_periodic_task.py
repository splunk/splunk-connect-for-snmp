import logging

# Get an instance of a logger
logging.basicConfig(level="DEBUG")
logging.info("Oh hi!")
from splunk_connect_for_snmp import customtaskmanager

schedule_data_create_interval = {
    "name": "sc4snmp;inventory;seed",
    "task": "splunk_connect_for_snmp.inventory.tasks.inventory_seed",
    "args": [],
    "kwargs": {
        "url": "https://gist.githubusercontent.com/rfaircloth-splunk/0590fa671f794902005257bcbd2ee274/raw/1ca50f510742f14ba40d2dd787f060af94d25bd9/snmp_inventory.csv"
    },
    "interval": {"every": 20, "period": "seconds"},
    "enabled": True,
}

periodic_obj = customtaskmanager.CustomPeriodicTaskManage()
print(periodic_obj.manage_task(**schedule_data_create_interval))
