# SC4SNMP GUI

SC4SNMP GUI is deployed in kubernetes and can be accessed through the web browser.

## Enabling GUI

To enable GUI, the following section must be added to `values.yaml` file and `UI.enable` variable must be set to `true`:

```yaml
UI:
  enable: true
  frontEnd:
    NodePort: 30001
    pullPolicy: "Always"
  backEnd:
    NodePort: 30002
    pullPolicy: "Always"
  valuesFileDirectory: ""
  valuesFileName: ""
  keepSectionFiles: true
```

- `NodePort`: port number on which GUI will be accessible. It has to be from a range `30000-32767`.
- `pullPolicy`: [kubernetes pull policy](https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy)
- `valuesFileDirectory`: this is an obligatory field if UI is used. It is an absolute directory path on the host machine where configuration files from the GUI will be generated. It is used to keep all the changes from the GUI so that users can easily switch back from using UI to the current sc4snmp version. It is advised to create new folder for those files, because this directory is mounted to the Kubernetes pod and GUI application has full write access to this directory.
- `valuesFileName`: [OPTIONAL] full name of the file with configuration (e.g. `values.yaml`) that is stored inside the `valuesFileDirectory` directory. If this file name is provided, and it exists in this directory, then GUI will update appropriate sections in provided `values.yaml` file. If this file name is not provided, or provided file name can’t be found inside `valuesFileDirectory` then inside that directory there will be created three files with the latest GUI configuration of groups, profiles and inventory. Those configuration can be copied and pasted to the appropriate sections in the original `values.yaml` file.
- `keepSectionFiles`:  if valid `valuesFileName` was provided then by setting this variable to `true` or `false` user can decide whether to keep additional files with configuration of groups, profiles and inventory. If valid `valuesFileName` was NOT provided, then those files are created regardless of this variable.


To access the GUI, in the browser type the IP address of your Microk8s cluster followed by the NodePort number from the frontEnd section, e.g. `192.168.123.13:30001`.



