# MIB submission process

To achieve human-readable OIDs, the corresponding MIB files are necessary.
They are stored in the MIB server, which is one of the components of SC4SNMP.

See the following link for a list of currently available MIBs:
[https://pysnmp.github.io/mibs/index.csv](https://pysnmp.github.io/mibs/index.csv)

An alternative way to check if the MIB you're interested in is being served is to check the following link:
`https://pysnmp.github.io/mibs/asn1/@mib@` where `@mib@` is the name of MIB, for example, `IF-MIB`. If the file 
is downloading, that means the MIB file exists in the MIB server.

## Submit a new MIB file

In case you want to add a new MIB file to the MIB server, see the following steps:

1. Create a fork of the [https://github.com/pysnmp/mibs](https://github.com/pysnmp/mibs) repository.
   
2. Put one or more MIB files under `src/vendor/@vendor_name@` where `@vendor_name@` is the name of the MIB file's vendor. If there is currently no directory of vendors that you need, create it yourself.
   
3. Create a pull request to a `main` branch.
   
4. Name the pull request the following way: `feat: add @vendor_name@ MIB files`.


An alternative way of adding MIBs to the MIB server is to create an issue in the
[https://github.com/pysnmp/mibs](https://github.com/pysnmp/mibs) repository, attaching the files and information about 
the vendor.

## Update your instance of SC4SNMP with the newest MIB server

Usually SC4SNMP is released with the newest version of MIB server every time the new MIB files are added.
But, if you want to use the newest MIB server right after its released, you can do it manually using the `values.yaml` file:

1. Append `mibserver` configuration to the values.yaml, with the `mibserver.image.tag` of a value of the newest `mibserver`, for example:
```
mibserver:
  image:
    tag: "1.14.5"
```
Check all the MIB server releases in https://github.com/pysnmp/mibs/releases. 

2. Run `microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace`.

3. Restart the following worker-trap and worker-poller deployments:

```
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-worker-trap -n sc4snmp
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-worker-poller -n sc4snmp
```

## Beta: use MIB server with local MIBs

From the `1.15.0` version of the MIB server, there is a way to use local MIB files. This may be useful when your MIB 
files are proprietary, or you use SC4SNMP offline. This way, you can update necessary MIBs by yourself, without having to
go through the MIB request procedure.

In order to add your MIB files to the MIB server in standalone SC4SNMP installation:

1. Create or choose a directory on the machine where SC4SNMP is installed, for example, `/home/user/local_mibs`.
2. Create vendor directories inside. For example, if you have MIB files from `VENDOR1` and `VENDOR2`, create
`/home/user/local_mibs/VENDOR1` and `/home/user/local_mibs/VENDOR2` and put files inside accordingly. Putting wrong 
vendor names won't make compilation fail, this is more for the logging purposes. Segregating your files will make 
troubleshooting easier.
3. MIB files should be named the same as the contained MIB module. The MIB module name is specified at the beginning of
the MIB file before `::= BEGIN` keyword.
4. Add the following to the `values.yaml`:

```yaml
mibserver:
  localMibs:
    pathToMibs: "/home/user/local_mibs"
```

To verify that the process of compilation was completed successfully, check the the mibserver logs using the following command:

```bash
microk8s kubectl logs -f deployments/snmp-mibserver -n sc4snmp
```

This creates a Kubernetes pvc with MIB files inside and maps it to the MIB server pod.
Also, you can change the storageClass and size of persistence according to the `mibserver` schema, see https://github.com/pysnmp/mibs/blob/main/charts/mibserver/values.yaml.
The default persistence size is 1 Gibibyte, so consider reducing or expanding it to the amount you actually need.
Whenever you add new MIB files, rollout restart MIB server pods to compile them again, using the following command:

```bash
microk8s kubectl rollout restart deployment snmp-mibserver -n sc4snmp
```

For a multi-node Kubernetes installation, create pvc beforehand, copy files onto it, and add it to the MIB server
using `persistence.existingClaim`. If you go with the `localMibs.pathToMibs` solution for a multi-node installation
(with `nodeSelector` set up to schedule MIB server pods on the same node where the MIB files are),
when the Node with the mapped hostPath fails, you'll have to access the MIB files on another node.

