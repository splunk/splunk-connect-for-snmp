# Support use of .env file for developers
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import os

MONGO_DB = os.getenv("MONGO_DB", "sc4")
MONGO_DB_SCHEDULES = os.getenv("MONGO_DB_SCHEDULES", "schedules")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_CELERY_DATABASE= os.getenv("MONGO_DB_CELERY_DATABASE", "sc4snmp_celery")

#broker 
broker_url = os.getenv("CELERY_BROKER_URL")
#results config
result_backend = MONGO_URI
mongodb_backend_settings = {"database": "sc4snmp_celery"}


beat_scheduler = "celerybeatmongo.schedulers.MongoScheduler"
