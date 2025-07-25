# Changelog

## Unreleased

### Changed

### Fixed


## [1.12.3]

### Changed
- change redis service name workers call from redis-headless to redis-master
- migrate MongoDB subchart to 15.6.26
- update MongoDB docker image to 7.0.14 for SC4SNMP docker installation

### Fixed
- Ensured `.Values.secret.name` is used during secret creation to prevent mismatched secret references in deployments
- lack of `externalTrafficPolicy` in `values.schema.json`
- update `mibserver` to 1.15.21 to fix problems with rendering pvc in case of local mibs compilation


## [1.12.2]

### Changed
- add IF-MIB.ifOperStatus to baseIF profile
- allow to set subnets for docker network configuration from .env file
- update ipv4 and ipv6 traps to be sent on the same port

### Fixed
- add communities for v1 traps
- add nodeSelector to worker chart
- upgrade base docker image
- dns resolution if only ipv4 is used
- fix CVEs on docker image

## [1.12.1]

### Changed
- general refactor of documentation
- merge docker compose files into one

### Fixed
- dns resolution for ipv6

## [1.12.0]

### Changed
- add metrics dashboard
- add support for IPv6 polling and traps for kubernetes deployment
- add support for IPv6 polling and traps for docker deployment
- add nodeSelector and podAntiAffinity to sim chart
- add support for new IP format in dashboard

## [1.11.0]

### Changed
- add docker compose deployment
- update default microk8s to 1.30
- change group and user ID in Docker image to 10001:10001
- create and/or change ownership of /tmp and /.pysnmp to 10001:10001 in Dockerfile
- while mounting volumes in docker compose explicitly mount them as read only or read write
- added `values.yaml` schema validation using `values.schema.json`
- released beta version of improved polling performance
- added `yamllint` validation for the `values.yaml` formatting
- added "in code" validation of groups and profiles
- added logs configuration to docker compose deployment
- add support for different security level in snmp v3

### Fixed
- fixed a bug with configuration from values.yaml not being transferred to the UI while migrating to SC4SNMP-UI

## [1.10.0]

### Changed
- add sc4snmp ui
- add reverse dns lookup in traps
- upgrade chart dependencies: redis to ~18.5.0, mibserver to 1.15.7
- add beta support for docker-compose deployment
- add log messages for invalid traps configuration
- review and update of documentation

### Fixed
- error handling to be more precise

## [1.9.3]

### Changed
- add regex and option to negate conditional profiles search
- downgrade of some log messages from warning to info
- upgrade of pymongo to v4
- make max walk retries configurable and decrease it from 50 to 5 by default to not waste time and resources on 
continuously ask devices that does not respond

### Fixed
- empty profile name when MIB family name and a polled varbind differs
- stop mib search on vendor if oid is for enterprise tree

## [1.9.2]

### Changed
- add option to enable liveness and readiness probes on workers

## [1.9.1]

### Changed
- add option to configure sourcetype for traps and polling events
- integration tests moved from AWS to github-actions

### Fixed
- missing mongodb's persistence and trap's loadBalancerIp in values.yaml file
- securityEngineId set from inventory.csv

## [1.9.0]

### Changed
- add possibility to poll compound indexes (more than one value, ex. `['IP-MIB', 'ipAddressStatus', 'ipv4', '172.31.27.144']`)
- add option to automatically poll SNMP objects based on provided conditions with conditional profiles
- remove IF-MIB from the scope of the default small walk

### Fixed
- possibility to use hostname instead of the bare ip address in polling
- getting rid off `An error of SNMP isWalk=False for a host 54.91.99.113 occurred: tooBig at ?` with limiting maximum 
number of varBinds polled at once `maxOidToProcess`

## [1.8.6]

### Changed

- update mibserver to 1.15.0 and document how to use local MIBs feature
- update mibserver to 1.15.1 to allow local MIB compilation in offline environment

### Fixed

- fix metrics enrichment issue - context were overwritten in some cases in the MongoDB, and the results looked not coherent

## [1.8.5]

### Changed

- delete lookup chart functionality as it wasn't working with older versions of Kubernetes
- add NodePort option for trap service to make using SC4SNMP in multinode easier
- appending OID metrics index on demand
- update mibserver to 1.14.10
- upgrade versions of charts: MongoDB to 12.1.31, Redis to 17.3.18
- add migration for MongoDB chart (setFeatureCompatibilityVersion and recreate as an updateStartegy)

### Fixed

- fix wrongly mounted usernameSecrets 