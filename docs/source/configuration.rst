Configuration operation
===================================================
Traps Configuration
===================================================

* traps-server-config.yaml

  * config.yaml

Splunk Connect for SNMP supports receiving SNMPv1 traps, SNMPv2 traps, and SNMPv3 traps.
To make it work, please configure with authorized SNMPv1/v2c community strings and/or SNMPv3 users in **traps-server-config.yaml**. Non-authorized traps/informs will be dropped.

Configure SNMPv1/v2c community strings
---------------------------------------------------


Add SNMPv1/v2c community strings under **v1/v2** section, respectively. 

**Params**:

* **community string** (required) - SNMP v1/v2c community string.


Configure SNMPv3 users
---------------------------------------------------

It gets a little more complex with respect to SNMPv3. The user database in a SNMPv3 application is actually referenced by a combination of the user's name (called a "security Name") and an identifier for the given SNMP application you're talking to (called an "engineID"). Therefore, both userName and engineID are required for SNMPv3 under **v3** section.

**Params**: 

* **userName** (required) - A human-readable string representing the name of the SNMP USM user.

* **authProtocol** (optional) - An indication of whether messages sent on behalf of this USM user can be authenticated, and if so, the type of authentication protocol that is used. If both authKey and authProtocol are not set, usmNoAuthProtocol is implied. If authKey is set and no authProtocol is specified, usmHMACMD5AuthProtocol takes effect.

  Supported authentication protocol identifiers are:

  * None (default is authKey not given)

  * MD5 (default if authKey is given)

  * SHA

  * SHA224

  * SHA256

  * SHA512


* **authKey** (optional) - Initial value of the secret authentication key. 

* **privProtocol** (optional) - An indication of whether messages sent on behalf of this USM user be encrypted, and if so, the type of encryption protocol that is used. If both privKey and privProtocol are not set, usmNoPrivProtocol is implied. If privKey is set and no privProtocol is specified, usmDESPrivProtocol takes effect.

  Supported encryption protocol identifiers are:

  * None (default is privhKey not given)

  * DES (default if privKey is given)

  * 3DES

  * AES

  * AES128

  * AES192

  * AES192BLMT

  * AES256

  * AES256BLMT

* **privKey** (optional) - Initial value of the secret encryption key. 

* **securityEngineId** (required): The EngineID of the authoritative SNMP engine that the traps was sent from. 

e.g. 

.. code-block:: language

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
    

Scheduler Configuration
===================================================
* scheduler-config.yaml

  * inventory.csv
  
  * config.yaml

Splunk Connect for SNMP supports polling from  SNMPv1 agents, SNMPv2 agents, and SNMPv3 agents.
To make it work, please configure with authorized SNMPv1/v2c community strings and/or SNMPv3 users in **scheduler-config.yaml**. 

**inventory.csv**
---------------------------------------------------


Inventory.csv acts as a lookup table where the poller application will read the SNMP agents' information and its corresponding queries information.


.. csv-table:: 
   :header: "host", "version", "community", "profile", "freqinseconds"
       

   "IP:Port of SNMP agents, where port is optional with default is 161","An indication of SNMP versions", "community string for SNMPv1/v2 OR userNanme for SNMPv3", "query info", "query frequency in seconds"

    "e.g. 174.62.79.72 (IP only) | 174.62.79.72:161 (IP+port)","e.g. 1 | 2c | 3", "e.g. public (SNMPv1/2 community string) | testUser (SNMPv3 username, setup other params in config.yaml)","e.g 1.3.6.1.2.1.1.9.1.3.1 (single oid for snmp get) | 1.3.6.1.2.1.1.9.1.3.* (oid for snmp walk to get subtree) | router (profile used to setup detials in config.yaml", "e.g. 30"

e.g.

.. csv-table:: 
   :header: "host", "version", "community", "profile", "freqinseconds"
   
   10.42.0.58,1,public,1.3.6.1.2.1.1.9.1.3.1,30
   host.docker.internal:161,2c,public,1.3.6.1.2.1.1.9.1.3.*,60
   174.62.79.72:16112,3,testUser,router,30

     

**config.yaml**
---------------------------------------------------


config.yaml acts as an extension for inventory.csv for these two situations.


1. Configure SNMPv3 users
---------------------------------------------------


SNMPv3 users may require more params for different security levels, which can be set up in config.yaml.

1. Add SNMPv3 userName as Key under **usernames** section.

2. Add necessary parameters.

  Here are supported optional parameters:

* **authKey** (optional) - Initial value of the secret authentication key. 

* **authProtocol** (optional) - An indication of whether messages sent on behalf of this USM user can be authenticated, and if so, the type of authentication protocol that is used. If both authKey and authProtocol are not set, usmNoAuthProtocol is implied. If authKey is set and no authProtocol is specified, usmHMACMD5AuthProtocol takes effect.

  Supported authentication protocol identifiers are:

  * None (default is authKey not given)

  * MD5 (default if authKey is given)

  * SHA

  * SHA224

  * SHA256

  * SHA512

* **privKey** (optional) - Initial value of the secret encryption key. 

* **privProtocol** (optional) - An indication of whether messages sent on behalf of this USM user be encrypted, and if so, the type of encryption protocol that is used. If both privKey and privProtocol are not set, usmNoPrivProtocol is implied. If privKey is set and no privProtocol is specified, usmDESPrivProtocol takes effect.

  Supported encryption protocol identifiers are:

  * None (default is privhKey not given)

  * DES (default if privKey is given)

  * 3DES

  * AES

  * AES128

  * AES192

  * AES192BLMT

  * AES256

  * AES256BLMT

* **securityEngineId** (optional): The snmpEngineID of the authoritative SNMP engine to which a dateRequest message is to be sent.

* **securityName** (optional): Together with the snmpEngineID it identifies a row in the SNMP-USER-BASED-SM-MIB::usmUserTable that is to be used for securing the message.

* **authKeyType** (optional): int. Type of authKey material. 

* **privKeyType** (optional): int. Type of privKey material.
               

* **contextName**: (optional) contextName is used to name an instance of MIB. SNMP engine may serve several instances of the same MIB within possibly multiple SNMP entities. SNMP context is a tool for unambiguously identifying a collection of MIB variables behind the SNMP engine.

e.g.

.. code-block:: language

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
        

2. Configure more detailed query information 
---------------------------------------------------
User can provide more detailed query information under **profiles** section to achieve two purposes: 1) query by mib string; 2) query multiple oids/mib string for one agent.

 1. Add the profile string in inventory.csv as Key under **profiles** section.
 2. add the desired query information as list entries under **<profile_tring>: varBinds**. e.g for <profile_tring> = router

.. code-block:: language

   profiles:
      router:
        varBinds:
          # Syntax: [ "MIB-Files", "MIB object name" "MIB index number"]
          - ['SNMPv2-MIB', 'sysDescr']
          - ['SNMPv2-MIB', 'sysUpTime',0]
          - ['SNMPv2-MIB', 'sysName']
          - ['CISCO-FC-MGMT-MIB', 'cfcmPortLcStatsEntry']
          - ['EFM-CU-MIB', 'efmCuPort']
          - '1.3.6.1.2.1.1.6.0'
          - '1.3.6.1.2.1.1.9.1.4.*'


   








    
    