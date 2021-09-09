# Getting Started



### Requirements (microk8s installation)

Basic installation of microk8s:
```yaml
#we need to have a normal install of kubectl because of operator scripts
sudo snap install kubectl --classic
sudo snap install microk8s --classic
# Basic setup of k8s
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube

su - $USER
microk8s status --wait-ready
#Note when installing metallb you will be prompted for one or more IPs to used as entry points
#Into the cluster if your plan to enable clustering this IP should not be assigned to the host (floats)
#If you do not plan to cluster then this IP may be the same IP as the host
#Note2: a single IP in cidr format is x.x.x.x/32 use CIDR or range syntax
microk8s enable dns metallb rbac storage openebs helm3
microk8s status --wait-ready
#
```

## Deploy

This step will install SC4SNMP and its depdenencies including snapd,
micrk8s and sck. This script has been tested with Centos 7, Centos 8,
Redhat 8, and Ubuntu 20.04. Both interactive and non-interactive options
are supported

### Deploy SC4SNMP Interactive

``` bash
curl -sfL https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/main/deploy/install.bash | sudo -E bash -
```

### Deploy SC4SNMP non-interactive

``` bash
curl -sfL https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/main/deploy/install.bash  | \
MODE=splunk \
PROTO=https \
INSECURE_SSL=true \
HOST=i-08c221389a3b9899a.ec2.splunkit.io \
PORT=8088 \
TOKEN=450a69af-16a9-4f87-9628-c26f04ad3785 \
METRICS_INDEX=em_metrics \
EVENTS_INDEX=em_logs \
META_INDEX=em_meta \
CLUSTER_NAME=foo \
SHAREDIP=10.202.18.166/32 \
RESOLVERIP=8.8.4.4 \
sudo -E bash -
```

-   Confirm deployment using
    `microk8s.kubectl get svc -n sc4snmp`confirm the value of
    external-ip in the row below matches IP used above

``` bash
NAME                 TYPE           CLUSTER-IP       EXTERNAL-IP    PORT(S)             AGE
sc4-snmp-traps       LoadBalancer   10.152.183.134   10.202.6.253   162:32652/UDP       28h
```

### Test Monioring with SCK (Requires Splunk)

Confirm the following search returns results
`| mcatalog values(metric_name)  where index=em_metrics AND metric_name=kube* AND host=<hostname>`

### Test SNMP Traps

-   Test the trap from a linux system with snmp installed replace the ip
    `10.0.101.22` with the shared ip above

``` bash
apt-get install snmpd
snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test
```

-   Search splunk, one event per trap command with the host value of the
    test machine ip will be found

``` bash
index=em_logs sourcetype="sc4snmp:traps"
```

### Setup Poller

-   Test the poller by logging to Splunk and confirm presence of events
    in snmp em_logs and metrics in em_metrics index.

\* You can change the inventory contents in scheduler-config.yaml and
use following command to apply the changes to Kubernetes cluster. Agents
configuration is placed in scheduler-config.yaml under section
inventory.csv, content below is interpreted as csv file with following
columns:

1.  host (IP or name)
2.  version of SNMP protocol
3.  community string authorisation phrase
4.  profile of device (varBinds of profiles can be found in convig.yaml
    section of scheduler-config.yaml file)
5.  frequency in seconds (how often SNMP connector should ask agent for
    data)

``` bash
curl -o ~/scheduler-inventory.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/main/deploy/sc4snmp/ftr/scheduler-inventory.yaml
vi ~/scheduler-inventory.yaml
# Remove the comment from line 2 and correct the ip and community value
kubectl apply -n sc4snmp -f ~/scheduler-inventory.yaml
```

### Test Poller

Search splunk, one event per trap command with the host value of the
test machine ip will be found

``` bash
index=em_meta sourcetype="sc4snmp:meta" SNMPv2_MIB__sysLocation_0="*" | dedup host
```

``` bash
| mcatalog values(metric_name)  where index=em_metrics AND metric_name=sc4snmp* AND host=<hostname>
```

### Maintain

Manage configuration obtain and update communities, user/secrets and
inventories
