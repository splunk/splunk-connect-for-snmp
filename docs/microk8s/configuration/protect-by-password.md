# Protect Mongo and Redis by password

## Using secrets

### Redis

Create secret:

```
microk8s kubectl create secret generic redis-auth-secret \
  --from-literal=redis-password=your_password -n sc4snmp
```

Reference on this secret in  `values.yaml`:

```
redis:
    auth:
        enabled: true
        existingSecret: "redis-auth-secret"
```

Redeploy SC4SNMP

### Mongo

Create secret:

```
microk8s kubectl create secret generic mongodb-auth-secret \
  --from-literal=mongodb-root-password=your_password -n sc4snmp
```

Reference on this secret in  `values.yaml`:

```

mongodb:
    auth:
        enabled: true
        existingSecret: "mongodb-auth-secret"
```

Redeploy SC4SNMP

!!! Warning
    Mongodb participating in migration jobs, would be good to update password manually before redeploy using `mongosh` CLI.


## Using password

### Redis

Set password in  `values.yaml`:

```
redis:
    auth:
        enabled: true
        password: "redis-pass"
```

Redeploy SC4SNMP

### Mongo

Set password in  `values.yaml`:

```
mongodb:
    auth:
        enabled: true
        rootPassword: "mongodb-pass"
```

Redeploy SC4SNMP

!!! Warning
    Mongodb participating in migration jobs, would be good to update password manually before redeploy using `mongosh` CLI.
