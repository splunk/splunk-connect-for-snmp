# Prerequisites for the Splunk Connect for SNMP

## Setup flow overview

1. **Prerequisites** *(this page)* - prepare Splunk indexes and HEC token
2. **Install Docker** - install Docker on the host machine
3. **Download package** - download and extract the `docker_compose.zip` package
4. **Configure** - create and edit the required configuration files in this order:
    1. [Inventory file](3-inventory-configuration.md) - define which devices to poll
    2. [Scheduler config](4-scheduler-configuration.md) - define polling profiles, communities, and groups
    3. [Traps config](5-traps-configuration.md) - define communities and secrets for receiving traps
    4. [SNMPv3 secrets](../configuration/snmpv3.md) *(optional)* - create Docker secrets for SNMPv3 credentials
    5. [`.env` file](6-env-file-configuration.md) - set file paths, Splunk connection details, and tuning parameters
5. **Deploy** - run `docker compose up -d`

### Requirements for Splunk Enterprise or Enterprise Cloud

1. Manually create the following indexes in Splunk:
   
   * Index to store Splunk Connect for SNMP logs:
       * em_logs (event type)
   * Destination indexes for forwarding SNMP data: 
       * netmetrics (metrics type)
       * netops (event type)
   
!!!note 
    `netmetrics` and `netops` are the default names of SC4SNMP indexes. You can use the index names of your choice and reference it in the `.env` file later on. See [SC4SNMP Parameters](6-env-file-configuration.md#splunk-instance) for details.

2. Create or obtain a new Splunk HTTP Event Collector token and the correct HTTPS endpoint.
3. Verify the token using [curl](https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector). The endpoint must use a publicly trusted certificate authority.

Once the above steps are complete, proceed to [Install Docker](./1-install-docker.md).