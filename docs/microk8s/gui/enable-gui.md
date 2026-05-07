# SC4SNMP GUI

SC4SNMP GUI is deployed in kubernetes and can be accessed through the web browser.

!!!warning 
    Please note that the UI is not officially supported as part of the SC4SNMP project. We are actively working on this issue and anticipate a resolution in the near future. The UI now ships with an optional authentication and authorisation layer (see [Enabling authentication and authorisation](#enabling-authentication-and-authorisation) below). When authentication is disabled, the UI must only be used along with additional controls that restrict access.

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
- `pullPolicy`: [kubernetes pull policy](https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy).
- `valuesFileDirectory`: this is an obligatory field if UI is used. It is an absolute directory path on the host machine 
where configuration files from the GUI will be generated. It is used to keep all the changes from the GUI so that users can 
easily switch back from using UI to the current sc4snmp version. It is advised to create new folder for those files, 
because this directory is mounted to the Kubernetes pod and GUI application has full write access to this directory.
- `valuesFileName`: [OPTIONAL] full name of the file with configuration (e.g. `values.yaml`) that is stored inside the 
`valuesFileDirectory` directory. If this file name is provided, and it exists in this directory, then GUI will update 
appropriate sections in provided `values.yaml` file. If this file name is not provided, or provided file name cannot be
found inside `valuesFileDirectory` then inside that directory there will be created three files with the latest GUI configuration
of groups, profiles and inventory. Those configuration can be copied and pasted to the appropriate sections in the original `values.yaml` file.

  Template of initial `values.yaml`:

    ```yaml
    scheduler:
      profiles: |
    
      groups: |
    
    poller:
      inventory: |-
    ```
  
  > This part of configuration can be also pasted to the `values.yaml` used for SC4SNMP installation.

- `keepSectionFiles`:  if valid `valuesFileName` was provided then by setting this variable to `true` or `false` user can 
decide whether to keep additional files with configuration of groups, profiles and inventory. If valid `valuesFileName` 
was NOT provided, then those files are created regardless of this variable.


To access the GUI, in the browser type the IP address of your Microk8s cluster followed by the NodePort number from the 
frontEnd section, e.g. `192.168.123.13:30001`.

## Enabling authentication and authorisation

Starting with the UI authentication feature, SC4SNMP-UI can require users to log in with a username and password before 
any configuration is viewed or changed. 

Authentication is disabled by default to preserve backwards compatibility. Follow the steps below to turn it on.

### Step 1 - Generate the admin password hash

The UI backend validates logins against an Argon2id hash. Generate one locally with the `argon2-cffi` library - the hash 
is the only value that will be stored.

Install the library and run the snippet below on any machine with Python 3.8+:

```bash
pip install argon2-cffi
python3 - <<'PY'
import getpass, sys
from argon2 import PasswordHasher

pw = getpass.getpass("Password: ")
if pw != getpass.getpass("Confirm password: "):
    sys.exit("Error: passwords do not match.")
if len(pw) < 8:
    sys.exit("Error: password must be at least 8 characters.")
print(PasswordHasher().hash(pw))
PY
```

You will be prompted for the password twice (minimum 8 characters). The command prints a single line containing the 
Argon2id hash (it starts with `$argon2id$...`). Copy that value - you will need it in the next step.

### Step 2 - Create the Kubernetes Secret

Credentials are consumed by the UI backend only through a Kubernetes Secret that lives in the same namespace as the 
SC4SNMP release (typically `sc4snmp`). The Secret must expose exactly these three keys:

| Key             | Description                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| `username`      | Admin username used at the login screen.                                    |
| `password_hash` | Argon2id hash produced in Step 1.                                           |
| `jwt_secret`    | Random hex string (>=32 bytes) used to sign session JWTs.                    |

Create the Secret with `kubectl`, pasting the hash generated in Step 1:

```bash
microk8s kubectl create secret generic sc4snmp-ui-auth \
  --namespace sc4snmp \
  --from-literal=username=admin \
  --from-literal=password_hash='<paste Argon2id hash here>' \
  --from-literal=jwt_secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

!!!note
    - The `jwt_secret` must be generated with a cryptographically secure random source (the command above uses Python's 
    `secrets` module). Never reuse it across environments and rotate it periodically.
    - To change the password or rotate the JWT secret, delete and recreate the Secret (or use `kubectl create secret ... 
      --dry-run=client -o yaml | kubectl apply -f -`) and restart the UI backend pods so they pick up the new values.

### Step 3 - Enable authentication in `values.yaml`

Add the `auth` section under `UI` and point `existingSecret` at the Secret created in the previous step:

```yaml
UI:
  enable: true
  # CORS allow-list for the backend (comma-separated scheme+host[+port]).
  # REQUIRED in production when authentication is enabled.
  allowedOrigins: "https://snmp-ui.example.com"

  auth:
    enabled: true
    existingSecret: "sc4snmp-ui-auth"
    jwtExpiryHours: 2
    idleTimeoutMinutes: 30
    secureCookies: false
```

Configuration reference:

| Key                          | Description                                                                                                                                                                                                                                                                                                                   | Default | Required                          |
|------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|-----------------------------------|
| `UI.auth.enabled`            | Set to `true` to require login. When `false`, the UI is unauthenticated.                                                                                                                                                                                                                                                      | `false` | no                                |
| `UI.auth.existingSecret`     | Name of the Secret created in Step 2. If omitted while auth is enabled, the Helm chart refuses to render (`helm template`/`helm install` will fail with an explanatory error). Prevents credentials from flowing through `values.yaml`.                                                                                       | `""`    | **yes**, when `auth.enabled=true` |
| `UI.auth.jwtExpiryHours`     | Absolute lifetime of a session JWT. After this period the user must log in again regardless of activity.                                                                                                                                                                                                                      | `2`     | no                                |
| `UI.auth.idleTimeoutMinutes` | Idle timeout. If no authenticated request is made for this many minutes, the session is invalidated.                                                                                                                                                                                                                          | `30`    | no                                |
| `UI.auth.secureCookies`      | When `true`, the session cookie is issued with the `Secure` flag and is only transmitted over HTTPS. Requires an HTTPS-terminating reverse proxy (e.g. nginx) in front of the NodePorts - the Helm chart serves plain HTTP only. Set to `false` for plain HTTP deployments; browsers will silently drop the cookie otherwise. | `false` | no                                |
| `UI.allowedOrigins`          | Comma-separated list of origins allowed to call the UI backend (e.g. `http://localhost:30001`). If empty and `auth.enabled=true`, the backend defaults to `http://localhost:8080`. Set explicitly in production to the exact URL(s) a browser will use to reach the UI - otherwise login requests will be rejected by CORS.   | `""`    | recommended in production         |

### Step 4 - Apply and verify

Upgrade the Helm release so the new settings take effect:

```bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp \
  --namespace sc4snmp --create-namespace
```

Open the UI in a browser (`https://<ui-host>:<frontEnd.NodePort>`). You will be redirected to a login screen; authenticate 
with the username and password used when generating the Secret. Inactivity beyond `idleTimeoutMinutes` or sessions older 
than `jwtExpiryHours` will require a fresh login.

### Operational guidance

- Serve the UI over HTTPS (TLS 1.2+). Because the JWT cookie is `HttpOnly` and `Secure`, authenticated access over plain 
  HTTP is intentionally broken outside `localhost`.
- Keep `UI.allowedOrigins` as tight as possible - ideally a single production URL. Wildcards are not supported when 
  authentication is enabled.
- Rotate the `jwt_secret` on staff changes or suspected compromise. Rotating the secret invalidates all outstanding 
  sessions immediately.
- Never commit the Kubernetes Secret manifest, the admin password, the password hash, or the JWT secret to source 
  control. Manage them with your existing secrets management solution (sealed-secrets, Vault, cloud KMS, etc.).
- Audit who has `get`/`list` permissions on Secrets in the release namespace; those users can read `password_hash` and 
  `jwt_secret`.

