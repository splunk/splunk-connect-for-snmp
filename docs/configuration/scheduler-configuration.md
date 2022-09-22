# Scheduler configuration
The scheduler service is responsible for managing schedules for SNMP walks and GETs. Schedule definitions
are stored in Mongo DB. 
 
### Scheduler configuration file

The scheduler configuration is kept in the `values.yaml` file in the 'scheduler' section.
`values.yaml` is used during the installation process for configuring Kubernetes values.

Example:
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
The log level for the scheduler can be set by changing the value OF the `logLevel` key. The allowed values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`. 
The default value is `WARNING`.

### Define resource requests and limits
```yaml
scheduler:
  #The following resource specification is appropriate for most deployments to scale. 
  #Larger inventories may require more memory, but should not require additional CPU
  resources:
    limits:
        cpu: 1
        memory: 1Gi
    requests:
      cpu: 200m
      memory: 128Mi
```

### Define groups of hosts
For more details on when to use groups, see: [Configuring Groups](configuring-groups.md).

Example group configuration:
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

The one obligatory field for the host configuration is `address`. If `port` isn't configured, its default value is `161`. 
Other fields that can be modified here are: `community`, `secret`, `version`, and `security_engine`.
However, if they remain unspecified in the host configuration, they will be derived from the inventory record for this specific group.
