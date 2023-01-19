# Changelog

## Unreleased

- update mibserver to 1.15.0 and document how to use local MIBs feature

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