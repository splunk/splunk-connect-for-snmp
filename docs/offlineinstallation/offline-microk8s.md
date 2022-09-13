# Offline Microk8s installation issues

Offline installation of Microk8s is described [here](https://microk8s.io/docs/install-alternatives#heading--offline), but
you may encounter some additional problems.

## Importing images

After running:

```
snap ack core_{microk8s_version}.assert
snap install core_{microk8s_version}.snap
```

You should check if the microk8s instance is healthy. Do it with:

```commandline
$ microk8s kubectl get pods -A
```

The output most probably will look like:
```
NAMESPACE      NAME                                       READY   STATUS     RESTARTS   AGE
kube-system    calico-kube-controllers-7c9c8dd885-fg8f2   0/1     Pending    0          14m
kube-system    calico-node-zg4c4                          0/1     Init:0/3   0          23s
```

You will need to download a few images and move them to the offline server. 
Also, the addons we enable through `microk8s enable {addon}` needs some images to work.
For example, `microk8s` version `3597` requires this images to work correctly:

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

NOTE: for other versions of `microk8s`, tags of images may differ. You need to monitor 

```commandline
microk8s kubectl get events -A
```

to see if `microk8s` fails to pull images, and then import anything it needs.

The healthy instance of microk8s, after running:

```commandline
microk8s enable storage
microk8s enable rbac
microk8s enable metrics-server
```

should look like this:

```
NAMESPACE      NAME                                       READY   STATUS                  RESTARTS   AGE
kube-system    calico-kube-controllers-7c9c8dd885-wxms9   1/1     Running                 0          3h21m
kube-system    calico-node-8cxsq                          1/1     Running                 0          3h21m
kube-system    hostpath-provisioner-f57964d5f-zs4sj       1/1     Running                 0          5m41s
kube-system    metrics-server-5f8f64cb86-x7k29            1/1     Running                 0          2m15s
```

## Installing helm3

The additional problem is the installation of `helm3` addon. You need to do a few things to make it work.

1. Check what is your server's platform with:

```commandline
dpkg --print-architecture
```

The output would be for ex.: `amd64`.
You need the platform to download the correct version of helm.

2. Download the helm package from `https://get.helm.sh/helm-v3.8.0-linux-{{arch}}.tar.gz` where `{{arch}}` should be 
replaced with the result from the previous command. Example: `https://get.helm.sh/helm-v3.8.0-linux-amd64.tar.gz`

3. Rename package to `helm.tar.gz` and send it to an offline lab.
4. Create `tmp` directory in `/var/snap/microk8s/current` and copy the package there:

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
