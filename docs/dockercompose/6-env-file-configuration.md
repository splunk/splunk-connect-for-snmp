# .env file configuration

Inside the directory with the docker compose files, there is a `.env`. Variables in it can be divided into few sections.

## Deployment

| Variable                              | Description                                                                                          |
|---------------------------------------|------------------------------------------------------------------------------------------------------| 
| `SC4SNMP_IMAGE`                       | The registry and name of the SC4SNMP image to pull                                                   |
| `SC4SNMP_TAG`                         | SC4SNMP image tag to pull                                                                            |
| `SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH` | Absolute path to [scheduler-config.yaml](./4-scheduler-configuration.md) file                        |
| `TRAPS_CONFIG_FILE_ABSOLUTE_PATH`     | Absolute path to [traps-config.yaml](./5-traps-configuration.md) file                                |
| `INVENTORY_FILE_ABSOLUTE_PATH`        | Absolute path to [inventory.csv](./3-inventory-configuration.md) file                                |
| `COREFILE_ABS_PATH`                   | Absolute path to Corefile used by coreDNS. Default Corefile can be found inside the `docker_compose` |
| `COREDNS_ADDRESS`                     | IP address of the coredns inside docker network. Shouldn’t be changed                                |
| `SC4SNMP_VERSION`                     | Version of SC4SNMP                                                                                   |

## Images of dependencies 

| Variable          | Description                          |
|-------------------|--------------------------------------| 
| `COREDNS_IMAGE`   | Registry and name of Coredns image   |
| `COREDNS_TAG`     | Coredns image tag to pull            |
| `MIBSERVER_IMAGE` | Registry and name of Mibserver image |
| `MIBSERVER_TAG`   | Mibserver image tag to pull          |
| `REDIS_IMAGE`     | Registry and name of Redis image     |
| `REDIS_TAG`       | Redis image tag to pull              |
| `MONGO_IMAGE`     | Registry and name of MongoDB image   |
| `MONGO_TAG`       | MongoDB image tag to pull            |

## Splunk instance

| Variable                            | Description                                                                                                          |
|-------------------------------------|----------------------------------------------------------------------------------------------------------------------| 
| `SPLUNK_HEC_HOST`                   | IP address or a domain name of a Splunk instance to send data to                                                     |
| `SPLUNK_HEC_PROTOCOL`               | The protocol of the HEC endpoint: `https` or `http`                                                                  |
| `SPLUNK_HEC_PORT`                   | The port of the HEC endpoint                                                                                         |
| `SPLUNK_HEC_TOKEN`                  | Splunk HTTP Event Collector token                                                                                    |
| `SPLUNK_HEC_INSECURESSL`            | Whether to skip checking the certificate of the HEC endpoint when sending data over HTTPS                            |
| `SPLUNK_SOURCETYPE_TRAPS`           | Splunk sourcetype for trap events                                                                                    |
| `SPLUNK_SOURCETYPE_POLLING_EVENTS`  | Splunk sourcetype for non-metric polling events                                                                      |
| `SPLUNK_SOURCETYPE_POLLING_METRICS` | Splunk sourcetype for metric polling events                                                                          |
| `SPLUNK_HEC_INDEX_EVENTS`           | Name of the Splunk event index                                                                                       |
| `SPLUNK_HEC_INDEX_METRICS`          | Name of the Splunk metrics index                                                                                     |
| `SPLUNK_HEC_PATH`                   | Path for the HEC endpoint                                                                                            |
| `SPLUNK_AGGREGATE_TRAPS_EVENTS`     | When set to true makes traps events collected as one event inside splunk                                             |
| `IGNORE_EMPTY_VARBINDS`             | Details can be found in [empty snmp response message issue](../bestpractices.md#empty-snmp-response-message-problem) |

## Workers

| Variable                     | Description                                                                                                                                          |
|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------| 
| `WALK_RETRY_MAX_INTERVAL`    | Maximum time interval between walk attempts                                                                                                          |
| `WALK_MAX_RETRIES`           | Maximum number of walk retries                                                                                                                       |
| `METRICS_INDEXING_ENABLED`   | Details can be found in [append oid index part to the metrics](../configuration/poller-configuration.md#append-oid-index-part-to-the-metrics)        |
| `POLL_BASE_PROFILES`         | Enable polling base profiles (with IF-MIB and SNMPv2-MIB)                                                                                            |
| `IGNORE_NOT_INCREASING_OIDS` | Ignoring `occurred: OID not increasing` issues for hosts specified in the array, ex: IGNORE_NOT_INCREASING_OIDS=127.0.0.1:164,127.0.0.6              |
| `WORKER_LOG_LEVEL`           | Logging level of the workers, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL                                                      |
| `UDP_CONNECTION_TIMEOUT`     | Timeout in seconds for SNMP operations                                                                                                               |
| `MAX_OID_TO_PROCESS`         | Sometimes SNMP Agent cannot accept more than X OIDs per once, so if the error "TooBig" is visible in logs, decrease the number of MAX_OID_TO_PROCESS |
| `WORKER_POLLER_CONCURRENCY`  | Minimum number of threads in the poller container                                                                                                    |
| `WORKER_SENDER_CONCURRENCY`  | Minimum number of threads in the sender container                                                                                                    |
| `WORKER_TRAP_CONCURRENCY`    | Minimum number of threads in the trap container                                                                                                      |
| `PREFETCH_POLLER_COUNT`      | How many tasks are consumed from the queue at once in the poller container                                                                           |
| `PREFETCH_SENDER_COUNT`      | How many tasks are consumed from the queue at once in the sender container                                                                           |
| `PREFETCH_TRAP_COUNT`        | How many tasks are consumed from the queue at once in the trap container                                                                             |
| `RESOLVE_TRAP_ADDRESS`       | Use reverse dns lookup for trap IP address and send the hostname to Splunk                                                                           |
| `MAX_DNS_CACHE_SIZE_TRAPS`   | If RESOLVE_TRAP_ADDRESS is set to true, this is the maximum number of records in cache                                                               |
| `TTL_DNS_CACHE_TRAPS`        | If RESOLVE_TRAP_ADDRESS is set to true, this is the time to live of the cached record in seconds                                                     |

## Inventory

| Variable                     | Description                                                                                       |
|------------------------------|---------------------------------------------------------------------------------------------------| 
| `INVENTORY_LOG_LEVEL`        | Logging level of the inventory, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL |
| `CHAIN_OF_TASKS_EXPIRY_TIME` | Tasks expirations time in seconds                                                                 |

## Traps

| Variable                     | Description                                                                                                                                                                                                                     |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| 
| `SNMP_V3_SECURITY_ENGINE_ID` | SNMPv3 TRAPs require the configuration SNMP Engine ID of the TRAP sending application for the USM users table of the TRAP receiving application for each USM user, for example: SNMP_V3_SECURITY_ENGINE_ID=80003a8c04,aab123456 |
| `TRAPS_PORT`                 | External port exposed for traps server                                                                                                                                                                                          |

## Scheduler

| Variable              | Description                                                                                       |
|-----------------------|---------------------------------------------------------------------------------------------------| 
| `SCHEDULER_LOG_LEVEL` | Logging level of the scheduler, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL |