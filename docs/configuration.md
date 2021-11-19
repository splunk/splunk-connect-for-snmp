# Configuration

In this section, we refer to these required files for configuring the scheduler:
1. `scheduler-inventory.yaml`
2. `scheduler-config.yaml`
3. `traps-server-config.yaml`

When installing SC4SNMP via HELM, we can easily configure all these files from one point
of management: `config_values.yaml`. The structure is:
```yaml
files:
  scheduler:            
    inventory: |                        <- scheduler-inventory.yaml
      address,version,community,walk_interval,profiles,SmartProfiles,delete
      10.0.0.1,2c,homelab,300,,,
    config: |                           <- scheduler-config.yaml
      celery:
        broker:
          type: "rabbitmq"
      # Sample Configuration file
      ipv4: True
      ipv6: False
      communities:
        ...
  traps:                                
    config:                             <- traps-server-config.yaml
      snmp:
        communities:
          v1:
            - public
            - "my-area"
          v2:
            - public
            - "my-area"
```

Use the following command to propagate configuration changes:
``` bash
microk8s helm3 upgrade --install snmp -f deployment_values.yaml -f config_values.yaml -f static_values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```
## Traps Configuration

-   traps-server-config.yaml
    -   config.yaml

Splunk Connect for SNMP supports receiving SNMPv1 traps, SNMPv2 traps,
and SNMPv3 traps. To use this functionality, configure using authorized
SNMPv1/SNMPv2c community strings and/or SNMPv3 users in
**traps-server-config.yaml** (`files: traps: config` part of `config_values.yaml`). Non-authorized traps/informs will not work.

### Configure SNMPv1/v2c community strings

Add SNMPv1/SNMPv2c community strings under **v1/v2** section,
respectively.

**Params**:

-   **community string** (required) - SNMPv1/SNMPv2c community string.

### Configure SNMPv3 users

It gets a little more complex with respect to SNMPv3. The user database
in a SNMPv3 application is actually referenced by a combination of the
user's name (called a \"security Name\") and an identifier for the
given SNMP application you're talking to (called an \"engineID\").
Therefore, both userName and engineID are required for SNMPv3 under the
**v3** section.

**Params**:

-   **userName** (required) - A human-readable string representing the
    name of the SNMP USM user.

-   **authProtocol** (optional) - An indication of whether messages sent
    on behalf of this USM user can be authenticated, and if so, the type
    of authentication protocol that is used. If both authKey and
    authProtocol are not set, usmNoAuthProtocol is implied. If authKey
    is set and no authProtocol is specified, usmHMACMD5AuthProtocol
    takes effect.

    Supported authentication protocol identifiers are:

    -   None (default is authKey not given)
    -   MD5 (default if authKey is given)
    -   SHA
    -   SHA224
    -   SHA256
    -   SHA512

-   **authKey** (optional) - Initial value of the secret authentication
    key.

-   **privProtocol** (optional) - An indication of whether messages sent
    on behalf of this USM user are encrypted, and if so, the type of
    encryption protocol that is used. If both privKey and privProtocol
    are not set, usmNoPrivProtocol is implied. If privKey is set and no
    privProtocol is specified, usmDESPrivProtocol takes effect.

    Supported encryption protocol identifiers are:

    -   None (default is privhKey not given)
    -   DES (default if privKey is given)
    -   3DES
    -   AES
    -   AES128
    -   AES192
    -   AES192BLMT
    -   AES256
    -   AES256BLMT

-   **privKey** (optional) - Initial value of the secret encryption key.

-   **securityEngineId** (required): The EngineID of the authoritative
    SNMP engine that the traps were sent from.

e.g.

