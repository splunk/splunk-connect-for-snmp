# Installation of SC4SNMP on small environment

SC4SNMP can be successfully installed on small environments with 2 CPUs and 4 Gb of memory.
One important thing to remember is that Splunk OpenTelemetry Collector for Kubernetes cannot be installed on such a small
environment along with SC4SNMP. The other difference from normal installation is that resources limits must be set for Kubernetes
pods. Example `values.yaml` with the appropriate resources can be seen bellow:

```yaml
splunk:
  enabled: true
  protocol: https
  host: ###SPLUNK_HOST###
  token: ###SPLUNK_TOKEN###
  insecureSSL: "false"
  port: "###SPLUNK_PORT###"
image:
  pullPolicy: "Always"
traps:
  replicaCount: 1
  resources:
     limits:
       cpu: 300m
       memory: 300Mi
     requests:
       cpu: 60m
       memory: 256Mi
  communities:
    2c:
      - public
      - homelab
  #usernameSecrets:
  #  - sc4snmp-hlab-sha-aes
  #  - sc4snmp-hlab-sha-des

  #loadBalancerIP: The IP address in the metallb pool
  loadBalancerIP: ###X.X.X.X###
worker:
  # There are 3 types of workers 
  trap:
    # replicaCount: number of trap-worker pods which consumes trap tasks
    replicaCount: 1
    resources:
      limits:
        cpu: 200m
        memory: 400Mi
      requests:
        cpu: 40m
        memory: 260Mi
    #autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 40
    #  targetCPUUtilizationPercentage: 80
  poller:
    # replicaCount: number of poller-worker pods which consumes polling tasks
    replicaCount: 1
    resources:
      limits:
        cpu: 400m
        memory: 400Mi
      requests:
        cpu: 100m
        memory: 260Mi
    #autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 40
    #  targetCPUUtilizationPercentage: 80
  sender:
    # replicaCount: number of sender-worker pods which consumes sending tasks
    replicaCount: 1
    resources:
      limits:
        cpu: 200m
        memory: 500Mi
      requests:
        cpu: 20m
        memory: 260Mi
    # autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 40
    #  targetCPUUtilizationPercentage: 80
  # udpConnectionTimeout: timeout in seconds for SNMP operations
  #udpConnectionTimeout: 5
  logLevel: "INFO"
scheduler:
  logLevel: "INFO"
  resources:
     limits:
       cpu: 40m
       memory: 300Mi
     requests:
       cpu: 20m
       memory: 180Mi
#  profiles: |
#    generic_switch:
#      frequency: 60
#      varBinds:
#        - ['SNMPv2-MIB', 'sysDescr']
#        - ['SNMPv2-MIB', 'sysName', 0]
#        - ['IF-MIB']
#        - ['TCP-MIB']
#        - ['UDP-MIB']
poller:
 # usernameSecrets:
 #   - sc4snmp-hlab-sha-aes
 #   - sc4snmp-hlab-sha-des
 # inventory: |
 #   address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
 #   10.0.0.1,,3,,sc4snmp-hlab-sha-aes,,1800,,,
 #   10.0.0.199,,2c,public,,,3000,,,True
 #   10.0.0.100,,3,,sc4snmp-hlab-sha-des,,1800,,,
sim:
  # sim must be enabled if you want to use signalFx
  enabled: false
#  signalfxToken: BCwaJ_Ands4Xh7Nrg
#  signalfxRealm: us0
mongodb:
  pdb:
    create: true
  persistence:
    storageClass: "microk8s-hostpath"
  volumePermissions:
    enabled: true
inventory:
  resources:
     limits:
       cpu: 60m
       memory: 312Mi
     requests:
       cpu: 20m
```

The rest of the installation is the same as in [online](gettingstarted/sc4snmp-installation.md) or 
[offline](offlineinstallation/offline-sc4snmp.md) installation.