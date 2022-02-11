#MIB submission process

In order to achieve human-readable OIDs,the corresponding MIB files are necessary.
They are being stored in one of the components of SC4SNMP - the MIB server. 

The lis of currently available MIBs is here:
https://pysnmp.github.io/mibs/index.csv

An alternative way to check if the MIB you're interested in is being served is to check the link:
`https://pysnmp.github.io/mibs/asn1/@mib@` where `@mib@` is the name of MIB (for example `IF-MIB`). If the file 
is downloading, that means the MIB file exists in the mib server.

## Requesting new MIB file

In case you want to add a new MIB file to the MIB server, follow the steps:

1. Create fork of the https://github.com/pysnmp/mibs repository 
   
2. Put MIB file/s under `src/vendor/@vendor_name@` where `@vendor_name@` is the name of the MIB file's vendor (in case
there is no directory of vendor you need, create it by yourself)
   
3. Create a pull request to a `main` branch
   
4. Name the pull request the following way: `feat: add @vendor_name@ MIB files`



