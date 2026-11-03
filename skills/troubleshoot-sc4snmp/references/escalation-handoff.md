# SC4SNMP escalation handoff

Use this file when the failure modes do not resolve the issue, when the evidence points outside SC4SNMP, or when the user asks to escalate.

## When to escalate

Treat the issue as a suspected SC4SNMP defect when all of the following are true:

1. The configuration was checked against the published docs for the installed version.
2. The fixes in the matching failure mode were tried and did not help.
3. It reproduces on the latest release, or the CHANGELOG shows no fix for it.
4. The evidence points at SC4SNMP: a `raised unexpected` traceback, a crash loop without a configuration cause, lost schedules or data, or behavior that contradicts the docs.
5. Device, network, and Splunk-side causes are ruled out with evidence.

Escalate right away, after mitigating where possible, when data has stopped for all devices, components keep crashing, or there is a risk of losing MongoDB data. Mitigating means rolling back the last change or reverting to the previous chart version.

Two kinds of failure need different evidence:
- **Task failure:** a `raised unexpected` traceback while the pod or container stays up. One task failed; capture the full traceback, the task name and ID, and the device address.
- **Process crash:** the restart count grows, or the pod is in `CrashLoopBackOff`. Capture the previous container's logs, the exit code, and the `OOMKilled` state ([status](operator-commands.md#pod-and-container-status)).

## Capture before escalating

Collect each item or mark it unknown:

1. SC4SNMP version (chart and image tag), runtime and its version (MicroK8s, Docker Compose, or other Kubernetes), and the host OS and kernel version ([version](operator-commands.md#version)).
2. The previous working version, and what changed before the failure: upgrade, configuration, inventory, secrets, OS, or network.
3. Redacted `values.yaml` or `.env`, plus the relevant inventory rows, profiles, and groups, and whether `UI.enable` is `true` ([configuration](operator-commands.md#configuration-redacted)).
4. The symptom and scope:
   - which pipeline (polling, traps, discovery) and how many devices
   - when it started, with timezone
   - whether it is reproducible or one-off, with the steps to reproduce
5. HEC test result, and the target indexes for events and metrics ([HEC check](operator-commands.md#hec-check)).
6. Timestamped logs from the affected components, at `DEBUG` if the issue was reproduced, with secrets redacted ([logs](operator-commands.md#logs-by-component)).
7. Pod or container status, recent events, and resource usage ([status](operator-commands.md#pod-and-container-status), [resources](operator-commands.md#resource-usage)).
8. The failure-mode branch followed, the checks run, and their results.
9. Any workaround applied, and its effect.
10. Links to existing GitHub issues searched, open and closed: https://github.com/splunk/splunk-connect-for-snmp/issues?q=is%3Aissue

## Do not collect

- HEC tokens, community strings, SNMPv3 authentication or privacy keys, and MongoDB, Redis, or UI passwords.
- Full MongoDB dumps or Redis snapshots, unless engineering asks for them through the support case.
- Unredacted device inventories, or device addresses that are not involved in the issue.

## Handoff template

```text
SC4SNMP issue: <symptom; ongoing or mitigated>
Escalation basis: <which "When to escalate" criteria are met, or "urgent: all data stopped / crash loop / data-loss risk">
Impact and scope: <pipeline, number of affected devices, data gap>
Versions and runtime: <SC4SNMP chart/image, MicroK8s/Compose version, OS and kernel>
Timeline: <start time with timezone, recent changes, last known good>
Evidence: <exact error lines with timestamps, counts, search results>
Checked and changed: <failure-mode branch, checks run and results, changes made>
Boundary: <SC4SNMP component, or external owner and why>
Workaround: <applied workaround and whether it holds>
Unknowns: <missing facts>
Requested help: <specific next action or decision>
```

## Where to send

Submit a ticket or issue only when the user asks for it.

- **Customer support case:** if the issue is not a confirmed bug or feature request, open a case through the Splunk Support Portal; see https://splunk.my.site.com/customer/s/article/Working-with-Support-and-the-Support-Portal
- **Bug report:** open a GitHub issue with the **Bug / Escalation report** template at https://github.com/splunk/splunk-connect-for-snmp/issues/new/choose. Fill in:
  - whether support replicated the issue
  - SC4SNMP version
  - runtime
  - `values.yaml` for installation or first-connection errors
  - steps to reproduce
  - logs

  Paste the handoff template into the description.
- **Community questions:** `#splunk-connect-for-snmp` in the splunk-usergroups Slack workspace, https://splunk-usergroups.slack.com/archives/C01K4V86WV7

## External owner handoffs

| Evidence | Owner | Hand over |
|---|---|---|
| `snmpget` from the SC4SNMP host times out with verified credentials, or the agent returns malformed responses | Device or SNMP agent owner | Device address, SNMP version, OID tested, exact error, and time |
| A test trap from the SC4SNMP host arrives but device traps do not, or polls time out for a whole subnet | Network or firewall owner | Source and destination addresses, UDP port, and the time of the test |
| HEC returns `Invalid token`, `Incorrect index`, `Token disabled`, or HTTP 5xx, or the target index does not exist | Splunk admin | HEC endpoint (no token), response body, index names, and time |
| Node, CNI, storage, or load balancer problems on a non-MicroK8s cluster | Kubernetes platform owner | Pod events, service status, and the failing resource |

## Resolution standard

Call the issue resolved only when all of these hold:

- Fresh events or metrics for the affected devices reach the target index after the fix ([Splunk searches](operator-commands.md#splunk-searches)).
- The result holds for at least one full poll or walk interval.
- The fix is persisted in `values.yaml`, `.env`, or the inventory, and survives the next `helm upgrade` or `docker compose up -d`.

A clean restart, a successful `helm upgrade`, or an empty error search alone is not proof. If a GitHub issue was filed, update it with the root cause and the fix.
