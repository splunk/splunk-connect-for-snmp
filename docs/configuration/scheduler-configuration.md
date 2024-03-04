# Scheduler configuration
The scheduler is a service that manages schedules for SNMP walks and GETs. The definitions of the schedules
are stored in MongoDB. 
 
### Scheduler configuration file

Scheduler configuration is kept in `values.yaml` file, in the section `scheduler`.
`values.yaml` is used during the installation process to configure Kubernetes values.

See the following example: 
```yaml
scheduler:
  logLevel: "WARN"
  profiles: |
    test_profile:
      frequency: 5 
      condition: 
        type: "field" 
        field: "SNMPv2-MIB.sysDescr" 
        patterns: 
          - "^.*"
      varBinds:
          # Syntax: [ "MIB-Component", "MIB object name"[Optional], "MIB index number"[Optional]]
        - ["SNMPv2-MIB", "sysDescr",0]
```

### Define log level
The log level for the scheduler can be set by changing the value for the `logLevel` key. The allowed values are `DEBUG`, `INFO`, `WARNING`, or `ERROR`. 
The default value is `WARNING`.

### Define resource requests and limits
```yaml
scheduler:
  #The following resource specification is appropriate for most deployments to scale the
  #Larger inventories may require more memory but should not require additional cpu
  resources:
    limits:
        cpu: 1
        memory: 1Gi
    requests:
      cpu: 200m
      memory: 128Mi
```

### Define groups of hosts
For more information on when to use groups, see [Configuring Groups](configuring-groups.md).

See the following example group configuration:
```yaml
scheduler:
  groups: |
    example_group_1:
      - address: 123.0.0.1
        port: 161
      - address: 178.8.8.1
        port: 999
      - address: 12.22.23
        port: 161
        community: 'private'
    example_group_2:
      - address: 103.0.0.1
        port: 1161
        version: '3'
        secret: 'my_secret'
      - address: 178.80.8.1
        port: 999
```

The one obligatory field for the host configuration is `address`. If `port` isn't configured its default value is `161`. 
Other fields that can be modified here are: `community`, `secret`, `version`, and `security_engine`.
However, if they remain unspecified in the host configuration, they will be derived from the inventory record. 

### Define the expiration time for tasks

Define the time, in seconds, when polling or walk tasks will be revoked if they haven't been picked up by the worker. See the [celery documentation](https://docs.celeryq.dev/en/stable/userguide/calling.html#expiration) for more details.
```yaml
scheduler:
  tasksExpiryTime: 300
```
