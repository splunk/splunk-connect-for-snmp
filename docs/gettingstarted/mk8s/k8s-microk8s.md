# Splunk Connect for SNMP using MicroK8s

Using this deployment option any Linux deployment of Microk8s can be used to support SC4SNMP given the following requirements are met. The minimum requirements below are suitable for proof of value and small installations, actual requirements will differ.

Single node minimum
* 4 cores
* 8 GB of memory per node
* 50 GB mounted as /

Three node minimum per node
* 4 cores
* 8 GB of memory per node
* 50 GB mounted /

# MicroK8s installation on Ubuntu

The following quick start guidance is based on Ubuntu 20.04LTS with MicroK8s with internet access. Other deployment options
may be found in the MicroK8s [documentation](https://microk8s.io/docs) including offline and with proxy. 

## Install MicroK8s using Snap

```bash
sudo snap install microk8s --classic
```

Add user to the microk8s group to no longer have to use the `sudo` command
```bash
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube
su - $USER
```

Wait for Installation of Mk8S to complete
```bash
microk8s status --wait-ready
```

## Add additional nodes (optional)

* Repeat the steps above for each additional node (minimum total 3)
* On the first node issue the following, this will return joining instructions

```bash
microk8s add-node
```

* On each additional node use the output from the command above

## Install basic services required for sc4snmp

The following commands can be issued from any one node in a cluster

```bash
sudo systemctl enable iscsid
microk8s enable rbac storage openebs helm3
microk8s status --wait-ready
```

Install the DNS server for mk8s and configure the forwarding DNS servers replace the IP addressed below (opendns) from
allowed values for your network

```bash
microk8s enable dns:208.67.222.222,208.67.220.220
microk8s status --wait-ready
```

## Install Metallb

Note: when installing metallb you will be prompted for one or more IPs to use as entry points
Into the cluster. If your plan to enable clustering, this IP should not be assigned to the host (floats)
If you do not plan to cluster, then this IP may be the same IP as the host

Note2: a single IP in cidr format is x.x.x.x/32 use CIDR or range syntax for single server installations this can be
the same as the primary ip.

```bash
microk8s enable metallb
microk8s status --wait-ready
```
