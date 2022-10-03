# OTEL and Splunk Observability Cloud configuration

Splunk OpenTelemetry Collector is a component that provides an option to send metrics to Splunk Observability Cloud.
In order to use it, you must set `enabled` flag in `values.yaml` to `true`:

```yaml
sim:
  # sim must be enabled if you want to use SignalFx
  enabled: true
```

## Token and realm

You need to specify Splunk Observability Cloud token and realm. There are two ways of configuring them:

1. Pass those in a plain text via `values.yaml` so at the end sim element looks like this:

```yaml
sim:
  enabled: true
  signalfxToken: BCwaJ_Ands4Xh7Nrg
  signalfxRealm: us0
```

2. Alternatively, create microk8s secret by yourself and pass its name in `values.yaml` file. Create secret:

```
microk8s kubectl create -n <namespace> secret generic <secretname> \
  --from-literal=signalfxToken=<signalfxToken> \
  --from-literal=signalfxRealm=<signalfxRealm>
```

Modify `sim.secret` section of `values.yaml`. Disable creation of the secret with `sim.secret.create` and provide the
`<secretname>` matching the one from the previous step. Pass it via `sim.secret.name`. For example, for `<secretname>`=`signalfx`
the `sim` section would look like:

```yaml
sim:
  secret:
    create: false
    name: signalfx
```

Note: After the initial installation, if you change `sim.signalfxToken` and/or `sim.signalfxRealm` and no `sim.secret.name` is given, 
the `sim` pod will sense the update by itself (after `helm3 upgrade` command) and trigger the recreation. But, when you edit secret created outside
of `values.yaml` (given by `sim.secret.name`), you need to roll out the deployment by yourself or delete the pod to update the data.


### Define annotations
In case you need to append some annotations to the `sim` service, you can do it by setting `sim.service.annotations`, for ex.:

```yaml
sim:
  service:
    annotations:
      annotation_key: annotation_value
```

## Verify the deployment

After executing `microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
`, the sim pod should be up and running:

```yaml
splunker@ip-10-202-13-233:~$ microk8s kubectl get pods -n sc4snmp
NAME                                                      READY   STATUS    RESTARTS   AGE
snmp-splunk-connect-for-snmp-scheduler-7ddbc8d75-bljsj        1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-poller-57cd8f4665-9z9vx   1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-sender-5c44cbb9c5-ppmb5   1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-trap-549766d4-28qzh       1/1     Running   0          133m
snmp-mibserver-7f879c5b7c-hz9tz                               1/1     Running   0          133m
snmp-mongodb-869cc8586f-vvr9f                                 2/2     Running   0          133m
snmp-redis-master-0                                           1/1     Running   0          133m
snmp-splunk-connect-for-snmp-trap-78759bfc8b-79m6d            1/1     Running   0          99m
snmp-splunk-connect-for-snmp-sim-59b89747f-kn6tf              1/1     Running   0          32s
```
