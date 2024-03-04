# SNMP Data Format

SC4SNMP classifies SNMP data elements as metrics or textual fields. Metric types are usually the indicators worth monitoring, 
which change dynamically, while textual fields are helpful context to understand what an SNMP object means.

SC4SNMP classifies the data element as a metric when its type is one of the following:

- `Unsigned`
- `Counter`
- `TimeTicks`
- `Gauge`
- `Integer`

Every other type is interpreted as a field value.

Sometimes, the MIB file indicates a field as an `INTEGER`, but there is also some mapping defined. See the following`IF-MIB.ifOperStatus` example:

```
ifOperStatus OBJECT-TYPE
    SYNTAX  INTEGER {
                up(1),        -- ready to pass packets
                down(2),
                testing(3),   -- in some test mode
                unknown(4),   -- status can not be determined
                              -- for some reason.
                dormant(5),
                notPresent(6),    -- some component is missing
                lowerLayerDown(7) -- down due to state of
                                  -- lower-layer interface(s)
            }
```
[source](https://www.circitor.fr/Mibs/Mib/I/IF-MIB.mib)

Here a numeric value is expected, but actually what SNMP Agents ends up receiving from the device is a `string` value,
like `up`. To avoid setting textual value as a metric, SC4SNMP does an additional check and tries to cast the
numeric value to float. If the check fails, the value is classified as a textual field.

See the following simple example. You just added a device and didn't configure anything special. The data from a walk
in Splunk's metrics index is:

```
{
   ifAdminStatus: up
   ifDescr: GigabitEthernet1
   ifIndex: 1
   ifOperStatus: up
   ifPhysAddress: 0a:aa:ef:53:67:15
   ifType: ethernetCsmacd
   metric_name:sc4snmp.IF-MIB.ifInDiscards: 0
   metric_name:sc4snmp.IF-MIB.ifInErrors: 0
   metric_name:sc4snmp.IF-MIB.ifInOctets: 3873878708
   metric_name:sc4snmp.IF-MIB.ifInUcastPkts: 47512921
   metric_name:sc4snmp.IF-MIB.ifInUnknownProtos: 0
   metric_name:sc4snmp.IF-MIB.ifLastChange: 454107556
   metric_name:sc4snmp.IF-MIB.ifMtu: 1500
   metric_name:sc4snmp.IF-MIB.ifOutDiscards: 0
   metric_name:sc4snmp.IF-MIB.ifOutErrors: 0
   metric_name:sc4snmp.IF-MIB.ifOutOctets: 1738565177
   metric_name:sc4snmp.IF-MIB.ifOutUcastPkts: 44295751
   metric_name:sc4snmp.IF-MIB.ifSpeed: 1000000000
}
```

You can see a textual part:

```
   ifAdminStatus: up
   ifDescr: GigabitEthernet1
   ifIndex: 1
   ifOperStatus: up
   ifPhysAddress: 0a:aa:ef:53:67:15
   ifType: ethernetCsmacd
```

And a metric one:
```
   metric_name:sc4snmp.IF-MIB.ifInDiscards: 0
   metric_name:sc4snmp.IF-MIB.ifInErrors: 0
   metric_name:sc4snmp.IF-MIB.ifInOctets: 3873878708
   metric_name:sc4snmp.IF-MIB.ifInUcastPkts: 47512921
   metric_name:sc4snmp.IF-MIB.ifInUnknownProtos: 0
   metric_name:sc4snmp.IF-MIB.ifLastChange: 454107556
   metric_name:sc4snmp.IF-MIB.ifMtu: 1500
   metric_name:sc4snmp.IF-MIB.ifOutDiscards: 0
   metric_name:sc4snmp.IF-MIB.ifOutErrors: 0
   metric_name:sc4snmp.IF-MIB.ifOutOctets: 1738565177
   metric_name:sc4snmp.IF-MIB.ifOutUcastPkts: 44295751
   metric_name:sc4snmp.IF-MIB.ifSpeed: 1000000000
```

## To which Splunk index will my data go?

### Metric index

The rule is, if we poll a profile with AT LEAST one metric value, it will go to the metric index and will be
enriched with all the textual fields you have for the object. For example, when polling:

```yaml
profile_with_one_metric:
  frequency: 100
  varBinds:
    - ['IF-MIB', 'ifOutUcastPkts']
    - ['IF-MIB', 'ifInUcastPkts']
```

The record that you'll see in Splunk `| mpreview index=net*` for the same case as the previous one would be:

```
   ifAdminStatus: up
   ifDescr: GigabitEthernet1
   ifIndex: 1
   ifOperStatus: up
   ifPhysAddress: 0a:aa:ef:53:67:15
   ifType: ethernetCsmacd
   metric_name:sc4snmp.IF-MIB.ifOutUcastPkts: 44295751
   metric_name:sc4snmp.IF-MIB.ifInUcastPkts: 47512921
```

Only fields specified in `varBinds` are actively polled from the device. In the case of the previous `profile_with_one_metric`, the textual fields `ifAdminStatus`, `ifDescr`, `ifIndex`, `ifOperStatus` and `ifPhysAddress` are taken from the database cache. This is updated on every walk process. This is fine in most cases, as values such as
MAC address, interface type, or interface status shouldn't change frequently if at all. 

If you want to keep `ifOperStatus` and `ifAdminStatus` up to date all the time, define profile using the following example:

```yaml
profile_with_one_metric:
  frequency: 100
  varBinds:
    - ['IF-MIB', 'ifOutUcastPkts']
    - ['IF-MIB', 'ifInUcastPkts']
    - ['IF-MIB', 'ifOperStatus']
    - ['IF-MIB', 'ifAdminStatus']
```

The result in Splunk will look the same, but `ifOperStatus` and `ifAdminStatus` will be actively polled.

### Event index

It is possible to create an event without a single metric value. In such scenario, it will go to an event index.
See the following example of profile under that scenario:

```yaml
profile_with_only_textual_fields:
  frequency: 100
  varBinds:
    - ['IF-MIB', 'ifDescr']
    - ['IF-MIB', 'ifName']
    - ['IF-MIB', 'ifOperStatus']
```

In the following example, no additional enrichment will be done. The events in event index `index=netops` of Splunk would look like:

```
{ [-]
   IF-MIB.ifDescr: { [-]
     name: IF-MIB.ifDescr
     oid: 1.3.6.1.2.1.2.2.1.2.5
     time: 1676302789.9729967
     type: f
     value: VirtualPortGroup0
   }
   IF-MIB.ifName: { [-]
     name: IF-MIB.ifName
     oid: 1.3.6.1.2.1.31.1.1.1.1.5
     time: 1676302789.6655216
     type: f
     value: Vi0
   }
   IF-MIB.ifOperStatus: { [-]
     name: IF-MIB.ifOperStatus
     oid: 1.3.6.1.2.1.2.2.1.8.5
     time: 1676302789.6655502
     type: g
     value: up
   }
}
```
