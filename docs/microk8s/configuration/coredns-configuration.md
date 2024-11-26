# Configuration of CoreDNS in microk8s to use different nameservers for different domains and ip ranges


In MicroK8s, CoreDNS is enabled by running the following command: `microk8s enable dns`.

Alternatively, you can specify a list of DNS servers by running the command: `microk8s enable dns:8.8.8.8,1.1.1.1`.

The servers in the provided list are expected to be capable of resolving the same addresses. 
If one of these servers is unreachable, another one is used. 
If the requirement is to use different DNS servers for various domains or different IP ranges in the case of reverse lookup, the configuration differs.

Before executing `microk8s enable dns`, the first step is to edit `coredns.yaml`, located inside the MicroK8s installation folder.
An example path is: `/var/snap/microk8s/common/addons/core/addons/dns/coredns.yaml`.


Inside `coredns.yaml`, there is a complete configuration for the CoreDNS deployment.
The only section that requires editing is the ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
  labels:
    addonmanager.kubernetes.io/mode: EnsureExists
    k8s-app: kube-dns
data:
  Corefile: |
    .:53 {
        errors
        health {
          lameduck 5s
        }
        ready
        log . {
          class error
        }
        kubernetes cluster.local in-addr.arpa ip6.arpa {
          pods insecure
          fallthrough in-addr.arpa ip6.arpa
        }
        prometheus :9153
        forward . $NAMESERVERS
        cache 30
        loop
        reload
        loadbalance
    }
```

Changes should be made in `data.Corefile` within this ConfigMap. Presented documentation explains basic configuration. 
For more details, refer to the official CoreDNS [documentation](https://coredns.io/manual/toc/).


Updated ConfigMap:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
  labels:
    addonmanager.kubernetes.io/mode: EnsureExists
    k8s-app: kube-dns
data:
  Corefile: |
      .:53 {
        errors
        health {
          lameduck 5s
        }
        ready
        log . {
          class error
        }
        kubernetes cluster.local in-addr.arpa ip6.arpa {
          pods insecure
          fallthrough in-addr.arpa ip6.arpa
        }
        prometheus :9153
        forward . $NAMESERVERS
        cache 1
        loop
        reload
        loadbalance
      }
      dummyhost.com:53 {
      errors
        health {
          lameduck 5s
        }
        ready
        log . {
          class error
        }
        kubernetes cluster.local in-addr.arpa ip6.arpa {
          pods insecure
          fallthrough in-addr.arpa ip6.arpa
        }
        prometheus :9153
        forward . 4.3.2.1
        cache 1
        loop
        reload
        loadbalance
      }
      2.1.in-addr.arpa:53 {
       errors
        health {
          lameduck 5s
        }
        ready
        log . {
          class error
        }
        kubernetes cluster.local in-addr.arpa ip6.arpa {
          pods insecure
          fallthrough in-addr.arpa ip6.arpa
        }
        prometheus :9153
        forward . 4.3.2.1
        cache 1
        loop
        reload
        loadbalance
      }
```

Two server blocks, `dummyhost.com:53` and `2.1.in-addr.arpa:53`, have been added.

The `dummyhost.com:53` server block is used to resolve all hosts within the `dummyhost.com` domain. 
The DNS server used for these hosts is specified in the forward plugin as `4.3.2.1`. 
Additional information about the forward plugin can be found in the official CoreDNS [documentation](https://coredns.io/plugins/forward/).

The `2.1.in-addr.arpa:53` server block is added for reverse DNS lookup for all devices in the IPv4 range `1.2.0.0/16`. 
The DNS server is the same as in the `dummyhost.com:53` server block.

All other DNS requests will be handled by the `8.8.8.8` server if `microk8s enable dns` is run without providing a list of DNS servers. 
Alternatively, one of the servers provided in the list will be used in the case of running with the list of servers, 
i.e., `microk8s enable dns:8.8.8.8,1.1.1.1`.