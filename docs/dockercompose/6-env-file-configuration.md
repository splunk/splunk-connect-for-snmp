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
| `SC4SNMP_VERSION`                     | Version of SC4SNMP                                                                                   |
| `DEPLOYMENT_USER`                       | A user name to set in the deployment environment. The default value is sc4snmp.                                                   |


## Network configuration

| Variable               | Description                                                              |
|------------------------|--------------------------------------------------------------------------| 
| `COREDNS_ADDRESS`      | IP address of the coredns inside docker network. Should not be changed   |
| `COREDNS_ADDRESS_IPv6` | IPv6 address of the coredns inside docker network. Should not be changed |
| `IPv6_ENABLED`         | Enable receiving traps and polling from IPv6 devices                     |
| `IPAM_SUBNET`          | Subnet in CIDR format that represents a network segment                  |
| `IPAM_GATEWAY`         | IPv4 gateway for the master subnet                                       |
| `IPAM_SUBNET_IPv6`     | Subnet in CIDR format that represents a network segment for IPv6         |
| `IPAM_GATEWAY_IPv6`    | IPv6 gateway for the master subnet                                       |

!!! info
    In case of configuring more than one IPv4 and IPv6 subnet in IPAM, docker compose file should be edited.

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

| Variable                                  | Description                                                                                                                           |
|-------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------| 
| `SPLUNK_HEC_HOST`                         | IP address or a domain name of a Splunk instance to send data to                                                                      |
| `SPLUNK_HEC_PROTOCOL`                     | The protocol of the HEC endpoint: `https` or `http`                                                                                   |
| `SPLUNK_HEC_PORT`                         | The port of the HEC endpoint                                                                                                          |
| `SPLUNK_HEC_TOKEN`                        | Splunk HTTP Event Collector token                                                                                                     |
| `SPLUNK_HEC_INSECURESSL`                  | Whether to skip checking the certificate of the HEC endpoint when sending data over HTTPS                                             |
| `SPLUNK_SOURCETYPE_TRAPS`                 | Splunk sourcetype for trap events                                                                                                     |
| `SPLUNK_SOURCETYPE_POLLING_EVENTS`        | Splunk sourcetype for non-metric polling events                                                                                       |
| `SPLUNK_SOURCETYPE_POLLING_METRICS`       | Splunk sourcetype for metric polling events                                                                                           |
| `SPLUNK_HEC_INDEX_EVENTS`                 | Name of the Splunk event index                                                                                                        |
| `SPLUNK_HEC_INDEX_METRICS`                | Name of the Splunk metrics index                                                                                                      |
| `SPLUNK_HEC_PATH`                         | Path for the HEC endpoint                                                                                                             |
| `SPLUNK_AGGREGATE_TRAPS_EVENTS`           | When set to true makes traps events collected as one event inside splunk                                                              |
| `SPLUNK_METRIC_NAME_HYPHEN_TO_UNDERSCORE` | Replaces hyphens with underscores in generated metric names to ensure compatibility with Splunk's metric schema                       |
| `IGNORE_EMPTY_VARBINDS`                   | Details can be found in [empty snmp response message issue](../troubleshooting/polling-issues.md#empty-snmp-response-message-problem) |
| `SPLUNK_LOG_INDEX`                        | Event index in Splunk where logs from docker containers would be sent                                                                 |

## Workers

### General
| Variable                     | Description                                                                                                                                            |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| `WALK_RETRY_MAX_INTERVAL`    | Maximum time interval between walk attempts                                                                                                            |
| `WALK_MAX_RETRIES`           | Maximum number of walk retries                                                                                                                         |
| `METRICS_INDEXING_ENABLED`   | Details can be found in [append oid index part to the metrics](../microk8s/configuration/poller-configuration.md#append-oid-index-part-to-the-metrics) |
| `POLL_BASE_PROFILES`         | Enable polling base profiles (with IF-MIB and SNMPv2-MIB)                                                                                              |
| `IGNORE_NOT_INCREASING_OIDS` | Ignoring `occurred: OID not increasing` issues for hosts specified in the array, ex: IGNORE_NOT_INCREASING_OIDS=127.0.0.1:164,127.0.0.6                |
| `WORKER_LOG_LEVEL`           | Logging level of the workers, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL                                                        |
| `UDP_CONNECTION_TIMEOUT`     | Timeout in seconds for SNMP operations                                                                                                                 |
| `MAX_OID_TO_PROCESS`         | Sometimes SNMP Agent cannot accept more than X OIDs per once, so if the error "TooBig" is visible in logs, decrease the number of MAX_OID_TO_PROCESS   |
| `MAX_REPETITIONS`            | The amount of requested next oids in response for each of varbinds in one request sent                                                                |
| `MAX_SNMP_BULK_WALK_CONCURRENCY` | The maximum number of concurrent SNMP bulk walks (bulk_walk_cmd) that can be executed at the same time. Default is 5. Setting this control determines the number of OID subtrees are walked in parallel and helps prevent overwhelming the target device or network. |
                                                            |
| `MAX_REPETITIONS`            | The amount of requested next oids in response for each of varbinds in one request sent                                                               |

### Worker Poller
| Variable                            | Description                                                                |
|-------------------------------------|----------------------------------------------------------------------------| 
| `WORKER_POLLER_CONCURRENCY`         | Minimum number of threads in the poller container                          |
| `PREFETCH_POLLER_COUNT`             | How many tasks are consumed from the queue at once in the poller container |
| `WORKER_POLLER_REPLICAS`            | Number of docker replicas of worker poller container                       |
| `WORKER_POLLER_CPU_LIMIT`           | Limit of cpu that worker poller container can use                          |
| `WORKER_POLLER_MEMORY_LIMIT`        | Limit of memory that worker poller container can use                       |
| `WORKER_POLLER_CPU_RESERVATIONS`    | Dedicated cpu resources for worker poller container                        |
| `WORKER_POLLER_MEMORY_RESERVATIONS` | Dedicated memory resources for worker poller container                     |

### Worker Sender
| Variable                            | Description                                                                |
|-------------------------------------|----------------------------------------------------------------------------| 
| `WORKER_SENDER_CONCURRENCY`         | Minimum number of threads in the sender container                          |
| `PREFETCH_SENDER_COUNT`             | How many tasks are consumed from the queue at once in the sender container |
| `WORKER_SENDER_REPLICAS`            | Number of docker replicas of worker sender container                       |
| `WORKER_SENDER_CPU_LIMIT`           | Limit of cpu that worker sender container can use                          |
| `WORKER_SENDER_MEMORY_LIMIT`        | Limit of memory that worker sender container can use                       |
| `WORKER_SENDER_CPU_RESERVATIONS`    | Dedicated cpu resources for worker sender container                        |
| `WORKER_SENDER_MEMORY_RESERVATIONS` | Dedicated memory resources for worker sender container                     |

### Worker Trap
| Variable                          | Description                                                                                      |
|-----------------------------------|--------------------------------------------------------------------------------------------------| 
| `WORKER_TRAP_CONCURRENCY`         | Minimum number of threads in the trap container                                                  |
| `PREFETCH_TRAP_COUNT`             | How many tasks are consumed from the queue at once in the trap container                         |
| `RESOLVE_TRAP_ADDRESS`            | Use reverse dns lookup for trap IP address and send the hostname to Splunk                       |
| `MAX_DNS_CACHE_SIZE_TRAPS`        | If RESOLVE_TRAP_ADDRESS is set to true, this is the maximum number of records in cache           |
| `TTL_DNS_CACHE_TRAPS`             | If RESOLVE_TRAP_ADDRESS is set to true, this is the time to live of the cached record in seconds |
| `WORKER_TRAP_REPLICAS`            | Number of docker replicas of worker trap container                                               |
| `WORKER_TRAP_CPU_LIMIT`           | Limit of cpu that worker trap container can use                                                  |
| `WORKER_TRAP_MEMORY_LIMIT`        | Limit of memory that worker trap container can use                                               |
| `WORKER_TRAP_CPU_RESERVATIONS`    | Dedicated cpu resources for worker trap container                                                |
| `WORKER_TRAP_MEMORY_RESERVATIONS` | Dedicated memory resources for worker trap container                                             |

## Inventory

| Variable                     | Description                                                                                       |
|------------------------------|---------------------------------------------------------------------------------------------------| 
| `INVENTORY_LOG_LEVEL`        | Logging level of the inventory, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL |
| `CHAIN_OF_TASKS_EXPIRY_TIME` | Tasks expirations time in seconds                                                                 |

## Traps

| Variable                     | Description                                                                                                                                                                                                                     |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| 
| `SNMP_V3_SECURITY_ENGINE_ID` | SNMPv3 TRAPs require the configuration SNMP Engine ID of the TRAP sending application for the USM users table of the TRAP receiving application for each USM user, for example: SNMP_V3_SECURITY_ENGINE_ID=80003a8c04,aab123456 |
| `INCLUDE_SECURITY_CONTEXT_ID` | Controls whether to add the context_engine_id field to v3 trap events                                                                                                                                                           |
| `TRAPS_PORT`                 | External port exposed for traps server                                                                                                                                                                                          |
## Scheduler

| Variable              | Description                                                                                       |
|-----------------------|---------------------------------------------------------------------------------------------------| 
| `SCHEDULER_LOG_LEVEL` | Logging level of the scheduler, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL |