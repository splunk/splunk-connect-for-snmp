# Offline installation

In order to install SC4SNMP using docker compose in the offline environment, several docker images must be imported. 
These images can be found in `.env` file:

- `SC4SNMP_IMAGE` and `SC4SNMP_TAG` in `Deployment configuration` section
- `COREDNS_IMAGE` and `COREDNS_TAG` in `Dependencies images` section
- `MIBSERVER_IMAGE` and `MIBSERVER_TAG` in `Dependencies images` section
- `REDIS_IMAGE` and `REDIS_TAG` in `Dependencies images` section
- `MONGO_IMAGE` and `MONGO_TAG` in `Dependencies images` section

Following images must be downloaded in the online environment, saved to `.tar` archive and moved to the offline environment.

## Steps required to install necessary images

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

They must be downloaded in the online environment by following commands:

```shell
docker pull ghcr.io/splunk/splunk-connect-for-snmp/container:main
docker pull ghcr.io/pysnmp/mibs/container:main
docker pull bitnamilegacy/redis:7.2.1-debian-11-r0
docker pull bitnamilegacy/mongodb:7.0.14-debian-12-r8
docker pull  coredns/coredns:1.11.1
```

Next step is to save them to `sc4snmp_offline_images.tar` archive:
```shell
docker save ghcr.io/splunk/splunk-connect-for-snmp/container:main \
ghcr.io/pysnmp/mibs/container:main \
bitnamilegacy/redis:7.2.1-debian-11-r0 \
coredns/coredns:1.11.1 \
bitnamilegacy/mongodb:7.0.14-debian-12-r8 > sc4snmp_offline.tar 
```

After moving `sc4snmp_offline.tar` archive to the offline environment, images can be loaded to docker:
```shell
docker load --input sc4snmp_offline.tar.tar
```