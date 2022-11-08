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