---
name: troubleshoot-sc4snmp
description: Diagnose Splunk Connect for SNMP (SC4SNMP) polling, walk, trap, discovery, SNMPv3 authentication, HEC delivery, inventory and profile, scheduler and Redis, MongoDB, and MIB problems on MicroK8s or Docker Compose with operator-run commands. Keep troubleshooting within SC4SNMP; identify device, network, or Splunk-side failures and hand off to their owner.
---

# Troubleshoot SC4SNMP

Find the earliest failing SC4SNMP stage, give the next useful check, and verify an evidenced fix. The operator runs every command; this skill needs no direct access to the cluster, hosts, or Splunk.

## Scope

Investigate SC4SNMP itself: the scheduler, worker-poller, worker-sender, worker-trap, traps, inventory job, discovery, mibserver, MongoDB, Redis, and UI pods or containers; `values.yaml`, `.env`, and the inventory, scheduler, and traps configuration; SNMPv3 secrets; delivery from SC4SNMP to Splunk HEC; and whether the MicroK8s add-ons SC4SNMP depends on (`helm3`, `hostpath-storage` or `openebs`, `rbac`, `metrics-server`, `metallb`, `dns`) are enabled and match the installation guide.

Do not investigate or change SNMP agent configuration on devices, firewalls or routing, Splunk indexes, HEC receiver configuration, or the internals of non-MicroK8s Kubernetes platforms. Also do not set up or administer the MicroK8s cluster itself: installing MicroK8s, sizing or joining nodes, choosing a metallb IP pool, or offline or proxy installation. When a required add-on is missing or an installation step was skipped, name it and point to [MicroK8s add-ons or installation steps missing](references/failure-modes.md#microk8s-add-ons-or-installation-steps-missing) instead of walking through the setup. If evidence points outside SC4SNMP entirely, state the boundary and give a short handoff to that owner using [external owner handoffs](references/escalation-handoff.md#external-owner-handoffs).

## Pipeline map

```text
Polling: scheduler -> worker-poller (walk or poll -> enrich) -> worker-sender (prepare -> send) -> Splunk HEC
Traps:   SNMP agent -> trap service (UDP) -> traps -> worker-trap (trap) -> worker-sender (prepare -> send) -> Splunk HEC
State:   MongoDB (inventory, profiles, groups, walk results)   Redis (Celery queues, RedBeat schedules)
```

- A device is polled only after its first successful walk. Walks run after an inventory change and then every `walk_interval`.
- Data with numeric values goes to the metrics index (default `netmetrics`); text-only data and traps go to the events index (default `netops`).
- Locate the first stage with no evidence of success and troubleshoot there.

## Start with the minimum evidence

Ask only for what is missing to choose the first check:

1. Runtime: MicroK8s, Docker Compose, or another Kubernetes distribution.
2. SC4SNMP version ([how to get it](references/operator-commands.md#version)).
3. Symptom and scope: polling, traps, or discovery; one device, some, or all; when it started.
4. Recent change: upgrade, `values.yaml`, `.env`, or inventory edit, secret rotation, UI "Apply changes", host OS or kernel update.
5. One matching error line with its timestamp from the relevant component ([which logs](references/operator-commands.md#logs-by-component)).

If the first message already contains an error that matches a failure mode, start that branch's first check right away and ask for the missing items in the same reply. Then follow the matching branch in [failure modes](references/failure-modes.md); each branch names the extra artefact to request. Collect the full bundle only when [escalating](references/escalation-handoff.md#capture-before-escalating); that is the one time to request several items at once.

Never request or repeat HEC tokens, community strings, SNMPv3 authentication or privacy keys, or MongoDB, Redis, or UI passwords. Ask for `values.yaml`, `.env`, and configuration files with those values replaced by `<redacted>`. If the user pastes a secret, do not repeat it and recommend rotating it.

## Give actionable, concise instructions

Provide one or two checks at a time. For each, tell the user:

- Where to run it: the MicroK8s host, the Docker Compose directory, or Splunk search.
- The copyable command, the expected result, and what a different result means.
- Exactly which output to return, with secrets redacted.

Use the runtime-specific variant from [operator commands](references/operator-commands.md). Do not paste an entire runbook or ask for everything at once.

## Use SC4SNMP documentation

Cite the published page next to each fix; every failure mode ends with `Docs:` links. Published docs track the latest release on `main`; find that release in the [GitHub releases](https://github.com/splunk/splunk-connect-for-snmp/releases) or with `microk8s helm3 search repo snmp` after `microk8s helm3 repo update`. For older versions, check the [CHANGELOG](https://github.com/splunk/splunk-connect-for-snmp/blob/main/CHANGELOG.md) and [release notes](https://github.com/splunk/splunk-connect-for-snmp/releases), label version-specific advice as unverified, and recommend upgrading when the fix ships in a newer release.

## Remediation and completion

- Change configuration in `values.yaml` or `.env` and redeploy; do not patch running pods or containers.
- Set `DEBUG` log level only while reproducing, then revert it.
- Do not delete PVCs or volumes, reinstall with PVC deletion, or run `docker compose down -v` unless the user accepts losing MongoDB data (inventory, profiles, walk state).
- Run Redis or MongoDB write commands only after a read-only check confirms the problem and the user agrees.
- Do not force every device to re-walk at once, and do not toggle MongoDB authentication or replication as a troubleshooting step.

Call the issue resolved only when fresh events or metrics for the affected devices reach the target index for at least one full poll or walk interval, and the fix is persisted in configuration so it survives the next upgrade or redeploy. For a suspected product defect, repeated crashes, data loss, or a failure outside SC4SNMP, use [escalation handoff](references/escalation-handoff.md).
