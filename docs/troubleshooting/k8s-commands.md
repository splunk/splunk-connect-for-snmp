## Kubectl commands

For full display of kubernetes commands and their usage can be found at [kubectl documentation](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands). 
Below are the most common commands used to troubleshoot issues with SC4SNMP. 

### Common flags
The following are some common flags that can be used with the `kubectl` commands:

- `-A` flag is used to list all resources in all namespaces
- `-n` flag is used to specify the namespace of the resource
- `-f` flag is used to specify the file that contains the resource definition
- `-o` flag is used to specify the output format of the command

For more flags and options, you can refer to the [kubectl documentation](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands).

### Accessing logs in kubernetes

The instruction on how to set up and access the logs can be found in [SC4SNMP logs](bestpractises) 

### The get command 
The `get` command is used to list one or more resources of selected type. The following are some examples of how to use the `get` command:
```
microk8s kubectl get all
microk8s kubectl get pods 
microk8s kubectl get svc
microk8s kubectl get deployments
microk8s kubectl get events
microk8s kubectl get nodes
microk8s kubectl get configmaps
microk8s kubectl get secrets
microk8s kubectl get ippools
```

For example to list all pods running in sc4snmp namespace you can use command:
```
~$ microk8s kubectl get pods -n sc4snmp
NAME                                                          READY   STATUS    RESTARTS        AGE
snmp-mibserver-95df967b9-cjhvz                                1/1     Running   1 (5h13m ago)   27h
snmp-mongodb-6dc5c4f74d-pxpxb                                 2/2     Running   2 (5h13m ago)   27h
snmp-redis-master-0                                           1/1     Running   1 (5h13m ago)   25h
snmp-splunk-connect-for-snmp-scheduler-7c675d7dd7-6ql2g       1/1     Running   2 (5h13m ago)   27h
snmp-splunk-connect-for-snmp-trap-755b58b8c5-kg5f4            1/1     Running   1 (5h13m ago)   27h
snmp-splunk-connect-for-snmp-trap-755b58b8c5-r8szq            1/1     Running   1 (5h13m ago)   27h
snmp-splunk-connect-for-snmp-worker-poller-5956f6dfb4-rs7mv   1/1     Running   1 (5h13m ago)   27h
snmp-splunk-connect-for-snmp-worker-poller-5956f6dfb4-wjxb6   1/1     Running   1 (5h13m ago)   27h
snmp-splunk-connect-for-snmp-worker-sender-76f5d49478-spvp2   1/1     Running   1 (5h13m ago)   27h
snmp-splunk-connect-for-snmp-worker-trap-5c4dbf8889-4njg2     1/1     Running   1 (5h13m ago)   27h
snmp-splunk-connect-for-snmp-worker-trap-5c4dbf8889-5hc6j     1/1     Running   1 (5h13m ago)   27h
```

### The describe command
The `describe` command is used to get detailed information about a resource. The following are some examples of how to use the `describe` command:
```
microk8s kubectl describe all 
microk8s kubectl describe pod <pod-name>
microk8s kubectl describe svc <service-name>
microk8s kubectl describe deployment <deployment-name>
microk8s kubectl describe events
microk8s kubectl describe node <node-name>
microk8s kubectl describe configmap <configmap-name>
microk8s kubectl describe secret <secret>
microk8s kubectl describe ippool <ippool-name>
```

For example to get detailed information about a service you can use command:
```
~$ microk8s kubectl describe svc/snmp-splunk-connect-for-snmp-trap -n sc4snmp
Name:                     snmp-splunk-connect-for-snmp-trap
Namespace:                sc4snmp
Labels:                   app.kubernetes.io/instance=snmp
                          app.kubernetes.io/managed-by=Helm
                          app.kubernetes.io/name=splunk-connect-for-snmp-trap
                          app.kubernetes.io/version=1.11.0
                          helm.sh/chart=splunk-connect-for-snmp-1.11.0
Annotations:              meta.helm.sh/release-name: snmp
                          meta.helm.sh/release-namespace: sc4snmp
                          metallb.universe.tf/allow-shared-ip: splunk-connect
Selector:                 app.kubernetes.io/instance=snmp,app.kubernetes.io/name=splunk-connect-for-snmp-trap
Type:                     LoadBalancer
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.153.183.151
IPs:                      10.153.183.151
IP:                       34.207.186.189
LoadBalancer Ingress:     34.207.186.189
Port:                     snmp-udp  162/UDP
TargetPort:               2162/UDP
NodePort:                 snmp-udp  31810/UDP
Endpoints:                10.3.209.194:2162,10.3.209.210:2162
Session Affinity:         None
External Traffic Policy:  Local
HealthCheck NodePort:     31789
Events:
  Type    Reason        Age                   From             Message
  ----    ------        ----                  ----             -------
  Normal  nodeAssigned  95s (x45 over 3h30m)  metallb-speaker  announcing from node "ip-172-31-18-142" with protocol "layer2"
```

### The exec command

The `exec` command is used to execute a command in a container. The following are some examples of how to use the `exec` command:
```
microk8s kubectl exec -it <pod-name> -- <command>
```

For example to connect to the container you can use:
```
~$ microk8s kubectl exec -it snmp-mibserver-95df967b9-cjhvz -n sc4snmp  -- /bin/bash 
I have no name!@snmp-mibserver-95df967b9-cjhvz:/app$ 
```

### The top command

The `top` command is used to display resource (CPU/memory) usage. The following are options of how to 
use the `top` command:
```
microk8s kubectl top nodes
microk8s kubectl top pods
```

