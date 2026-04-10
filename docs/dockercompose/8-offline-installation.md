# Offline installation

!!! note
    If your target host has no internet access, complete this page **before** running `docker compose up`. The image download must be performed on a separate machine that has internet access. Once the images are loaded on the target host, continue with the normal setup flow.

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

REDIS_IMAGE=docker.io/redis
REDIS_TAG=latest

MONGO_IMAGE=docker.io/mongodb
MONGO_TAG=latest
```

They must be downloaded in the online environment by following commands:

```shell
docker pull ghcr.io/splunk/splunk-connect-for-snmp/container:latest
docker pull coredns/coredns:1.11.1
docker pull ghcr.io/pysnmp/mibs/container:latest
docker pull docker.io/redis:latest
docker pull docker.io/mongodb:latest
```

Next step is to save them to `sc4snmp_offline_images.tar` archive:
```shell
docker save ghcr.io/splunk/splunk-connect-for-snmp/container:latest \
coredns/coredns:1.11.1 \
ghcr.io/pysnmp/mibs/container:latest \
docker.io/redis:latest \
docker.io/mongodb:latest > sc4snmp_offline_images.tar
```

After moving `sc4snmp_offline_images.tar` archive to the offline environment, images can be loaded to docker:
```shell
docker load --input sc4snmp_offline_images.tar
```