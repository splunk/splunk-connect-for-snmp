# Enabling IPv6 for SC4SNMP

Default installation of SC4SNMP does not support polling or receiving trap notifications from IPv6 addresses. 
To enable IPv6, follow instruction below.

## Docker

Older versions of Docker do not support IPv6 or have known issues with IPv6 configuration. 
To avoid problems with the network, use the latest version of Docker. 

To enable IPv6 for SC4SNMP:

1. Set `IPv6_ENABLED=true` in your `.env` file.
2. Set **`COREDNS_ADDRESS_IPv6`** to an IPv6 address that lies **inside** your `IPAM_SUBNET_IPv6`.  
   If this is unset or points outside the configured subnet, Docker can fail with errors like  
   `no configured subnet contains IP address fd02::...`.

   With the default subnet `fd02::/64` and gateway `fd02::1`, use an address from that range, for example:

   ```bash
   COREDNS_ADDRESS_IPv6=fd02::1
   ```

   If you use a different `IPAM_SUBNET_IPv6` / `IPAM_GATEWAY_IPv6`, pick an address from that subnet (e.g. the gateway or another host address).

3. The default IPv6 subnet is `fd02::/64`; you can change it in `.env` under the **Network configuration** section (`IPAM_SUBNET_IPv6`, `IPAM_GATEWAY_IPv6`).

If you configure more than one IPv4 and IPv6 subnet in IPAM, edit the `networks` section of `docker-compose.yaml` accordingly.

For more information about IPv6 networking in Docker, see the [official Docker documentation](https://docs.docker.com/engine/daemon/ipv6/).