For example to display resource usage of nodes you can use:
```
~$ microk8s kubectl top pods
NAME                                                              CPU(cores)   MEMORY(bytes)   
sck-splunk-otel-collector-agent-jrl62                             34m          209Mi           
sck-splunk-otel-collector-k8s-cluster-receiver-5c56564cf5-ks2zb   3m           99Mi    
```


## Examples of command usage

### Check secret for snmp v3

One of the issues related to snmp v3 can be incorrectly configured secrets in kubernetes. 
Below you can find the instruction to check the existing secrets and decode their value.

To check the existing secrets:
```
~$ microk8s kubectl get secret -n sc4snmp
NAME                             TYPE                 DATA   AGE
sh.helm.release.v1.snmp.v1       helm.sh/release.v1   1      23h
sh.helm.release.v1.snmp.v2       helm.sh/release.v1   1      21h
splunk-connect-for-snmp-splunk   Opaque               1      23h
testing1                         Opaque               6      68m
```
To get more details about one secret you can use command:
```
~$ microk8s kubectl describe secret/testing1 -n sc4snmp
Name:         testing1
Namespace:    sc4snmp
Labels:       <none>
Annotations:  <none>

Type:  Opaque

Data
====
privProtocol:  3 bytes
securityName:  7 bytes
userName:      8 bytes
authKey:       10 bytes
authProtocol:  3 bytes
privKey:       10 bytes
```
The secrets in kubernetes are not visible in describe command. To fully see them you have to decode them.
Below are some methods to do that:

- With json query:
```
~$ microk8s kubectl get secrets/testing1 -n sc4snmp -o json | jq '.data | map_values(@base64d)'
{
  "authKey": "testing123",
  "authProtocol": "MD5",
  "privKey": "testing123",
  "privProtocol": "AES",
  "securityName": "testing",
  "userName": "testing1"
}
```

- With template: 
```
~$ microk8s kubectl get secrets/testing1 -n sc4snmp --template='{{ range $key, $value := .data }}{{ printf "%s: %s\n" $key ($value | base64decode) }}{{ end }}'
authKey: testing123
authProtocol: MD5
privKey: testing123
privProtocol: AES
securityName: testing
userName: testing1
```

You can also check [this](https://stackoverflow.com/questions/56909180/decoding-kubernetes-secret) thread for different decoding methods.


### Check pods health
To check the health of the pods, you can use the `get` command to look at the `STATUS` and `RESTARTS` columns. 
If the `STATUS` is not `Running` or the `RESTARTS` is not `0`, then there might be an issue with the pod. 
You can also use the `describe` command to get more detailed information about the pod and see if there are any errors or warnings in the `Events`.

### Check resource usage
To check the resource usage of the nodes and pods, you can use the `top` command. 
With this command, you can see the CPU and memory usage of the nodes and pods and compare it with the ones 
assigned in `resources` section in the configuration yaml.
If they are close to each other you might consider increasing the resources assigned.

### Check network
Checking the network configuration can be useful when enabling the dual-stack for SC4SNMP.
The default network controller used by the microk8s is `calico`. 

One of useful commands to check the network configuration is:
```
~$ microk8s kubectl describe daemonset/calico-node -n kube-system
(...)
    Environment:
      DATASTORE_TYPE:                     kubernetes
      WAIT_FOR_DATASTORE:                 true
      NODENAME:                            (v1:spec.nodeName)
      CALICO_NETWORKING_BACKEND:          <set to the key 'calico_backend' of config map 'calico-config'>  Optional: false
      CLUSTER_TYPE:                       k8s,bgp
      IP:                                 autodetect
      IP_AUTODETECTION_METHOD:            first-found
      CALICO_IPV4POOL_VXLAN:              Always
      IP6_AUTODETECTION_METHOD:           first-found
      CALICO_IPV6POOL_CIDR:               fd02::/64
      IP6:                                autodetect
      CALICO_IPV6POOL_VXLAN:              Always
      FELIX_IPINIPMTU:                    <set to the key 'veth_mtu' of config map 'calico-config'>  Optional: false
      FELIX_VXLANMTU:                     <set to the key 'veth_mtu' of config map 'calico-config'>  Optional: false
      FELIX_WIREGUARDMTU:                 <set to the key 'veth_mtu' of config map 'calico-config'>  Optional: false
      CALICO_IPV4POOL_CIDR:               10.3.0.0/16
      CALICO_DISABLE_FILE_LOGGING:        true
      FELIX_DEFAULTENDPOINTTOHOSTACTION:  ACCEPT
      FELIX_IPV6SUPPORT:                  true
      FELIX_HEALTHENABLED:                true
      FELIX_FEATUREDETECTOVERRIDE:        ChecksumOffloadBroken=true
(...)
```
One section of the command is showing the `environment` variables used by the `calico` network controller. 
With seeing them we can check if the different versions of IP are enabled and if the pools for them are 
configured with subnet.

Next useful command to check when having issues with connectivity is:
```
~$ microk8s kubectl describe service/webhook-service -n metallb-system
Name:              webhook-service
Namespace:         metallb-system
Labels:            <none>
Annotations:       <none>
Selector:          component=controller
Type:              ClusterIP
IP Family Policy:  SingleStack
IP Families:       IPv4
IP:                10.153.183.249
IPs:               10.153.183.249
Port:              <unset>  443/TCP
TargetPort:        9443/TCP
Endpoints:         10.3.209.208:9443
Session Affinity:  None
```
`Metallb` is the network load-balancer used by the SC4SNMP. 
With checking the service configuration we can see the IP assigned to the service and the port it is listening on.
When having the issues with dual-stack configuration the `IP Family Policy` and the `IP Families` fields should be checked.

### Check service configuration

Checking the service configuration can be useful when having issues with the traps connectivity. 
For better explanation refer to: [Wrong IP or port](../traps-issues#wrong-ip-or-port)
