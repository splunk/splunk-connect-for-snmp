# Offline SC4SNMP installation

## Local machine with internet access
To install the SC4SNMP offline, first, some packages must be downloaded from the Github release and then moved
to the SC4sNMP installation server. Those packages are:

- `dependencies-images.tar`
- `splunk-connect-for-snmp-chart.tar`

Moreover, SC4SNMP Docker image must be pulled, saved as a `.tar` package, and then moved to the server as well. 
This process requires Docker to be installed locally.

Images can be pulled from the following repository: `ghcr.io/splunk/splunk-connect-for-snmp/container:<tag>`. 
The latest tag can be found [here](https://github.com/splunk/splunk-connect-for-snmp) under the Releases section with the label `latest`.


Example of docker pull command:

```bash
docker pull ghcr.io/splunk/splunk-connect-for-snmp/container:<tag>
```

Then save the image. Directory where this image will be saved can be specified after the `>` sign:

```bash
docker save ghcr.io/splunk/splunk-connect-for-snmp/container:<tag> > snmp_image.tar
```
All three packages, `snmp_image.tar`, `dependencies-images.tar`, and `splunk-connect-for-snmp-chart.tar`, must be moved to the SC4SNMP installation server.

## Installation on the server

On the server, all the images must be imported to the microk8s cluster. This can be done with the following command:

```bash
microk8s ctr image import <name_of_tar_image>
```

In case of this installation the following commands must be run:

```bash
microk8s ctr image import dependencies-images.tar
microk8s ctr image import snmp_image.tar 
```

Then create `values.yaml`. It's a little different from `values.yaml` used in an online installation. 
The difference between the two files is the following, which is used for automatic image pulling:

```yaml
image:
  pullPolicy: "Never"
```

Example `values.yaml` file:
```yaml
splunk:
  enabled: true
  protocol: https
  host: ###SPLUNK_HOST###
  token: ###SPLUNK_TOKEN###
  insecureSSL: "false"
  port: "###SPLUNK_PORT###"
image:
  pullPolicy: "Never"
traps:
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
    replicaCount: 2
    #autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 40
    #  targetCPUUtilizationPercentage: 80
  poller:
    # replicaCount: number of poller-worker pods which consumes polling tasks
    replicaCount: 2
    #autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 40
    #  targetCPUUtilizationPercentage: 80
  sender:
    # replicaCount: number of sender-worker pods which consumes sending tasks
    replicaCount: 1
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
  image:
    pullPolicy: "Never"
#  signalfxToken: BCwaJ_Ands4Xh7Nrg
#  signalfxRealm: us0
mongodb:
  image:
    pullPolicy: "Never"
  pdb:
    create: true
  persistence:
    storageClass: "microk8s-hostpath"
  volumePermissions:
    enabled: true
redis:
  image:
    pullPolicy: "Never"
```

The next step is to unpack the chart package `splunk-connect-for-snmp-chart.tar`. It will result in creating the `splunk-connect-for-snmp` directory:

```bash
tar -xvf splunk-connect-for-snmp-chart.tar --exclude='._*'
```

Finally, run the helm install command in the directory where both the `values.yaml` and `splunk-connect-for-snmp` directories are located:

```bash
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```
