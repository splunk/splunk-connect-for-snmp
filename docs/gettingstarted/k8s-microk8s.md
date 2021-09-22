# MicroK8s installation on Ubuntu

We need to have a normal install of kubectl because of operator scripts
```bash
sudo snap install kubectl --classic
sudo snap install microk8s --classic
```

Add user to microk8s group to not to use `sudo` anymore
```bash
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube
su - $USER
```
Check microk8s status
```bash
microk8s status --wait-ready
```
Install microk8s dependencies necessary to deploy SC4SNMP.

Note: when installing metallb you will be prompted for one or more IPs to used as entry points
Into the cluster if your plan to enable clustering this IP should not be assigned to the host (floats)
If you do not plan to cluster then this IP may be the same IP as the host

Note2: a single IP in cidr format is x.x.x.x/32 use CIDR or range syntax
```bash
microk8s enable dns metallb rbac storage openebs helm3
microk8s status --wait-ready
```