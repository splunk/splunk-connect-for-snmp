# MIB submission process

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
Check all the MIB server releases [here](https://github.com/pysnmp/mibs/releases).

2. Run `microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace`

3. Restart worker-trap and worker-poller deployments:

```
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-worker-trap -n sc4snmp
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-worker-poller -n sc4snmp
```

## Beta: use MIB server with local MIBs

From the `1.15.0` version of the MIB server, there is a way to use local MIB files. This may be useful when your MIB 
files are proprietary, or you use SC4SNMP offline - this way you can update necessary MIBs by yourself, without a need
of going through the MIB request procedure.

In order to add your MIB files to the MIB server in standalone SC4SNMP installation:

1. Create/Choose a directory on the machine where SC4SNMP is installed. For example: `/home/user/local_mibs`.
2. Create vendor directories inside. For example, if you have MIB files from `VENDOR1` and `VENDOR2`, create
`/home/user/local_mibs/VENDOR1` and `/home/user/local_mibs/VENDOR2` and put files inside accordingly. Putting wrong 
vendor names won't make compilation fail, this is more for the logging purposes. Segregating your files will make 
troubleshooting easier.
3.  Add following config to the `values.yaml`:

```yaml
localMibs:
  pathToMibs: "/home/user/local_mibs"
```

To verify if the process of compilation was completed successfully, check the mibserver logs with:

```bash
microk8s kubectl deployments/snmp-mibserver
```

It creates a Kubernetes pvc with MIB files inside and maps it to MIB server pod.
Also, you can change the storageClass and size of persistence according to the `mibserver` schema: [check here](https://github.com/pysnmp/mibs/blob/main/charts/mibserver/values.yaml).
The default persistence size is 3 Gibibytes, so consider reducing it to the amount you actually need.
Whenever you add new MIB files, rollout restart MIB server pods to compile them again:

```bash
microk8s kubectl rollout restart deployment snmp-mibserver -n sc4snmp
```

NOTE: In case of multi-node Kubernetes installation, create pvc beforehand, copy files onto it and add to the MIB server
using `persistence.existingClaim`. If you go with `localMibs.pathToMibs` solution in case of multi-node installation
(with `nodeSelector` set up to schedule MIB server pods on the same node where the MIB files are),
it will work - but when the Node with hostPath mapped fails, you'll use access to the MIB files on another node.

