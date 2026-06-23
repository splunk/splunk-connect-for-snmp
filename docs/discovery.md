# Discovery

## Purpose
The SNMP Discovery feature in Splunk Connect for SNMP provides an automated way to identify SNMP-enabled devices within user-specified subnets. Instead of manually scanning networks or maintaining a static list of devices, users can now use this feature to generate an up-to-date list of IP addresses where SNMP is actively running.

!!! info
    The current implementation does not automatically integrate discovered devices into the polling pipeline. The discovered IPs are saved to an output file, which can then be reviewed or used manually to update your SNMP polling configuration.


### This feature is useful when:
- Visibility into which devices in the network have SNMP enabled is required.
- A fast way to generate a list of devices for which further monitoring is needed.

## How It Works
The discovery process consists of two main steps:

### 1. List devices
To begin, the system identifies all the devices within the defined subnet.

### 2. SNMP Probing
Once the list of devices is identified:

- The system sends SNMP requests to each device using the credentials specified in the configuration (e.g., community strings or SNMPv3 secrets).
- If the device responds successfully to an SNMP poll, the IP is considered SNMP-enabled.
- All such devices along with some details are saved to a defined output file.

This output can later be used by the user to configure polling.

### Multi-Subnet Support
Multiple discovery jobs can be configured to run independently for different subnets. Each job can have its frequency, SNMP version, credentials, and grouping logic. This makes it easy to scan different parts of your network separately.

## Output Format
After each discovery run, a file named `discovery_devices.csv` is generated in the path defined by `discoveryPath`. This file includes all successfully discovered SNMP devices and can be used in poller configuration. The CSV file contains fields like key (discovery name), subnet, ip address, port, snmp version, group, secret, and community.

To use this feature, the user must provide a valid path where the CSV file will be created. Note that this is a single shared file, and all discovery jobs for different subnets will update the same file.

Example:

```csv
key,subnet,ip,port,version,group,secret,community
discovery_version2c,10.202.4.200/30,10.202.4.202,161,2c,linux-group,,public
```

!!! info
    This file serves as a reference and does not automatically update any active polling configuration. Users are expected to manually review and incorporate this list into their SNMP polling setup as needed.


## Configuration
To configure and run SNMP Autodiscovery, refer to:
- [Docker Compose discovery configuration](./dockercompose/11-discovery-configuration.md)
- [Microk8s discovery configuration](./microk8s/configuration/discovery-configuration.md)
