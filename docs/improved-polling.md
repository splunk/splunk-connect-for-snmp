# Improved polling performance

SC4SNMP now offers beta support for improved polling performance.

While this is in beta, we encourage users to explore it. Although we have conducted extensive testing, occasional issues may arise.
Your feedback during this phase is crucial in refining and optimizing and can be shared using [issues](https://github.com/splunk/splunk-connect-for-snmp/issues).
To get started, the zip file with helm chart must be downloaded. It can be found on [feat/improve-polling-time](https://github.com/splunk/splunk-connect-for-snmp/pull/976/checks) branch.

On the left-hand side click `create-charts-zip`:
![Workflows](../images/improved-polling-tmp/actions-view.png)

<hr style="border:2px solid">

At the bottom of the page in the `Artifacts` section there will be 
`charts` package. Download it and unzip it in your environment.

![Workflows](../images/improved-polling-tmp/charts-zip-view.png)

In `values.yaml` set the following image settings:

```yaml
image:
  repository: ghcr.io/splunk/splunk-connect-for-snmp/improved-polling-time
  tag: "latest"
```

Change the directory to `charts/splunk-connect-for-snmp` and run `microk8s helm3 dep update`. You can exit `charts/splunk-connect-for-snmp` directory.
While running `microk8s helm3 install` or `microk8s helm3 upgrade` commands, path to the helm chart must be modified. 
In the [sc4snmp installation](./microk8s/sc4snmp-installation.md#install-sc4snmp) documentation, the following commands are presented:
``` bash
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```
``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

In order to use this beta release, `splunk-connect-for-snmp/splunk-connect-for-snmp` needs to be changed to the path of the `charts/splunk-connect-for-snmp` directory. 

To learn how the new improved polling works, refer to the documentation [Poller Configuration - Define maxRepetitions](https://github.com/splunk/splunk-connect-for-snmp/blob/feat/improve-polling-time/docs/configuration/poller-configuration.md#define-maxrepetitions) 
for instructions.

Your involvement in testing new polling support is pivotal, and we look forward to hearing about your experiences.
