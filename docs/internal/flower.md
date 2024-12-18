# Celery admin panel (internal)

Main component of SC4SNMP architecture is Celery framework that can run background and periodic tasks (like polling and walk). It can be helpful to administrate Celery cluster using admin panel with [Flower](https://github.com/mher/flower).

## k8s

Just add `flower` section on `values.yaml`:

```
flower:
    enabled: true
    loadBalancerIP: x.x.x.x
```


## docker-compose

Just use `--profile debug` flag to run optional `flower` service together with SC4SNMP: `docker-compose --profile debug up`