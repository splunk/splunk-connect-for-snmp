## General issues

### Upgrading SC4SNMP from 1.12.2 to 1.12.3

When upgrading SC4SNMP from version `1.12.2` to `1.12.3`, the subchart version of MongoDB will be updated from `13.18.5` to `15.6.26`. This upgrade requires an increase in the MongoDB `Feature Compatibility Version (FCV)` from `5.0` to `6.0`.

To facilitate this change, a new pre-upgrade job has been introduced in SC4SNMP: `mongo-fcv-upgrade-to-6`. This job automatically updates the Feature Compatibility Version on MongoDB before the installation of MongoDB version `15.6.26`.

#### Pre-Upgrade Job: `mongo-fcv-upgrade-to-6`

- The `mongo-fcv-upgrade-to-6` job is designed to ensure compatibility by running the FCV update prior to upgrading MongoDB.

#### Handling Job Failures

If the `mongo-fcv-upgrade-to-6` job fails for any reason, there are two recovery options:

1. **Reinstall SC4SNMP**:

    [Reinstall SC4SNMP](../../microk8s/sc4snmp-installation#restart-splunk-connect-for-snmp) with **Persistent Volume Claim (PVC) deletion**.

2. **Manually Update MongoDB**:

    [Update MongoDB's Feature Compatibility Version](https://www.mongodb.com/docs/manual/release-notes/6.0-upgrade-standalone/#upgrade-procedure) manually by executing the following command:
     ```bash
     microk8s exec -it pod/<mongodb-pod-id> -n sc4snmp mongosh
     db.adminCommand( { setFeatureCompatibilityVersion: "6.0" })
     ```

    Replace `<mongodb-pod-id>` with the actual Pod ID of your MongoDB instance.


### Upgrading SC4SNMP from 1.12.3 to 1.13.0

When upgrading SC4SNMP from version `1.12.3` to `1.13.0`, the subchart version of MongoDB will be updated from `15.6.26` to `16.5.9`. This upgrade requires an increase in the MongoDB `Feature Compatibility Version (FCV)` from `6.0` to `7.0`.

To facilitate this change, a new pre-upgrade job has been introduced in SC4SNMP: `mongo-fcv-upgrade-to-7`. This job automatically updates the Feature Compatibility Version on MongoDB before the installation of MongoDB version `16.5.9`.

#### Pre-Upgrade Job: `mongo-fcv-upgrade-to-7`

- The `mongo-fcv-upgrade-to-7` job is designed to ensure compatibility by running the FCV update prior to upgrading MongoDB.

#### Handling Job Failures

If the `mongo-fcv-upgrade-to-7` job fails for any reason, there are two recovery options:

1. **Reinstall SC4SNMP**:

    [Reinstall SC4SNMP](../../microk8s/sc4snmp-installation#restart-splunk-connect-for-snmp) with **Persistent Volume Claim (PVC) deletion**.

2. **Manually Update MongoDB**:

    [Update MongoDB's Feature Compatibility Version](https://www.mongodb.com/docs/manual/release-notes/6.0-upgrade-standalone/#upgrade-procedure) manually by executing the following command:
     ```bash
     microk8s exec -it pod/<mongodb-pod-id> -n sc4snmp mongosh
     db.adminCommand( { setFeatureCompatibilityVersion: "7.0", confirm: true })
     ```

    Replace `<mongodb-pod-id>` with the actual Pod ID of your MongoDB instance.
