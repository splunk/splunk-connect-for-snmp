# Celery admin panel (internal)

Main component of SC4SNMP architecture is Celery framworks that can run background and periodic tasks (like polling and walk). By this reason super helpfull might be administrate Celery cluster using admin panel and we using for that [Flower](https://github.com/mher/flower).

## k8s

Just add `flower` section on `values.yaml`:

```
flower:
    enabled: true
    loadBalancerIP: x.x.x.x
```


## docker-compose

Just use `--profile debug` flag to run optional `flower` service together with SC4SNMP: `docker-compose --profile debug up`