``` language
snmp:
   communities:
     v1:
       - public
       - "my-area"
     v2:
       - public
       - "my-area"
     v3:
       - userName: snmpv3test
         authKey: AuthPass1
         privKey: PrivPass2
         securityEngineId: 8000000004030201
       - userName: snmpv3test2
         authProtocol: SHA
         authKey: AuthPass11
         privProtocol: aes
         privKey: PrivPass22
         securityEngineId: 8000000004030202
       - userName: snmpv3test3
         securityEngineId: 8000000004030203
```

## Poller

### Scheduler Configuration

-   scheduler-config.yaml
    -   config.yaml
-   scheduler-inventory.yaml
    -   inventory.csv

Splunk Connect for SNMP supports polling from SNMPv1 agents, SNMPv2
agents, and SNMPv3 agents. To use this functionality, configure using
authorized SNMPv1/SNMPv2c community strings and/or SNMPv3 users in
**scheduler-config.yaml** (`files: scheduler: config` part of `config_values.yaml`).

### **inventory.csv**

Inventory.csv (`files: scheduler: inventory` part of `config_values.yaml`) acts as a lookup table where the poller application will
read the SNMP agents' information and its corresponding query
information.

```
address,version,community,walk_interval,profiles,SmartProfiles,delete
10.0.0.1,2c,homelab,300,,,
"IP:Port of SNMP agents, where port is optional with default of 161","An indication of SNMP versions", "community string for SNMPv1/v2 OR userNanme for SNMPv3", "query info", "query frequency in seconds"
```

> \"e.g. 174.62.79.72 (IP only) \| 174.62.79.72:161 (IP+port)\",\"e.g. 1
> \| 2c \| 3\", \"e.g. public (SNMPv1/SNMPv2c community string) \|
> testUser (SNMPv3 username, setup other params in config.yaml)\",\"e.g
> 1.3.6.1.2.1.1.9.1.3.1 (single oid for snmp get) \|
> 1.3.6.1.2.1.1.9.1.3.\* (oid for snmp walk to get subtree) \| router
> (profile used to setup detials in config.yaml\", \"e.g. 30\"

### **config.yaml**

config.yaml acts as an extension for inventory.csv for these three
situations.

#### 1. Configure optional parameters for SNMPv1/SNMPv2c community data

Community-Based Security Model of SNMPv1/SNMPv2c may require more
parameters, which can be set up in config.yaml (`files: scheduler: config` part of `config_values.yaml`).

> 1.  Add SNMPv1/SNMPv2c community string as Key under the **communities**
>     section.
> 2.  Add necessary parameters.
>
> > Here are supported optional parameters:

-   **communityIndex** (optional) - Unique index value of a row in
    snmpCommunityTable. If it is the only positional parameter, it is
    treated as a communityName.
-   **contextEngineId** (optional) - Indicates the location of the
    context in which management information is accessed when using the
    community string specified by the communityName.
-   **contextName** (optional) - The context in which management
    information is accessed when using the above communityName.
-   **tag** (optional) - Arbitrary string that specifies a set of
    transport endpoints from which a command responder application will
    accept management requests with a given communityName or to which
    notification originator application will send notifications when
    targets are specified by a tag value(s).

#### 2. Configure optional parameters SNMPv3 users

SNMPv3 users may require more parameters for different security levels,
which can be set up in config.yaml (`files: scheduler: config` part of `config_values.yaml`).

1.  Add SNMPv3 userName as Key under **usernames** section.
2.  Add necessary parameters.

> Here are supported optional parameters:

-   **authKey** (optional) - Initial value of the secret authentication
    key.

-   **authProtocol** (optional) - An indication of whether messages sent
    on behalf of this USM user can be authenticated, and if so, the type
    of authentication protocol that is used. If both authKey and
    authProtocol are not set, usmNoAuthProtocol is implied. If authKey
    is set and no authProtocol is specified, usmHMACMD5AuthProtocol
    takes effect.

    Supported authentication protocol identifiers are:

    -   None (default is authKey not given)
    -   MD5 (default if authKey is given)
    -   SHA
    -   SHA224
    -   SHA256
    -   SHA512

-   **privKey** (optional) - Initial value of the secret encryption key.

-   **privProtocol** (optional) - An indication of whether messages sent
    on behalf of this USM user be encrypted, and if so, the type of
    encryption protocol that is used. If both privKey and privProtocol
    are not set, usmNoPrivProtocol is implied. If privKey is set and no
    privProtocol is specified, usmDESPrivProtocol takes effect.

    Supported encryption protocol identifiers are:

    -   None (default is privhKey not given)
    -   DES (default if privKey is given)
    -   3DES
    -   AES
    -   AES128
    -   AES192
    -   AES192BLMT
    -   AES256
    -   AES256BLMT

-   **securityEngineId** (optional): The snmpEngineID of the
    authoritative SNMP engine to which a dateRequest message is to be
    sent.

-   **securityName** (optional): Along with the snmpEngineID, it
    identifies a row in the SNMP-USER-BASED-SM-MIB::usmUserTable that is
    to be used for securing the message.

-   **authKeyType** (optional): int. Type of authKey material.

-   **privKeyType** (optional): int. Type of privKey material.

-   **contextName**: (optional) contextName is used to name an instance
    of MIB. SNMP engine may serve several instances of the same MIB
    within possibly multiple SNMP entities. SNMP context is a tool for
    unambiguously identifying a collection of MIB variables behind the
    SNMP engine.

e.g.

``` yaml
usernames:
   testUser1:
     authKey: auctoritas
     privKey: privatus        
   testUser2:
     authKey: testauthKey
     privKey: testprivKey
     authProtocol: SHA
     privProtocol: AES
     securityEngineId: 8000000004030201
     securityName:
     authKeyType: 0
     privKeyType: 0
     contextName: "4c9184f37cff01bcdc32dc486ec36961"  
```

#### 3. Configure more detailed query information

Users can provide more detailed query information under the **profiles**
section to achieve two purposes: 1) query by mib string; 2) query
multiple oids/mib string for one agent.

