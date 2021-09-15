# Configuration

In this section we're refering to following files required to configure scheduler:
1. `scheduler-inventory.csv`
2. `scheduler-config.yaml`
3. `traps-server-config.yaml`

While installing SC4SNMP via HELM we can easily configure all of those using one point
of management: `values.yaml`. The structure is:
```yaml
scheduler:
  ...
  inventory:               
    content: |-                       <- scheduler-inventory.csv
      #10.0.0.1,2c,public,basev1,300
  config: |                           <- scheduler-config.yaml
    celery:
      broker:
        type: "rabbitmq"
    # Sample Configuration file
    ipv4: True
    ipv6: False
    communities:
      ...
traps:                                <- traps-server-config.yaml
  ...
  config:
    snmp:
      communities:
        v1:
          - public
          - "my-area"
        v2:
          - public
          - "my-area"
```
From now on, when editing any of those files is mentioned, that means the change must be
inserted in corresponding section of `values.yaml`.
## Traps Configuration

-   traps-server-config.yaml
    -   config.yaml

Splunk Connect for SNMP supports receiving SNMPv1 traps, SNMPv2 traps,
and SNMPv3 traps. To make it work, please configure with authorized
SNMPv1/SNMPv2c community strings and/or SNMPv3 users in
**traps-server-config.yaml** (`traps: config` part of `values.yaml`). Non-authorized traps/informs will be
dropped.

### Configure SNMPv1/v2c community strings

Add SNMPv1/SNMPv2c community strings under **v1/v2** section,
respectively.

**Params**:

-   **community string** (required) - SNMPv1/SNMPv2c community string.

### Configure SNMPv3 users

It gets a little more complex with respect to SNMPv3. The user database
in a SNMPv3 application is actually referenced by a combination of the
user\'s name (called a \"security Name\") and an identifier for the
given SNMP application you\'re talking to (called an \"engineID\").
Therefore, both userName and engineID are required for SNMPv3 under
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

-   **privKey** (optional) - Initial value of the secret encryption key.

-   **securityEngineId** (required): The EngineID of the authoritative
    SNMP engine that the traps was sent from.

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
agents, and SNMPv3 agents. To make it work, please configure with
authorized SNMPv1/SNMPv2c community strings and/or SNMPv3 users in
**scheduler-config.yaml** (`scheduler: config` part of `values.yaml`).

### **inventory.csv**

Inventory.csv (`scheduler: inventory: content` part of `values.yaml`) acts as a lookup table where the poller application will
read the SNMP agents\' information and its corresponding queries
information.

```
"host", "version", "community", "profile", "freqinseconds"
"IP:Port of SNMP agents, where port is optional with default is 161","An indication of SNMP versions", "community string for SNMPv1/v2 OR userNanme for SNMPv3", "query info", "query frequency in seconds"
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
params, which can be set up in config.yaml (`scheduler: config` part of `values.yaml`).

> 1.  Add SNMPv1/SNMPv2c community string as Key under **communities**
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
    accept management requests with given communityName or to which
    notification originator application will send notifications when
    targets are specified by a tag value(s).

#### 2. Configure optional parameters SNMPv3 users

SNMPv3 users may require more params for different security levels,
which can be set up in config.yaml (`scheduler: config` part of `values.yaml`).

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

-   **securityName** (optional): Together with the snmpEngineID it
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

User can provide more detailed query information under **profiles**
section to achieve two purposes: 1) query by mib string; 2) query
multiple oids/mib string for one agent.

1.  In **scheduler-inventory.yaml** (`scheduler: inventory: content` part of `values.yaml`), add the profile string(e.g. router)
    to **profile** field under **data > inventory.csv** section.

```csv
"host", "version", "community", "profile", "freqinseconds"
10.42.0.58,1,public,router,30
```

2.  In **scheduler-config.yaml** (`scheduler: config` part of `values.yaml`), add the desired query information
    under **profiles > \<profiles_string> > varBinds** section as list
    entries. e.g. **profiles > router > varBinds**.

When you use the mib string, you **MUST** follow the Syntax below

``` yaml
["MIB-Files", "MIB object name", "MIB index number"]
```

Where **"MIB index number"** is optional.

1.  Specify the index number when you want to get the information for a
    specific interface. e.g. \[\"SNMPv2-MIB\", \"sysUpTime\", 0\]
2.  Don't put the index number when you want to get information for all
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

#### Test the poller

**SNMPv1/SNMPv2**

-   You can change the inventory contents in scheduler-config.yaml (`scheduler: config` part of `values.yaml`) and
    use following command to apply the changes to Kubernetes cluster.
    Agents configuration is placed in scheduler-config.yaml under
    section **inventory.csv**, content below is interpreted as csv file
    with following columns:

1.  host (IP or name)
2.  version of SNMP protocol
3.  community string authorisation phrase
4.  profile of device (varBinds of profiles can be found in `scheduler: config` part of `values.yaml`)
5.  frequency in seconds (how often SNMP connector should ask agent for
    data)

`` `csv    "host", "version", "community", "profile", "freqinseconds"       10.42.0.58,1,public,1.3.6.1.2.1.1.9.1.3.1,30    host.docker.internal,2c,public,1.3.6.1.2.1.1.9.1.3.*,60 ``\`

``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/snmp-installer --namespace=sc4snmp --create-namespace
```

**SNMPv3**

-   Besides changing the inventory contents under section
    `scheduler: inventory: content` of `values.yaml`, you may need to set up security passphrases for
    the SNMPv3 under section `scheduler: config: usernames` of `values.yaml`.

Here are the steps to configure these two SNMPv3 Users.

  --------------------------------------------------------------------------
  User Name   Security    Auth        Priv        Auth         Priv
              Level       Protocol    Protocol    Passphrase   Passphrase
  ----------- ----------- ----------- ----------- ------------ -------------
  testUser1   Auth,Priv   MD5         DES         auctoritas   privatus

  testUser2   Auth,Priv   SHA         AES         authpass     privacypass
  --------------------------------------------------------------------------

1.  Specify User Name under **community** filed in section
    `scheduler: inventory: content` of `values.yaml`.

```csv
"host", "version", "community", "profile", "freqinseconds"
host.docker.internal1,3,testUser1,1.3.6.1.2.1.1.9.1.3.1,30
host.docker.internal2,3,testUser2,1.3.6.1.2.1.1.9.1.3.*,30
```

2.  Specify other security params under section `scheduler: config` of `values.yaml`.

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
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/snmp-installer --namespace=sc4snmp --create-namespace
```
