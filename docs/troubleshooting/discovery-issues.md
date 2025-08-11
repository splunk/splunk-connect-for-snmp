# Troubleshooting Discovery Issues


## Permission denied while writing discovery file

Discovery fails with a `PermissionError` related to `discovery_devices.csv`. In such cases, you may see the following error:

```log
PermissionError: [Errno 13] Permission denied: '/app/discovery/discovery_devices.csv'
```

The folder specified in the `discoveryPath` value (which is mounted to `/app/discovery` inside the container) does not have the correct permissions for the application user (UID `10001`) to write files.

Ensure that the folder specified in the `discoveryPath` has write permissions for UID `10001`. You can fix this by updating the folder ownership or permissions before starting the containers.

**Example (on the host system):**
```bash
sudo chown 10001:10001 /your/local/folder/path
sudo chmod 755 /your/local/folder/path
```

## Discovery not completing within the time limit

If the subnet being scanned has a large IP range (e.g., `/22`, `/21`, or bigger), the task may not complete within the default time limit of **2400 seconds**. In such cases, you may see the following error:

```log
[2025-08-07 06:03:29,415: ERROR/MainProcess] Hard time limit (2400s) exceeded for splunk_connect_for_snmp.discovery.tasks.discovery
```


Increase the task timeout value using the `taskTimeout` field under the `worker` section in your `values.yaml`:

```yaml
worker:
  taskTimeout: 3600  # Increase based on expected duration
```

## Discovery takes too much time

Discovery tasks may take longer to complete due to unnecessary SNMP requests or long wait times when scanning large subnets. Below are few ways to optimize performance:

**Enable Active Device Check**

Set the `skip_active_check` flag to `false` so that SNMP requests are sent **only** to devices that are active in the given subnet.  
This reduces the total number of SNMP request and speeds up the discovery process.

**Adjust Timeout and Retries**
  
If the subnet has very few SNMP-enabled devices, high timeout and retry values can significantly slow down the process.  
For example, with the default `udpConnectionTimeout` of `3` seconds and `udpConnectionRetries` of `5`, a non-SNMP-enabled device will take up to **15 seconds** before moving to the next IP.  
Consider lowering the retry parameters to speed up execution:

```yaml
worker:
  udpConnectionTimeout: 3
  udpConnectionRetries: 2
```

> **Note:** Reduce these values carefully. Setting them too low may cause missed detections in slow or high-latency networks, which can impact data accuracy.

## No Output in `discovery_devices.csv`

After running a discovery task, no entries are written to the `discovery_devices.csv` file. The issue might have several root causes. Some of them are:

- Wrong device IP or port provided.
- Subnet contains no reachable or SNMP-enabled devices.
- Nmap is unable to detect live hosts due to network or firewall restrictions.
- For SNMPv2c: Incorrect community string.
- For SNMPv3: Incorrect privacy key or authentication credentials.

**Resolution:**
- Double-check the IP range or subnet provided in the discovery config.
- Validate that the target devices have SNMP enabled and are reachable from the container.
- Ensure firewall rules or network policies allow NMAP scan or enable `skip_active_check` to skip the NMAP scan. 
- Verify SNMP credentials (community string or SNMPv3 credentials) for correctness.
