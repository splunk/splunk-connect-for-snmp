# Offline Microk8s installation issues

See [install alternatives](https://microk8s.io/docs/install-alternatives#heading--offline) for offline installation of Microk8s,  but there are additional steps to install microk8s offline. See the following steps to install offline:

## Importing images

After running the following:

```
snap ack microk8s_{microk8s_version}.assert
snap install microk8s_{microk8s_version}.snap --classic
```

You should check if the microk8s instance is healthy. Do it using the following command:

```commandline
microk8s kubectl get pods -A
```

The output will probably look like:
```
NAMESPACE      NAME                                       READY   STATUS     RESTARTS   AGE
kube-system    calico-kube-controllers-7c9c8dd885-fg8f2   0/1     Pending    0          14m
kube-system    calico-node-zg4c4                          0/1     Init:0/3   0          23s
```

The pods are in the `Pending`/`Init` state because they’re trying to download images, which is impossible to do offline. In order to make them download, you need to download all the images on a different server with an internet connection, pack it up, and import it to a microk8s image registry on your offline server.

### Packing up images for an offline environment

You need to monitor

```commandline
microk8s kubectl get events -A
```

to see if `microk8s` fails to pull images, and then import anything it needs. An example of such information is:

```commandline
kube-system    0s          Warning   Failed              pod/calico-node-sc784                           Failed to pull image "docker.io/calico/cni:v3.21.4": rpc error: code = Unknown desc = failed to pull and unpack image "docker.io/calico/cni:v3.21.4": failed to resolve reference "docker.io/calico/cni:v3.21.4": failed to do request: Head "https://registry-1.docker.io/v2/calico/cni/manifests/v3.21.4": dial tcp 54.83.42.45:443: i/o timeout
kube-system    0s          Warning   Failed              pod/calico-node-sc784                           Error: ErrImagePull
```

The previous information shows you that you lack a `docker.io/calico/cni:v3.21.4` image, and need to import it in order to fix the issue.

The process to do this action is always the following:

```commandline
docker pull <needed_image>
docker save <needed_image> > image.tar
```
Transfer package to the offline lab and execute:

```
microk8s ctr image import image.tar
```


### Example of the offline installation

For example, `microk8s` version `3597` requires the following images to work correctly:

```commandline
docker pull docker.io/calico/kube-controllers:v3.21.4 
docker pull docker.io/calico/node:v3.21.4
docker pull docker.io/calico/pod2daemon-flexvol:v3.21.4
docker pull docker.io/calico/cni:v3.21.4  
docker pull k8s.gcr.io/pause:3.1 
docker pull k8s.gcr.io/metrics-server/metrics-server:v0.5.2 
```

You should issue the above commands on your instance connected to the internet,
then save it to `tar` packages:

```
docker save docker.io/calico/kube-controllers:v3.21.4 > kube-controllers.tar
docker save docker.io/calico/node:v3.21.4 > node.tar
docker save docker.io/calico/pod2daemon-flexvol:v3.21.4 > pod2daemon-flexvol.tar
docker save docker.io/calico/cni:v3.21.4 > cni.tar
docker save k8s.gcr.io/pause:3.1  > pause.tar
docker save cdkbot/hostpath-provisioner:1.2.0 > cdkbot.tar 
docker save k8s.gcr.io/metrics-server/metrics-server:v0.5.2 > metrics.tar
```

After that, `scp` those packages to your offline server and import it to its `microk8s` image registry:

```
microk8s ctr image import kube-controllers.tar
microk8s ctr image import node.tar
microk8s ctr image import pod2daemon-flexvol.tar
microk8s ctr image import cni.tar
microk8s ctr image import pause.tar
microk8s ctr image import metrics.tar
```

NOTE: for other versions of `microk8s`, tags of images may differ. 

After running the following:

```commandline
microk8s enable hostpath-storage
microk8s enable rbac
microk8s enable metrics-server
```

The microk8s instance should be the following:

```
NAMESPACE      NAME                                       READY   STATUS                  RESTARTS   AGE
kube-system    calico-kube-controllers-7c9c8dd885-wxms9   1/1     Running                 0          3h21m
kube-system    calico-node-8cxsq                          1/1     Running                 0          3h21m
kube-system    hostpath-provisioner-f57964d5f-zs4sj       1/1     Running                 0          5m41s
kube-system    metrics-server-5f8f64cb86-x7k29            1/1     Running                 0          2m15s
```

## Enabling DNS and Metallb

`dns` and `metallb` don’t require importing any images, so you can enable them simply through the following commands:

```yaml
microk8s enable dns
microk8s enable metallb
```

For more information on `metallb`, see [Install metallb](../gettingstarted/mk8s/k8s-microk8s.md#install-metallb).

## Installing helm3

Additionally, you need to install the helm3 add-on.  See the following steps:

1. Check your server's platform with:

```commandline
dpkg --print-architecture
```

The output would be, for example: `amd64`.
You need the platform to download the correct version of helm.

2. Download the helm package from `https://get.helm.sh/helm-v3.8.0-linux-{{arch}}.tar.gz`, where `{{arch}}` should be 
replaced with the result from the previous command, for example: `https://get.helm.sh/helm-v3.8.0-linux-amd64.tar.gz`.

3. Rename the package to `helm.tar.gz` and send it to an offline lab.
4. Create `tmp` directory in `/var/snap/microk8s/current` and copy the package in the following locations: 

```
sudo mkdir -p /var/snap/microk8s/current/tmp/helm3
sudo cp helm.tar.gz /var/snap/microk8s/current/tmp/helm3
```

5. Go to the directory containing `enable` script for `helm3`:

```
cd /var/snap/microk8s/common/addons/core/addons/helm3
```

Open `enable` file with vi, nano, or some other editor. Comment this line:

```commandline
#fetch_as $SOURCE_URI/helm-$HELM_VERSION-linux-${SNAP_ARCH}.tar.gz "$SNAP_DATA/tmp/helm3/helm.tar.gz"
```

Save file.

6. Run `microk8s enable helm3`

## Verify your instance

Check if all the add-ons were installed successfully using the following command: `microk8s status --wait-ready`. An example of
a correct output is:

```commandline
microk8s is running
high-availability: no
  datastore master nodes: 127.0.0.1:19001
  datastore standby nodes: none
addons:
  enabled:
    dns                  # (core) CoreDNS
    ha-cluster           # (core) Configure high availability on the current node
    helm3                # (core) Helm 3 - Kubernetes package manager
    hostpath-storage     # (core) Storage class; allocates storage from host directory
    metallb              # (core) Loadbalancer for your Kubernetes cluster
    metrics-server       # (core) K8s Metrics Server for API access to service metrics
    rbac                 # (core) Role-Based Access Control for authorisation
    storage              # (core) Alias to hostpath-storage add-on, deprecated
  disabled:
    community            # (core) The community addons repository
    dashboard            # (core) The Kubernetes dashboard
    gpu                  # (core) Automatic enablement of Nvidia CUDA
    helm                 # (core) Helm 2 - the package manager for Kubernetes
    host-access          # (core) Allow Pods connecting to Host services smoothly
    ingress              # (core) Ingress controller for external access
    mayastor             # (core) OpenEBS MayaStor
    prometheus           # (core) Prometheus operator for monitoring and logging
    registry             # (core) Private image registry exposed on localhost:32000
```
