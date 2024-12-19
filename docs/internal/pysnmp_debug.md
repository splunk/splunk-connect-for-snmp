# PYSNP debug mode (internal)

During the on-calls and escalations, it might be helpful to understand low-levels details that are happening on SNMP protocol side. For that we are using `debug logger` from `pysnmp lib`.


List of available debug modes:
* io
* dsp
* msgproc
* secmod
* mibbuild
* mibview
* mibinstrum
* acl
* proxy
* app
* all


## docker-compose

Add on `.env` file `PYSNMP_DEBUG` variable and specify debug modes in comma-separated format:

```
PYSNMP_DEBUG=dsp,msgproc,io
```

## k8s

Add on top level of `values.yaml` file `pysnmpDebug` variable and specify debug modes (using comma-separated format):

```
pysnmpDebug: "dsp,msgproc,io"
```