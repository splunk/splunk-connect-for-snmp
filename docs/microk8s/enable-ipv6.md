# Enabling IPv6 for SC4SNMP

Default installation of SC4SNMP does not support polling or receiving trap notifications from IPv6 addresses. To enable IPv6, follow instruction below.

## Microk8s
To configure dual-stack network on microk8s follow instructions at [Microk8s page](https://microk8s.io/docs/how-to-dual-stack).
After completing the steps, you can follow the instruction at [Microk8s installation on Ubuntu](mk8s/k8s-microk8s.md#microk8s-installation-on-ubuntu) 
to install microk8s.

## Calico
The default CNI used for microk8s is Calico. For pods to be able to reach internet over IPv6, you need to enable 
the `natOutgoing` parameter in ipv6 ip pool configuration from calico.
To set it create the yaml file with the following content:
```
# calico-ippool.yaml
---
apiVersion: crd.projectcalico.org/v1
kind: IPPool
metadata:
  name: default-ipv6-ippool
spec:
  natOutgoing: true
```
You can check with command `microk8s kubectl get ippools -n kube-system` the default name of the ip pool for IPv6. 
If it differs from `default-ipv6-ippool` you need to change the name in the yaml file.
Then apply the configuration with the following command:
```
microk8s kubectl apply -f calico-ippool.yaml
```

After those changes you can restart the microk8s for the changes to be applied with the following commands:
```
microk8s stop
microk8s start
```

## Metallb
As of version `1.33` of microk8s, Metallb add-on does not support passing the IPv6 addresses in enable command. To 
add the IPv6 addresses to your Metallb configuration, you can prepare the yaml file with configuration like below:
```
# addresspool.yaml
---
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-addresspool
  namespace: metallb-system
spec: 
  addresses:
  - 1.1.1.1/32
  - 2001:0db8:ac10:fe01:0000:0000:0000:0001/128
```
You can check with command `microk8s kubectl get ipaddresspool -n metallb-system` the default name of the ip address pool created in metallb. If it differs from `default-addresspool` you need to change the name in the yaml file.
You can add the single ip or subnets for both IPv4 and IPv6 under `spec.addresses` section. After preparing the yaml file, apply the configuration with the following command:
```
microk8s kubectl apply -f addresspool.yaml
```

## SC4SNMP
To configure traps to receive notification from IPv4 and IPv6 addresses, you need to add the following configuration to the `values.yaml` file:
```
traps:
  ipFamilyPolicy: RequireDualStack
  ipFamilies: ["IPv4", "IPv6"]
```

To configure poller to poll IPv4 and IPv6 addresses, you need to add the following configuration to the `values.yaml` file:
``` 
poller:
  ipv6Enabled: true
```
