## Docker commands

For full display of docker commands and their usage can be found at [docker documentation](https://docs.docker.com/reference/cli/docker/). 
Below are the most common commands used to troubleshoot issues with SC4SNMP. 

### Common flags
The following are some common flags that can be used with the `docker` commands:

- `-a` flag is used to list all resources

For more flags and options, you can refer to the [docker documentation](https://docs.docker.com/reference/cli/docker/).

### Accessing logs in docker

The instruction on how to set up and access the logs can be found in [SC4SNMP logs](configuring-logs.md#accessing-logs-in-docker) 

### The ls and ps commands

The `ls` or `ps` command are used to list the resources in docker. The following are the example of resources that 
can be listed using the commands:

```
docker compose ls
docker network ls
docker image ls
docker container ls
docker ps
docker ps -a
docker compose ps <service_name/id>
```

### The inspect command

The `inspect` command is used to get detailed information about the resources in docker. The following are the 
example of resources that can be inspected:

```
docker inspect --type <resource_type> <resource_name/id>
docker network inspect <resource_name/id>
docker image inspect <resource_name/id>
```

### The logs command

The `logs` command is used to get the logs of the resources in docker. 
The following are some examples of how to use the `logs` command:

```
docker logs <container_name/id>
docker compose logs <service_name/id>
```

### The exec command

The `exec` command is used to execute a command in a running container. The following is an example of how to 
use the `exec` command:

```
docker exec -it <container_name/id> sh -c <command>
```

### The stats command

The `stats` command is used to display the live resource usage statistics of a container. The following are some
examples of how to use the `stats` command:

```
docker stats
docker stats <container_name/id>
```

## Examples of command usage

### Check secret for snmp v3

One of the issues related to snmp v3 can be incorrectly configured secrets in docker. 
Below you can find the instruction to check the existing secrets.

To check the existing secrets:
```
~$ docker exec -it docker_compose-worker-poller-1 sh -c "ls secrets/snmpv3"
my_secret
```
To get more details about one secret you can use command:
```
~$ docker exec -it docker_compose-worker-poller-1 sh -c "ls secrets/snmpv3/my_secret"
authKey  authProtocol  contextEngineId  privKey  privProtocol  userName
```
Replace **my_secret** with the name of the secret you want to check and **docker_compose-worker-poller-1** with the name of the container.

To see the configured details of the secret: 
```
~$ docker exec -it docker_compose-worker-poller-1 sh -c 'cd secrets/snmpv3/my_secret && for file in *; do echo "$file= $(cat $file)"; done'
authKey= admin1234
authProtocol= SHA
contextEngineId= 80003a8c04
privKey= admin1234
privProtocol= AES
userName= r-wuser
```
Replace **my_secret** with the name of the secret you want to check and **docker_compose-worker-poller-1** with the name of the container.

### Check containers health
To check the health of the containers, you can use the `ps` command to look at the `STATUS`. 
If the `STATUS` is not `Up` or the containers restarts continuously, then there might be an issue with it. 
You can also use the `inspect` command to get more detailed information about the container and see if there are any 
errors or warnings in the `state` or use `logs` command to see the logs of the container.

### Check resource usage
To check the resource usage of the containers, you can use the `stats` command. 
With this command, you can see the CPU and memory usage of the containers in real-time and compare it with the ones 
assigned in `resources` section in the configuration yaml.
If they are close to each other you might consider increasing the resources assigned.

### Check network
Checking the network configuration can be useful when enabling the dual-stack for SC4SNMP.


One of useful commands to check the network configuration is:
```
~$ docker network ls
NETWORK ID     NAME              DRIVER    SCOPE
7e46b3818089   bridge            bridge    local
1401c370b8f4   docker_gwbridge   bridge    local
12ca971fa954   host              host      local
rssypcqbwarx   ingress           overlay   swarm
b6c176852f41   none              null      local
978e06ffcd4a   sc4snmp_network   bridge    local
```
This command is showing all the network configured in the docker. The network created for sc4snmp by default is named `sc4snmp_network`.

To see details of configured network use:
```
~$ docker network inspect sc4snmp_network
[
    {
        "Name": "sc4snmp_network",
        "Id": "978e06ffcd4a49de5cd78a038050530342a029b1b1a1f1967254f701ae5ff1a0",
        "Created": "2024-10-10T11:38:01.627727666Z",
        "Scope": "local",
        "Driver": "bridge",
        "EnableIPv6": false,
        "IPAM": {
            "Driver": "default",
            "Options": null,
            "Config": [
                {
                    "Subnet": "172.28.0.0/16",
                    "Gateway": "172.28.0.1"
                },
                {
                    "Subnet": "fd02::/64",
                    "Gateway": "fd02::1"
                }
            ]
        },
        "Internal": false,
        "Attachable": false,
        "Ingress": false,
        "ConfigFrom": {
            "Network": ""
        },
        "ConfigOnly": false,
        "Containers": {
            "231b21c24bd722d684349174cc5aebf40cf294617aa98741a4af1269ed930fcc": {
                "Name": "docker_compose-worker-poller-1",
                "EndpointID": "0195750f0539535615ebdb24d8ee7eb967d31ca3c86a0d5d4b5c21f907cb61a0",
                "MacAddress": "02:42:ac:1c:00:0b",
                "IPv4Address": "172.28.0.11/16",
                "IPv6Address": ""
            },
            "25479e15afee663a7d0ad7b97f734f65d35672c49e9610f9e0406975d616e584": {
                "Name": "snmp-mibserver",
                "EndpointID": "68a27a27fc5acc7b1350cb5f073abf9218f1c0fa4ede5f037a67fdcce46ec91b",
                "MacAddress": "02:42:ac:1c:00:03",
                "IPv4Address": "172.28.0.3/16",
                "IPv6Address": ""
            },
            "35f2bdd191898f7186a0c00dbffa5cc700e9d72e07efb6f3b341c6b8ce14d5f5": {
                "Name": "coredns",
                "EndpointID": "0c76c32e9b9b1dd033141332dee9a8f954c4a83ea5344ee4c93af057d2523d9a",
                "MacAddress": "02:42:ac:1c:00:ff",
                "IPv4Address": "172.28.0.255/16",
                "IPv6Address": ""
            },
            "3dc9f0d293578a7aca1b6b33cc3557f82262849e2be488a9cda729152854b9a9": {
                "Name": "docker_compose-worker-trap-2",
                "EndpointID": "88fc3701b04803d6317ad5d23031f880ec96c2206185c1994184580932ed5865",
                "MacAddress": "02:42:ac:1c:00:0c",
                "IPv4Address": "172.28.0.12/16",
                "IPv6Address": ""
            },
            "43c5893f2688da599dd0331a328937b19a62496f4eb06eaa40a9cad8e879c567": {
                "Name": "redis",
                "EndpointID": "c1c91866f67ed76d83e78a6b11e5001b0cf65107df3b7d4733373653be7f5e6a",
                "MacAddress": "02:42:ac:1c:00:04",
                "IPv4Address": "172.28.0.4/16",
                "IPv6Address": ""
            },
            "52fa13245149422e559d4ff7a2f6c929b46ebfffdbafb52efcaade26e861128e": {
                "Name": "sc4snmp-traps",
                "EndpointID": "926187b2e4c3e9753dd260e8fa9db2745c20ed6c87f73f2df4870f0cb3be1511",
                "MacAddress": "02:42:ac:1c:00:05",
                "IPv4Address": "172.28.0.5/16",
                "IPv6Address": ""
            },
            "68813263e9d6a74e70061f85f9044ec334cce9aee364804566b4823e6960ae04": {
                "Name": "docker_compose-worker-poller-2",
                "EndpointID": "06d883d0ee21926be450b8c0adf4c31da7f13ceaa70dba3d0830608d5c192b2d",
                "MacAddress": "02:42:ac:1c:00:08",
                "IPv4Address": "172.28.0.8/16",
                "IPv6Address": ""
            },
            "78b04a7cd5c9ec1d3aaf014fd10c0ad89d401ad63093052a26111066198639af": {
                "Name": "docker_compose-worker-sender-1",
                "EndpointID": "0e9c84d4e7d1ce6362bba33c41161086a2de4623161a0ef34ce746d9983a4be7",
                "MacAddress": "02:42:ac:1c:00:09",
                "IPv4Address": "172.28.0.9/16",
                "IPv6Address": ""
            },
            "a34c808997eb56ab5c4043be3d9cd5ceb86f5b0f481b7bd51009eace9ff12965": {
                "Name": "mongo",
                "EndpointID": "992f5fd3eed5e646c250d61cc1d3c94bf43dc2ad0621f0044dbfd718d24325d5",
                "MacAddress": "02:42:ac:1c:00:02",
                "IPv4Address": "172.28.0.2/16",
                "IPv6Address": ""
            },
            "b197d6b5ac9a0a69d8afb9a613006e916eacffd4c3a2c71e3ee8db927c307457": {
                "Name": "sc4snmp-scheduler",
                "EndpointID": "3753aec5d05a24683fb04f29284297444957e466fd5d5ffc6f40f8b58d04c443",
                "MacAddress": "02:42:ac:1c:00:07",
                "IPv4Address": "172.28.0.7/16",
                "IPv6Address": ""
            },
            "b52716b229679ec14fcc3236eee4e64f6f2b2c257889979ebb7d4b091c8cd0db": {
                "Name": "docker_compose-worker-trap-1",
                "EndpointID": "f1066da76315c595b6bd606e2f0437b16ec33b2c16e3f659682910e6a79ecb24",
                "MacAddress": "02:42:ac:1c:00:0a",
                "IPv4Address": "172.28.0.10/16",
                "IPv6Address": ""
            }
        },
        "Options": {},
        "Labels": {
            "com.docker.compose.network": "sc4snmp_network",
            "com.docker.compose.project": "docker_compose",
            "com.docker.compose.version": "2.29.7"
        }
    }
]
```

One section of the command is showing the `containers` assigned to that network with their ipv4 and ipv6 addresses.
The commands also shows if the ipv6 is enabled and what subnets are assigned to the network.

