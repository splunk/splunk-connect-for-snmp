# Enabling IPv6 for SC4SNMP

Default installation of SC4SNMP does not support polling or receiving trap notifications from IPv6 addresses. 
To enable IPv6, follow instruction below.

## Docker

Older versions of Docker do not support IPv6 or have know issues with IPv6 configuration. 
To avoid any problem with configuring the network, it is recommended to use the latest version of Docker. 

To enable IPv6 for SC4SNMP, set `IPv6_ENABLED` variable to `true` in `.env` file.
The default subnet used for SC4SNMP network in docker is `fd02::/64`, this configuration can be changed in `.env` file under `Network configuration` section.
In case of configuring more than one IPv4 and IPv6 subnet in IPAM, `networks` section of `docker-compose.yaml` should be edited.

For more information about IPv6 networking in docker, you can check the [official Docker documentation](https://docs.docker.com/engine/daemon/ipv6/).