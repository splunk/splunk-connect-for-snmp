# Offline installation

In order to install SC4SNMP using docker compose in the offline environment, several docker images must be imported to 
docker. These images can be found in `.env` file:

- `SC4SNMP_IMAGE` and `SC4SNMP_TAG` in `Deployment configuration` section
- `COREDNS_IMAGE` and `COREDNS_TAG` in `Dependencies images` section
- `MIBSERVER_IMAGE` and `MIBSERVER_TAG` in `Dependencies images` section
- `REDIS_IMAGE` and `REDIS_TAG` in `Dependencies images` section
- `MONGO_IMAGE` and `MONGO_TAG` in `Dependencies images` section

These images must be downloaded in the online environment, saved to `.tar` archive and moved to the offline environment.

## Steps to install necessary images

Suppose that `.env` contains the following images:

```.env
SC4SNMP_IMAGE=ghcr.io/splunk/splunk-connect-for-snmp/container
SC4SNMP_TAG=latest

COREDNS_IMAGE=coredns/coredns
COREDNS_TAG=1.11.1

MIBSERVER_IMAGE=ghcr.io/pysnmp/mibs/container
MIBSERVER_TAG=latest

REDIS_IMAGE=docker.io/bitnami/redis
REDIS_TAG=7.2.1-debian-11-r0

MONGO_IMAGE=docker.io/bitnami/mongodb
MONGO_TAG=6.0.9-debian-11-r5
```

These images must be downloaded in the online environment:

```shell
docker pull ghcr.io/splunk/splunk-connect-for-snmp/container:latest
docker pull coredns/coredns:1.11.1
docker pull ghcr.io/pysnmp/mibs/container:latest
docker pull docker.io/bitnami/redis:7.2.1-debian-11-r0
docker pull docker.io/bitnami/mongodb:6.0.9-debian-11-r5
```

Next step is to save these images to `sc4snmp_offline_images.tar` archive:
```shell
docker save ghcr.io/splunk/splunk-connect-for-snmp/container:latest \
coredns/coredns:1.11.1 \
ghcr.io/pysnmp/mibs/container:latest \
docker.io/bitnami/redis:7.2.1-debian-11-r0 \
docker.io/bitnami/mongodb:6.0.9-debian-11-r5 > sc4snmp_offline_images.tar
```

After moving `sc4snmp_offline_images.tar` archive to the offline environment, images can be loaded to docker:
```shell
docker load --input sc4snmp_offline_images.tar
```