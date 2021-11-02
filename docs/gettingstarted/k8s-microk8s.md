# MicroK8s installation for CentOS and Ubuntu

Snap tool is installed by default only on Ubuntu. If you use a different platform you need to install snap first.

For CentOS:
[Installing snap on CentOS | Snapcraft documentation](https://snapcraft.io/docs/installing-snap-on-centos)

For RedHat 7:
[Installing snap on RedHat | Snapcraft documentation](https://snapcraft.io/docs/installing-snap-on-red-hat)


Then microk8s must be installed with:

```bash
sudo snap install microk8s --classic
```

Add user to the microk8s group to no longer have to use the `sudo` command
```bash
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube
su - $USER
```
Check microk8s status
```bash
microk8s status --wait-ready
```
Install required microk8s dependencies to deploy SC4SNMP.

Note: when installing metallb you will be prompted for one or more IPs to use as entry points
Into the cluster. If your plan to enable clustering, this IP should not be assigned to the host (floats)
If you do not plan to cluster, then this IP may be the same IP as the host

Note2: a single IP in cidr format is x.x.x.x/32 use CIDR or range syntax
```bash
microk8s enable dns metallb rbac storage openebs helm3
```
Verify microk8s status
```bash
microk8s status --wait-ready
```