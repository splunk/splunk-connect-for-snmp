# Changelog

## Unreleased

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