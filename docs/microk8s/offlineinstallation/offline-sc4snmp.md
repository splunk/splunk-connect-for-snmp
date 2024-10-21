# Offline SC4SNMP installation

See the following options for an offline SC4SNMP installation. 

## Local machine with internet access
To install the SC4SNMP offline, first, download some packages from the [Github release](https://github.com/splunk/splunk-connect-for-snmp/releases) and then move them
to the SC4SNMP installation server. Those packages are:

- `dependencies-images.tar`
- `splunk-connect-for-snmp-chart.tar`

Additionally, you'll need 

- `pull_mibserver.sh` script
- `pull_gui_images.sh` script

to easily pull and export mibserver image and GUI images.

Moreover, the SC4SNMP Docker image must be pulled, saved as a `.tar` package, and then moved to the server as well. 
This process requires Docker to be installed locally.

Images can be pulled from the following repository: `ghcr.io/splunk/splunk-connect-for-snmp/container:<tag>`. 
The latest tag can be found in [The Splunk Connect for SNMP Repository](https://github.com/splunk/splunk-connect-for-snmp), under the Releases section with the label `latest`.

See the following example of docker pull command:

```bash
docker pull ghcr.io/splunk/splunk-connect-for-snmp/container:<tag>
```

Afterwards, save the image. The directory where this image will be saved can be specified after the `>` sign:

```bash
docker save ghcr.io/splunk/splunk-connect-for-snmp/container:<tag> > snmp_image.tar
```

Other packages you have to pull are mibserver and GUI images. Do this by executing `pull_mibserver.sh` and 
`pull_gui_images.sh` scripts from the Release section, or copy-pasting its content. See the following:

```bash
chmod a+x pull_mibserver.sh # you'll probably need to make file executable
./pull_mibserver.sh
chmod a+x pull_gui_images.sh
./pull_gui_images.sh
```

Those scripts should produce `mibserver.tar` with the image of the mibserver and `sc4snmp-gui-images.tar` with GUI images inside.

All five packages, `mibserver.tar`, `snmp_image.tar`, `dependencies-images.tar`, `sc4snmp-gui-images.tar` and `splunk-connect-for-snmp-chart.tar`, must be moved to the SC4SNMP installation server.

## Installation on the server

On the server, all the images must be imported to the microk8s cluster. This can be done with the following command:

```bash
microk8s ctr image import <name_of_tar_image>
```

Run the following commands:

```bash
microk8s ctr image import dependencies-images.tar
microk8s ctr image import snmp_image.tar
microk8s ctr image import mibserver.tar
```

Afterwards, create `values.yaml`. It's a little different from `values.yaml` used in an online installation. 
The difference between the two files is the following, which is used for automatic image pulling:

```yaml
image:
  pullPolicy: "Never"
```

An example `values.yaml` file can be found in the [Offline SC4SNMP values.yaml template](https://github.com/splunk/splunk-connect-for-snmp/blob/main/examples/offline_installation_values.md).

Next, unpack the chart package `splunk-connect-for-snmp-chart.tar`. It will result in creating the following `splunk-connect-for-snmp` directory:

```bash
tar -xvf splunk-connect-for-snmp-chart.tar --exclude='._*'
```

Finally, run the helm install command in the directory where both the `values.yaml` and `splunk-connect-for-snmp` directories are located:

```bash
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

[offline_doc_link]: https://github.com/splunk/splunk-connect-for-snmp/blob/main/examples/offline_installation_values.md
