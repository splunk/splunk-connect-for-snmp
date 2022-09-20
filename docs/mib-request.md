#MIB submission process

To achieve human-readable OIDs, the corresponding MIB files are necessary.
They are being stored in one of the components of SC4SNMP - the MIB server. 

The list of currently available MIBs is here:
[https://pysnmp.github.io/mibs/index.csv](https://pysnmp.github.io/mibs/index.csv)

An alternative way to check if the MIB you're interested in is being served is to check the link:
`https://pysnmp.github.io/mibs/asn1/@mib@` where `@mib@` is the name of MIB (for example `IF-MIB`). If the file 
is downloading, that means the MIB file exists in the mib server.

## Submit a new MIB file

In case you want to add a new MIB file to the MIB server, follow the steps:

1. Create a fork of the [https://github.com/pysnmp/mibs](https://github.com/pysnmp/mibs) repository 
   
2. Put MIB file/s under `src/vendor/@vendor_name@` where `@vendor_name@` is the name of the MIB file's vendor (in case
there is no directory of vendors you need, create it by yourself)
   
3. Create a pull request to a `main` branch
   
4. Name the pull request the following way: `feat: add @vendor_name@ MIB files`


An alternative way of adding MIBs to the MIB server is to create an issue on 
[https://github.com/pysnmp/mibs](https://github.com/pysnmp/mibs) repository, attaching the files and information about 
the vendor.

## Update your instance of SC4SNMP with the newest MIB server

Usually SC4SNMP is released with the newest version of MIB server every time the new MIB files were added.
But, if you want to use the newest MIB server right after its released, you can do it manually via the `values.yaml` file.

1. Append `mibserver` config to the values.yaml, with the `mibserver.image.tag` of a value of the newest `mibserver`, for ex.:
```
mibserver:
  image:
    tag: "1.14.5"
```
Check all of the MIB server releases [here](https://github.com/pysnmp/mibs/releases).

2. Run `microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace`

3. Restart worker-trap and worker-poller deployments:

```
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-worker-trap -n sc4snmp
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-worker-poller -n sc4snmp
```