1.  In **scheduler-inventory.yaml** (`files: scheduler: inventory` part of `config_values.yaml`), add the profile string(e.g. router)
    to the **profile** field under **data > inventory.csv** section.

```csv
"host", "version", "community", "profile", "freqinseconds"
10.42.0.58,1,public,router,30
```

2.  In **scheduler-config.yaml** (`files: scheduler: config` part of `config_values.yaml`), add the desired query information
    under the **profiles > \<profiles_string> > varBinds** section as list
    entries. e.g. **profiles > router > varBinds**.

When you use the mib string, you **MUST** follow the Syntax below

``` yaml
["MIB-Files", "MIB object name", "MIB index number"]
```

Where **"MIB index number"** is optional.

1.  Specify the index number when you want to get the information for a
    specific interface. e.g. \[\"SNMPv2-MIB\", \"sysUpTime\", 0\]
2.  Don't specify the index number when you want to get information for all
    interfaces. e.g. \[\"SNMPv2-MIB\", \"sysORID\"\]

**Note**: A wrong index number would cause an error. If you are not sure
which index exists, don't put it at all. For example, in the situation
where \[\"SNMPv2-MIB\", \"sysUpTime\", 0\] exsits, both
\[\"SNMPv2-MIB\", \"sysUpTime\", 0\] and \[\"SNMPv2-MIB\",
\"sysUpTime\"\] will help you get \[\"SNMPv2-MIB\", \"sysUpTime\", 0\],
while \[\"SNMPv2-MIB\", \"sysUpTime\", 1\] will throw erroe because
index 1 doesn\'t exist for sysUpTime.

``` yaml
profiles:
   router:
     varBinds:
       # Syntax: [ "MIB-Files", "MIB object name", "MIB index number"]
       - ['SNMPv2-MIB', 'sysDescr', 0]
       - ['SNMPv2-MIB', 'sysUpTime',0]
       - ['SNMPv2-MIB', 'sysORID']
       - ['CISCO-FC-MGMT-MIB', 'cfcmPortLcStatsEntry']
       - ['EFM-CU-MIB', 'efmCuPort']
       - '1.3.6.1.2.1.1.6.0'
       - '1.3.6.1.2.1.1.9.1.4.*'
```
#### 4. Configure additional field to the metrics data

Users can make every metric data include a **profile** name
(which is not included by default) by adding **profile**
under the **additionalMetricField** in **scheduler-config.yaml** (`files: scheduler: config` part of `config_values.yaml`)


e.g.

``` yaml
additionalMetricField:
  - profile
```

#### 5. Configure poller to return query with additional fields present

Users can add an **enricher** section to make poller enrich queries sent to Splunk by adding additional dimensions. There are two types of fields:
1. **existingVarBinds**: this section updates query results with new fields calculated from the existing SNMP information.
2. **additionalVarBinds**: this section updates query results with additional parameters defined below.

##### Existing VarBinds
For now, `existingVarBinds` section works only for IF-MIB oid family.
Every property of IF-MIB family can be extracted and added as an additional dimension to the query. For example, if we want to see the name and the index of the interface along with the basic query information,
the **enricher** must be structured as follows:
```yaml
enricher:
  oidFamily:
    IF-MIB:
      existingVarBinds:
        - ifIndex: 'interface_index'
        - ifDescr: 'interface_desc'
```
Let's run a metrics query in Splunk Search:
```
| msearch "index"="em_metrics"
```
While enricher is not being used, the example result is:
```yaml
{ [-]
   com.splunk.index: em_metrics
   host.name: 10.202.14.102
   metric_name:sc4snmp.IF-MIB.ifInOctets_1: 398485
}
```
After adding the `enricher` structure as noted above, the same result should contain "interface_index" and "interface_desc":
```yaml
{ [-]
   com.splunk.index: em_metrics
   host.name: 10.202.14.102
   interface_desc: lo
   interface_index: 1
   metric_name:sc4snmp.IF-MIB.ifInOctets_1: 398485
}
```

For an event query in Splunk Search:
```yaml
index="*" sourcetype="sc4snmp:meta"
```
Before using `enricher`, the search result is structured as following:
```yaml
oid-type1="ObjectIdentity" value1-type="OctetString" 1.3.6.1.2.1.2.2.1.6.2="0x00127962f940" value1="0x00127962f940" IF-MIB::ifPhysAddress.2="12:79:62:f9:40"  
```
When using the same `enricher` as in the example above, in the result string two new fields "interface_index" and "interface_desc" are visible:
```yaml
oid-type1="ObjectIdentity" value1-type="OctetString" 1.3.6.1.2.1.2.2.1.6.2="0x00127962f940" value1="0x00127962f940" IF-MIB::ifPhysAddress.2="12:79:62:f9:40" interface_index="2" interface_desc="eth0"
```

The value of newly added properties is calculated according to current query index. 
For IF-MIB::ifAdminStatus.**2** we're interested in IF-MIB::ifIndex.**2** and IF-MIB::ifDescr.**2**.
```yaml
IF-MIB::ifNumber.0 = INTEGER: 2
IF-MIB::ifIndex.1 = INTEGER: 1
IF-MIB::ifIndex.2 = INTEGER: 2
IF-MIB::ifDescr.1 = STRING: lo
IF-MIB::ifDescr.2 = STRING: eth0
```
Any other IF-MIB property can be inserted to existingVarBinds.

**existingVarBinds list parameters**

| existingVarBinds part | description | example | 
| --- | --- | --- |
| key | the key is the word between OID family identifier and the index | for ex. for MTU extraction, the key is **ifMtu** (derived from IF-MIB::**ifMtu**.1) |
| value | the field name shown as an additional dimension in Splunk | `interface_mtu` |

#### Additional VarBinds

#### 1. Index number -- indexNum
For every OID family there is an option to add index number as an additional dimension to both event and metrics data.
In order to enable it, the enricher must be structured as follows:
```yaml
enricher:
  oidFamily:
    IF-MIB:
      additionalVarBinds:
        - indexNum: 'index_number'
    SNMPv2-MIB:
      additionalVarBinds:
        - indexNum: 'index_number'
```
For the above configuration, every query concerning IF-MIB or SNMPv2-MIB has an additional `index_number` field equal to the index number of current record, for ex.:

For event query:
```yaml
oid-type1="ObjectIdentity" value1-type="OctetString" 1.3.6.1.2.1.2.2.1.2.2="eth0" value1="eth0" IF-MIB::ifDescr.2="eth0" index_number="2" 
```

For metrics query:
```yaml
	
{ [-]
   com.splunk.index: em_metrics
   host.name: 10.202.14.102
   index_num: 1
   metric_name:sc4snmp.IF-MIB.ifInOctets_1: 398485
}
```

**Additional varbinds available to configure**

| variable | description |
| --- | --- | 
| indexNum | index number of current record, for ex. `SNMPv2-MIB::sysORID.5` -> `index_num` is 5

**additionalVarBinds list parameters**

| additionalVarBinds part | description | example | 
| --- | --- | --- |
| key | the key is the value from additional varbinds table above | `indexNum` |
| value | the field name shown as an additional dimension in Splunk | `index_number`, `index_num`, `if_mib_index_number` |

#### Test the poller

**SNMPv1/SNMPv2**

-   You can change the inventory contents in scheduler-config.yaml (`files: scheduler: config` part of `config_values.yaml`) and
    use the following command to apply the changes to the Kubernetes cluster.
    Agents configuration is placed in scheduler-config.yaml under the
    section **inventory.csv**, and the content below is interpreted as a .csv file
    with following columns:

1.  host (IP or name)
2.  version of SNMP protocol
3.  community string authorisation phrase
4.  profile of device (varBinds of profiles can be found in `files: scheduler: config` part of `config_values.yaml`)
5.  frequency in seconds (how often SNMP connector should ask agent for
    data)

`` `csv    address,version,community,walk_interval,profiles,SmartProfiles,delete
10.0.0.1,2c,homelab,300,,, ``\`

``` bash
microk8s helm3 upgrade --install snmp -f deployment_values.yaml -f config_values.yaml -f static_values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

**SNMPv3**

-   Besides changing the inventory contents under the section
    `files: scheduler: inventory` part of `config_values.yaml`, you may need to set up security passphrases for
    the SNMPv3 under the section `files: scheduler: config: usernames` part of `config_values.yaml`.

Here are the steps to configure these two SNMPv3 Users.

  --------------------------------------------------------------------------
  User Name   Security    Auth        Priv        Auth         Priv
              Level       Protocol    Protocol    Passphrase   Passphrase
  ----------- ----------- ----------- ----------- ------------ -------------
  testUser1   Auth,Priv   MD5         DES         auctoritas   privatus

  testUser2   Auth,Priv   SHA         AES         authpass     privacypass
  --------------------------------------------------------------------------

1.  Specify User Name under **community** filed in section
    `files: scheduler: inventory` part of `config_values.yaml`.

```csv
address,version,community,walk_interval,profiles,SmartProfiles,delete
10.0.0.1,2c,homelab,300,,,
10.0.0.2:143,2c,homelab,300,,,
10.0.0.2:143,2c,homelab,300,,,
```

2.  Specify other security parameters under section `files: scheduler: config` part of `config_values.yaml`.

``` yaml
usernames:
   testUser1:
     authKey: auctoritas
     privKey: privatus        
   testUser2:
     authKey: authpass
     privKey: privacypass
     authProtocol: SHA
     privProtocol: AES
```

3.  Apply the changes.

``` bash
microk8s helm3 upgrade --install snmp -f deployment_values.yaml -f config_values.yaml -f static_values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```
