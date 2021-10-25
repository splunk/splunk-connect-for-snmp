# MicroK8s installation for RHEL

Enable iSCSI API 
```yaml
sudo yum -y update
sudo setenforce 0
sudo yum install -y iscsi-initiator-utils git
sudo systemctl enable iscsid
```

Install brew and some handfull tools:
```yaml
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"'>> /home/ec2-user/.bash_profile
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
```

```yaml
brew install helm kubectl kubectx k9s nano
```

Use [kurl.sh](kurl.sh) to prepare url for a microk8s installation. Use:
1.  Kubernetes version: 1.20.x ( or newer) 
2. CRI: Containerd ( lates)
3. CNI: Weave (latest)
4. PVC: Provisioner  openEBS (2.6.0) 

Url to install k8s example:
```yaml
curl https://kurl.sh/bb01dee | sudo bash
```

After the installation run:
```yaml
echo unset KUBECONFIG >> ~/.bash_profile
bash -l
echo 'alias k=kubectl' >>~/.bashrc
```
Refresh `.bashrc`:
```yaml
. ~/.bashrc
```
Check if the installations are running:
```yaml
k get all -A
```
The response for the above command should look like this:
```yaml
[ec2-user@ip-172-31-16-56 ~]$ k get all -A
NAMESPACE     NAME                                                       READY   STATUS    RESTARTS   AGE
kube-system   pod/coredns-74ff55c5b-lkpxc                                1/1     Running   0          10m
kube-system   pod/coredns-74ff55c5b-sr6hl                                1/1     Running   0          10m
kube-system   pod/etcd-ip-172-31-16-56.ec2.internal                      1/1     Running   0          10m
kube-system   pod/kube-apiserver-ip-172-31-16-56.ec2.internal            1/1     Running   0          10m
kube-system   pod/kube-controller-manager-ip-172-31-16-56.ec2.internal   1/1     Running   0          10m
kube-system   pod/kube-proxy-spb46                                       1/1     Running   0          10m
kube-system   pod/kube-scheduler-ip-172-31-16-56.ec2.internal            1/1     Running   0          10m
kube-system   pod/weave-net-rkbdz                                        2/2     Running   1          10m

NAMESPACE     NAME                 TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE
default       service/kubernetes   ClusterIP   10.96.0.1    <none>        443/TCP                  11m
kube-system   service/kube-dns     ClusterIP   10.96.0.10   <none>        53/UDP,53/TCP,9153/TCP   10m

NAMESPACE     NAME                        DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR            AGE
kube-system   daemonset.apps/kube-proxy   1         1         1       1            1           kubernetes.io/os=linux   10m
kube-system   daemonset.apps/weave-net    1         1         1       1            1           <none>                   10m

NAMESPACE     NAME                      READY   UP-TO-DATE   AVAILABLE   AGE
kube-system   deployment.apps/coredns   2/2     2            2           10m

NAMESPACE     NAME                                DESIRED   CURRENT   READY   AGE
kube-system   replicaset.apps/coredns-74ff55c5b   2         2         2       10m
```

Note that you'll use `helm` commands with `helm` and not `microk8s helm`.

Also, for SNMP install you need to create PV for mongodb and rabbitmq. To do so, please 
create two files:
```yaml
touch rabbitmq_pvc.yaml
touch mongodb_pvc.yaml
```
The content of `rabbitmq_pvc.yaml` should be:
```yaml
kind: PersistentVolume
apiVersion: v1
metadata:
 name: pv1
 labels:
   type: local
   app: app
spec:
 capacity:
   storage: 15Gi
 accessModes:
   - ReadWriteOnce
 hostPath:
   path: "/home/ec2-user/data/pv1"
```
The content of `mongodb_pvc.yaml` should be:
```yaml
kind: PersistentVolume
apiVersion: v1
metadata:
 name: pv2
 labels:
   type: local
   app: app
spec:
 capacity:
   storage: 15Gi
 accessModes:
   - ReadWriteOnce
 hostPath:
   path: "/home/ec2-user/data/pv2"
```
Where directory in `hostPath.path` `ec2-user` should refer to yours account name.

Create directory trees:
```yaml
mkdir -p /home/ec2-user/data/pv1 /home/ec2-user/data/pv2
```
Where `ec2-user` is yours account name.

Move files to directories:
```yaml
mv mongodb_pvc.yaml /home/ec2-user/data/pv1
mv rabbitmq_pvc.yaml /home/ec2-user/data/pv2
```

Change directories ownership:
```yaml
sudo chown -R 1001:1001 ~/data
```
