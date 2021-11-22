try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass
import csv
import os
import re
from typing import List, Union

import pymongo
import urllib3
import yaml
from bson.objectid import ObjectId
from celery import shared_task
from celery.canvas import chain, chord, group, signature
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.hummanbool import hummanBool
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")


@shared_task()
# This task gets the inventory and creates a task to schedules each walk task
def inventory_seed(path=None):
    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4snmp.targets

    periodic_obj = customtaskmanager.CustomPeriodicTaskManage()

    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        line_count = 0
        for target in csv_reader:
            if line_count == 0:
                print(f'Column names are {", ".join(target)}')
                line_count += 1
                continue
            logger.debug(f"Inventory record {target}")
            ir = InventoryRecord(*target)
            # The default port is 161
            if len(ir.address.split(":")) == 1:
                ir.address = f"{ir.address}:161"

            try:
                wi = float(ir.walk_interval)
                if wi < 0 or wi > 42000:
                    ir.walk_interval = 42000
            except:
                ir.walk_interval = 42000

            if "delete" in target and hummanBool(ir.delete, default=False):
                periodic_obj.delete_task(ir.address)
            else:
                if ir.version not in ("1", "2", "2c", "3"):
                    logger.error("Invalid version in inventory record {row}")
                    continue
                if ir.version == "3" and ir.community == "public":
                    logger.error(
                        "Invalid community in inventory record {row} when version=3 community can not be public"
                    )
                    continue

                if len(ir.community.strip()) == 0:
                    logger.error(
                        "Invalid community in inventory record {row} must not be blank"
                    )
                    continue

                updates = []
                # TODO: if SmartProfiles or profiles is changed we need to set the immediate flag on walk
                updates.append(
                    {
                        "$set": {
                            "config": {
                                "community": {
                                    "version": ir.version,
                                    "name": ir.community,
                                }
                            }
                        }
                    }
                )
                profiles: List[str] = []
                if ir.profiles:
                    profiles = ir.profiles

                SmartProfiles: bool = hummanBool(ir.SmartProfiles, default=True)

                updates.append(
                    {
                        "$set": {
                            "config": {
                                "profiles": {
                                    "SmartProfiles": SmartProfiles,
                                    "StaticProfiles": profiles,
                                }
                            }
                        }
                    }
                )
                ur = targets_collection.update_one(
                    {"target": ir.address}, updates, upsert=True
                )
                fr = targets_collection.find_one({"target": ir.address}, {"_id": True})
                task_config = {
                    "name": f"sc4snmp;{ir.address};walk",
                    "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                    "target": f"{ir.address}",
                    "args": [],
                    "kwargs": {
                        "walk": True,
                        "id": str(fr["_id"]),
                        "address": ir.address,
                        "version": ir.version,
                        "community": ir.community,
                    },
                    "options": {
                        "link": chain(
                            signature("splunk_connect_for_snmp.enrich.tasks.enrich"),
                            group(
                                signature(
                                    "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller"
                                ),
                                chain(
                                    signature(
                                        "splunk_connect_for_snmp.splunk.tasks.prepare"
                                    ),
                                    signature(
                                        "splunk_connect_for_snmp.splunk.tasks.send"
                                    ),
                                ),
                            ),
                        ),
                    },
                    "interval": {"every": ir.walk_interval, "period": "seconds"},
                    "enabled": True,
                }

                if ur.modified_count:
                    logger.debug("Device Config Changed need to walk")
                    logger.info(f"Upserted id: {fr['_id']}")
                    task_config["kwargs"]["id"] = str(fr["_id"])
                    task_config["run_immediately"] = True
                else:
                    task_config["kwargs"]["id"] = str(fr["_id"])
                periodic_obj.manage_task(run_immediately_if_new=True, **task_config)
    return True


