# Enabling IPv6 for SC4SNMP

Default installation of SC4SNMP does not support polling or receiving trap notifications from IPv6 addresses. 
To enable IPv6, follow instruction below.

## Docker

Older versions of Docker do not support IPv6 or have know issues with IPv6 configuration. 
To avoid any problem with configuring the network, it is recommended to use the latest version of Docker. 

To enable IPv6 for SC4SNMP, set `IPv6_ENABLED` variable to `true` in `.env` file.
The default subnet used for SC4SNMP network in docker is `fd02::/64`, this and other network configuration can be 
changed in the `docker-compose.yaml` file in `networks` section.

Default trap port for notifications for IPv6 is `2163`. You can change it to any other port if needed with `IPv6_TRAPS_PORT` parameter in `.env` file.
The IPv6 port and IPv4 port cannot be the same.

For more information about IPv6 networking in docker, you can check the [official Docker documentation](https://docs.docker.com/engine/daemon/ipv6/).