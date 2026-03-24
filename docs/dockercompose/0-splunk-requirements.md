# Prerequisites for the Splunk Connect for SNMP

Splunk Connect for SNMP (SC4SNMP) collects SNMP data from network devices and forwards it to Splunk. It supports two modes of operation:

- **Polling** — SC4SNMP periodically queries devices for metrics and status data according to a configurable schedule.
- **Traps** — SC4SNMP listens for trap notifications that devices send spontaneously (for example, on a link-down event).

The Docker Compose deployment runs SC4SNMP as a set of containers on a single Linux host. The following components are started:

| Component | Role |
|---|---|
| **Scheduler** | Manages the polling schedule and dispatches tasks |
| **Worker Poller** | Executes SNMP queries against devices |
| **Worker Trap** | Receives and processes incoming SNMP trap notifications |
| **Worker Sender** | Forwards collected data to Splunk via HEC |
| **MIB Server** | Translates numeric OIDs to human-readable names |
| **Redis** | Message broker between the scheduler and workers |
| **MongoDB** | Stores SC4SNMP configuration and state |
| **CoreDNS** | Internal DNS resolver for the container network |

The Docker Compose deployment does not include a web UI. All configuration is done by editing files directly.

## Setup flow overview

1. **Prerequisites** *(this page)* — prepare Splunk indexes and HEC token
2. **Install Docker** — install Docker on the host machine
3. **Download package** — download and extract the `docker_compose.zip` package
4. **Configure** — create and edit the required configuration files in this order:
    1. [Inventory file](3-inventory-configuration.md) — define which devices to poll
    2. [Scheduler config](4-scheduler-configuration.md) — define polling profiles, communities, and groups
    3. [Traps config](5-traps-configuration.md) — define communities and secrets for receiving traps
    4. [SNMPv3 secrets](../configuration/snmpv3.md) *(optional)* — create Docker secrets for SNMPv3 credentials
    5. [`.env` file](6-env-file-configuration.md) — set file paths, Splunk connection details, and tuning parameters
5. **Deploy** — run `docker compose up -d`

See the following prerequisites for the Splunk Connect for SNMP.

### Requirements for Splunk Enterprise or Enterprise Cloud

1. Manually create the following indexes in Splunk:
   
   * Index to store Splunk Connect for SNMP logs:
       * em_logs (event type)
   * Destination indexes for forwarding SNMP data: 
       * netmetrics (metrics type)
       * netops (event type)
   
> **_Note:_** `netmetrics` and `netops` are the default names of SC4SNMP indexes. You can use the index names of your choice and
> reference it in the `.env` file later on. See [SC4SNMP Parameters](6-env-file-configuration.md#splunk-instance) for details.

2. Create or obtain a new Splunk HTTP Event Collector token and the correct HTTPS endpoint.
3. Verify the token using [curl](https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector). The endpoint must use a publicly trusted certificate authority.

Once the above steps are complete, proceed to [Install Docker](./1-install-docker.md).