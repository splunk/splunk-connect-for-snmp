## Running integration tests

### Set environmental variables

Create script `set_env.sh` in `scripts` folder with the following content:

```bash
export AWS_ACCESS_KEY_ID=<VALUE>
export AWS_SECRET_ACCESS_KEY=<VALUE>
export AWS_SECURITY_GROUP=<VALUE>
export AWS_SUBNET=<VALUE>
```

Fill values to match your AWS settings.

### Run integration tests

Run script from `scripts` folder:

```commandline
./local_run.sh
```

When the environment is created, you can log there using `ansible_host` created in `inventory.yaml` and 
`snmp-ssh-key.pem` from `.ssh` folder. The created username is `ubuntu`. For example, if `ansible_host` is `54.90.167.146`,
you can use ssh with:

```commandline
ssh -i .ssh/snmp-ssh-key.pem ubuntu@54.90.167.146
```

You can observe the progress in `~/splunk-connect-for-snmp/integration_tests/pytest.log`

### Run simulator with SNMPv3

If you want to walk SNMP V3 device place "test" value as secret in inventory.csv, copy sample_v3_values from integration tests into working directory, rename to secrets and edit 7 filed under secrets/snmpv3/test directory

### Run autodiscovery integration tests

The setup scripts install and configure a dedicated Nginx UDP stream proxy and
18 compact SNMP simulators before SC4SNMP starts. The discovery output directory
is owned by UID/GID `10001`, matching the discovery worker. MicroK8s places the
simulators in the dedicated `agent-simulator` namespace; Docker Compose uses an
equivalent isolated Docker network.

Run only the autodiscovery test locally with either deployment:

```shell
integration_tests/scripts/run_local_microk8s_tests.sh --test discovery
integration_tests/scripts/run_local_docker_tests.sh --test discovery
```

See `integration_tests/autodiscovery/README.md` for the simulator matrix,
network layout, credentials, and minimal OID set.
