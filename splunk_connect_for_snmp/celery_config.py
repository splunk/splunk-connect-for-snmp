# Support use of .env file for developers
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import os

MONGO_DB = os.getenv("MONGO_DB", "SC4SNMP")
MONGO_DB_SCHEDULES = os.getenv("MONGO_DB_SCHEDULES", "schedules")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_CELERY_DATABASE = os.getenv("MONGO_DB_CELERY_DATABASE", MONGO_DB)

# broker
broker_url = os.getenv("CELERY_BROKER_URL")
# results config
result_backend = MONGO_URI
mongodb_backend_settings = {"database": MONGO_DB_CELERY_DATABASE}


beat_scheduler = "celerybeatmongo.schedulers.MongoScheduler"
mongodb_scheduler_url = MONGO_URI
mongodb_scheduler_db = MONGO_DB_CELERY_DATABASE
# mongodb_scheduler_connection_alias = "sc4snmp_celery_beat"
