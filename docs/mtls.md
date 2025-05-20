# mTLS


## Intro

!!! info
    mTLS encryption support is available beginning with Splunk 10

Mutual TLS (mTLS) is an extension of the standard TLS protocol that provides mutual authentication between a client and a server. While TLS typically ensures that the client can verify the server’s identity, mTLS requires both parties to verify each other’s identities using digital certificates. In our case client is SC4SNMP and server is Splunk.


## How to setup Splunk

!!! info
    if you using Splunk Cloud please contact to administrator to setup mTLS

1. Ensure that client and server mTLS certificates are already prepared

2. Update `$SPLUNK_HOME/etc/system/local/server.conf`:

```
[sslConfig]
requireClientCert = true
[kvstore]
hostnameOption = fullyqualifiedname
```

3. Update `$SPLUNK_HOME/etc/system/local/web.conf`:

```
[settings]
sslPassword = password
sslRootCAPath = cacert.pem
enableSplunkWebSSL = true
```

4. Restart Splunk:

```
$SPLUNK_HOME/bin/splunk restart
```

## How to setup SC4SNMP

/// tab | microk8s
1. Add your **client** mTLS certificates to secrets:

```
microk8s kubectl create secret generic mtls -n sc4snmp \
  --from-file=client.crt=./client.crt \
  --from-file=client.key=./client.key \
  --from-file=cacert.pem=./cacert.pem
```

2. Use https protocol to communicate with Splunk. To enforce this, set the `splunk.protocol` variable in the configuration file values.yaml:

```
splunk:
    protocol: "https"
```

3. Add `mtls` section and provide your secret with certificates inside. To do this, update the `values.yaml` file under the splunk section as shown below:

```
splunk:
    mtls:
        enabled: true
        secretRef: "mtls"
```

4. Redeploy SC4SNMP
///

/// tab | docker-compose
1. Add your **client** mTLS certificates to secrets. To do this, update the docker-compose.yaml file by adding the following section at the end:

```
secrets:
  cert:
    file: client.crt
  key:
    file: client.key
  ca:
    file: cacert.pem
```

2. To provide the certificates to the `worker-sender` service, update its definition in the `docker-compose.yaml` file as shown below:

```
worker-sender:
    environment:
        SPLUNK_HEC_MTLS_CLIENT_CERT: /run/secrets/cert
        SPLUNK_HEC_MTLS_CLIENT_KEY: /run/secrets/key
        SPLUNK_HEC_MTLS_CA_CERT: /run/secrets/ca
    secrets:
        - cert
        - key
        - ca
```
3. Use https protocol to communicate with Splunk. To enforce this, set the `SPLUNK_HEC_PROTOCOL` variable in the configuration file `.env`:

```
SPLUNK_HEC_PROTOCOL=https
```

4. Redeploy SC4SNMP
///


## Troubleshooting

1. Double-check that the mTLS certificates you are using are valid. To do this, send a test log message using `curl` in verbose mode, which can help identify any issues with the certificates:

```
curl -k https://${HEC_URL} \
  -H "Authorization: Splunk ${HEC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"event": "Hello", "sourcetype": "manual", "host": "myhost", "source": "myapp"}' \
  --cert client.crt \
  --key client.key \
  --cacert cacert.pem \
  -vvv
```

2. Check logs of `worker-sender`. Refer to the instructions on how to configure logs for `kubernetes` or `docker` deployment.


