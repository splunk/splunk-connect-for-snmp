#Redis configuration

Recently, RabbitMQ was replaced with Redis as a queue service and periodic task database. The reason for this is to increase SC4SNMP performance and protect against bottlenecks.

Redis both manages periodic tasks and queues the SC4SNMP service. It queues tasks like SNMP Walk and Poll.  

### Redis configuration file

Redis configuration is kept in the `values.yaml` file in the `redis` section.
`values.yaml` is being used during the installation process for configuring Kubernetes values.

To edit the configuration, see: [Redis on Kubernetes](https://github.com/bitnami/charts/tree/master/bitnami/redis) 
