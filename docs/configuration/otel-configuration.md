# Otel configuration

Splunk OpenTelemetry Collector is a component that provides an option to send metrics to signalFx.
In order to use it, you must set `enabled` flag in `values.yaml` to `true`:
```yaml
otel:
  # otel must be enabled if you want to use signalFx
  enabled: true
```
Also you need to specify signalFx token and realm, so at the end otel element in `values.yaml` looks like this:
```yaml
otel:
  enabled: true
  signalfxToken: BCwaJ_Ands4Xh7Nrg
  signalfxRealm: us0
```
After executing 
`microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
`, 
the otel pod should be up and running:
```yaml
splunker@ip-10-202-13-233:~$ microk8s kubectl get pods -n sc4snmp
NAME                                                      READY   STATUS    RESTARTS   AGE
snmp-splunk-connect-for-snmp-worker-7496b66947-6hjhl      1/1     Running   0          32s
snmp-splunk-connect-for-snmp-worker-7496b66947-flcg7      1/1     Running   0          32s
snmp-splunk-connect-for-snmp-scheduler-846f9b4f69-4rxd8   1/1     Running   0          32s
snmp-mibserver-cdfccf586-cwz7h                            1/1     Running   0          32s
snmp-splunk-connect-for-snmp-inventory--1-dxz5d           1/1     Running   0          32s
snmp-splunk-connect-for-snmp-traps-6bbf57497b-v8d7l       1/1     Running   0          32s
snmp-splunk-connect-for-snmp-traps-6bbf57497b-nvxrz       1/1     Running   0          31s
snmp-splunk-connect-for-snmp-otel-59b89747f-kn6tf         1/1     Running   0          32s
snmp-rabbitmq-0                                           0/1     Running   0          31s
snmp-mongodb-9957b9f4d-f94hv                              2/2     Running   0          32s
```