@shared_task()
def inventory_setup_poller(work):
    logger.warn(f"work {work}")
    with open("config.yaml") as file:
        config_base = yaml.safe_load(file)

    periodic_obj = customtaskmanager.CustomPeriodicTaskManage()

    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4snmp.targets

    target = targets_collection.find_one(
        {"_id": ObjectId(work["id"])},
        {"target": True, "state": True, "config": True},
    )
    assigned_profiles: dict[int, list[str]] = {}
    logger.debug(f"target is target {target}")
    logger.debug(f" Config base is {config_base}")
    if target["config"]["profiles"]["SmartProfiles"]:
        for profile_name, profile in config_base["poller"]["profiles"].items():
            logger.debug(f"Checking match for {profile_name} {profile}")

            # Skip this profile its disabled
            if hummanBool(profile.get("disabled", False), default=False):
                logger.debug(f"Skipping disabled profile {profile_name}")
                continue

            if "frequency" not in profile:
                logger.error(f"Profile {profile_name} has no frequency")
                continue

            if "condition" not in profile:
                logger.error(f"Profile {profile_name} has no condition")
                continue

            if "type" not in profile["condition"]:
                logger.error(f"Profile {profile_name} condition has no type")
                continue

            if profile["condition"]["type"] not in ("base", "field"):
                logger.info("Profile is not smart")
                continue

            if (
                profile["condition"]["type"] == "field"
                and "field" not in profile["condition"]
            ):
                logger.error(f"Profile {profile_name} condition has no field")
                continue
            if (
                profile["condition"]["type"] == "field"
                and "patterns" not in profile["condition"]
            ):
                logger.error(f"Profile {profile_name} condition has no patterns")
                continue

            # skip this profile it is static
            if profile["condition"]["type"] == "base":
                logger.debug(f"Adding base profile {profile_name}")
                logger.debug(f"profile is a base {profile_name}")
                if profile["frequency"] not in assigned_profiles:
                    assigned_profiles[profile["frequency"]] = []
                assigned_profiles[profile["frequency"]].append(profile_name)

            elif profile["condition"]["type"] == "field":
                logger.debug(f"profile is a field condition {profile_name}")

                if profile["condition"]["field"].replace(".", "|") in target["state"]:
                    cs = target["state"][
                        profile["condition"]["field"].replace(".", "|")
                    ]

                    for pattern in profile["condition"]["patterns"]:

                        result = re.match(pattern, cs["value"])
                        if result:
                            logger.debug(f"Adding smart profile {profile_name}")
                            if profile["frequency"] not in assigned_profiles:
                                assigned_profiles[profile["frequency"]] = []
                            assigned_profiles[profile["frequency"]].append(profile_name)
                            continue
    else:
        for profile_name in target["config"]["profiles"]["StaticProfiles"]:
            if profile_name in config_base["poller"]["profiles"]:
                profile = config_base["poller"]["profiles"][profile_name]
                if profile["frequency"] not in assigned_profiles:
                    assigned_profiles[profile["frequency"]] = []
                assigned_profiles[profile["frequency"]].append(profile_name)

    logger.debug(f"Profiles Assigned {assigned_profiles}")

    activeschedules: list[str] = []
    for period in assigned_profiles:
        run_immediately: bool = False
        if period > 300:
            run_immediately = True
        name = f"sc4snmp;{target['target']};{period};poll"
        period_profiles = set(assigned_profiles[period])
        activeschedules.append(name)

        varbinds_bulk = {}
        varbinds_get = {}
        varbinds_oid = []
        # First pass we only look at profiles for a full mib walk
        for ap in period_profiles:
            profile_binds = config_base["poller"]["profiles"][ap]["varBinds"]
            for pb in profile_binds:
                if str(pb[0]).find(".") == -1:
                    if len(pb) == 1:
                        if pb[0] not in varbinds_bulk:
                            varbinds_bulk[pb[0]] = None
        # Second pass we only look at profiles for a tabled mib walk
        for ap in period_profiles:
            profile_binds = config_base["poller"]["profiles"][ap]["varBinds"]
            for pb in profile_binds:
                if str(pb[0]).find(".") == -1:
                    if len(pb) == 2:
                        if pb[0] not in varbinds_bulk:
                            varbinds_bulk[pb[0]] = [pb[1]]
                        elif (
                            pb[0] in varbinds_bulk and pb[1] not in varbinds_bulk[pb[0]]
                        ):
                            varbinds_bulk[pb[0]].append(pb[1])

        # #Third pass we only look at profiles for a get mib walk, we only need
        # #to do gets if there is not a bulk/walk
        for ap in period_profiles:
            profile_binds = config_base["poller"]["profiles"][ap]["varBinds"]
            for pb in profile_binds:
                if str(pb[0]).find(".") == -1:
                    if len(pb) == 3:
                        if pb[0] not in varbinds_bulk or (
                            pb[0] in varbinds_bulk and pb[1] not in varbinds_bulk[pb[0]]
                        ):
                            if pb[0] not in varbinds_get:
                                varbinds_get[pb[0]] = {}
                            if pb[1] not in varbinds_get[pb[0]]:
                                varbinds_get[pb[0]][pb[1]] = []

                            varbinds_get[pb[0]][pb[1]].append(pb[2])

        for ap in period_profiles:
            profile_binds = config_base["poller"]["profiles"][ap]["varBinds"]
            for pb in profile_binds:
                if str(pb[0]).find(".") > -1:
                    varbinds_oid.append(pb[0])

        task_config = {
            "name": name,
            "task": "splunk_connect_for_snmp.snmp.tasks.poll",
            "target": f"{target['target']}",
            "args": [],
            "kwargs": {
                "id": work["id"],
                "address": target["target"],
                "version": target["config"]["community"]["version"],
                "community": target["config"]["community"]["name"],
                "profiles": period_profiles,
                "varbinds_bulk": varbinds_bulk,
                "varbinds_get": varbinds_get,
                "varbinds_oid": varbinds_oid,
            },
            "options": {
                "link": chain(
                    signature("splunk_connect_for_snmp.enrich.tasks.enrich"),
                    chain(
                        signature("splunk_connect_for_snmp.splunk.tasks.prepare"),
                        signature("splunk_connect_for_snmp.splunk.tasks.send"),
                    ),
                ),
            },
            "interval": {"every": period, "period": "seconds"},
            "enabled": True,
            "run_immediately": run_immediately,
        }
        periodic_obj.manage_task(**task_config)
    periodic_obj.delete_unused_poll_tasks(f"{target['target']}", activeschedules)
