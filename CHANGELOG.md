# Changelog

## Unreleased

### Changed
- add option to automatically poll SNMP objects based on provided conditions with conditional profiles

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