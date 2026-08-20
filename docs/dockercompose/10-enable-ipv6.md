# Enabling IPv6 for SC4SNMP

Docker Compose uses `IPv6_ENABLED` to enable IPv6 for the SC4SNMP network, polling, traps, MongoDB, and the MIB server. The default value is `false`.

Older versions of Docker do not support IPv6 or have known issues with IPv6 configuration.
To avoid problems with the network, use the latest version of Docker.
Install the latest version of Docker Compose as well.

## Configure IPv6

1. Set `IPv6_ENABLED=true` in the `.env` file:

    ```text
    IPv6_ENABLED=true
    ```

2. `COREDNS_ADDRESS_IPv6` must be a unique address inside `IPAM_SUBNET_IPv6` and must not match the gateway.

    If the value is empty or outside the configured subnet, Docker can fail with an error such as `no configured subnet contains IP address fd02::...`.

    With the default subnet `fd02::/64` and gateway `fd02::1`, use an available address from that subnet, for example:

    ```text
    COREDNS_ADDRESS_IPv6=fd02::53
    ```

3. The default IPv6 subnet and gateway are configured in the **Network configuration** section of `docker_compose/.env`:

    ```text
    IPAM_SUBNET_IPv6=fd02::/64
    IPAM_GATEWAY_IPv6=fd02::1
    ```

    You can change these values for your environment. If you use a different subnet or gateway, select a unique `COREDNS_ADDRESS_IPv6` from that subnet that is not the gateway.

4. If you configure more than one IPv4 or IPv6 subnet in IPAM, update the `networks` section of `docker-compose.yaml` accordingly.

For more information about IPv6 networking in Docker, see the [Docker documentation](https://docs.docker.com/engine/daemon/ipv6/).