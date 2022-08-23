# Otel configuration

Splunk OpenTelemetry Collector is a component that provides an option to send metrics to SignalFx.
In order to use it, you must set `enabled` flag in `values.yaml` to `true`:

```yaml
sim:
  # sim must be enabled if you want to use SignalFx
  enabled: true
```

Also, you need to specify SignalFx token and realm, so at the end sim element in `values.yaml` looks like this:

```yaml
sim:
  enabled: true
  signalfxToken: BCwaJ_Ands4Xh7Nrg
  signalfxRealm: us0
```

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
