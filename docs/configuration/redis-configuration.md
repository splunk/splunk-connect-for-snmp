#Redis configuration

Recently, RabbitMQ was replaced with Redis as a queue service and periodic task database. The reason for that was to increase SC4SNMP performance and protect against bottlenecks.

Redis is a service with is used for both managing periodic tasks and as a queue service for SC4SNMP. It is queuing tasks like SNMP Walk and Poll.  

### Redis configuration file

Redis configuration is kept in `values.yaml` file in section `redis`.
`values.yaml` is being used during the installation process for configuring Kubernetes values.

In case of need to change it please follow documentation: [Redis on Kubernetes](https://github.com/bitnami/charts/tree/master/bitnami/redis) 
