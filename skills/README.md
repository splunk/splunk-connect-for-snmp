# SC4SNMP AI agent skills

This folder contains AI agent skills for Splunk Connect for SNMP. It sits outside `docs/`, so it is not published with the documentation site.

## troubleshoot-sc4snmp

Helps Support and On-Call engineers troubleshoot SC4SNMP escalations on MicroK8s or Docker Compose. The skill:

- asks for the minimum evidence first (runtime, version, symptom and scope, recent change, one error line)
- routes the symptom to a known failure mode with step-by-step checks
- gives copyable, read-only commands with the expected result and what to return
- links each fix to the published SC4SNMP documentation
- prepares an escalation handoff with a capture checklist and template
- never asks for tokens, community strings, SNMPv3 keys, or passwords

```text
troubleshoot-sc4snmp/
├── SKILL.md                         # entry point: scope, evidence, interaction rules
├── agents/openai.yaml               # display metadata for Codex-style agents
└── references/
    ├── failure-modes.md             # symptom -> checks -> fix, with Docs links
    ├── operator-commands.md         # MicroK8s and Docker Compose commands per check
    └── escalation-handoff.md        # when to escalate, capture checklist, handoff template
```

## Install

- **Claude Code:** copy or symlink the skill into a skills directory, then start a new session.

  ```bash
  mkdir -p ~/.claude/skills
  ln -s "$(pwd)/skills/troubleshoot-sc4snmp" ~/.claude/skills/troubleshoot-sc4snmp
  ```

  For a single project, use `<project>/.claude/skills/` instead of `~/.claude/skills/`.
- **Codex:** link the folder into `~/.codex/skills/`. `agents/openai.yaml` provides the display name and default prompt.
- **Other agents:** point the agent at `skills/troubleshoot-sc4snmp/SKILL.md`. It links to the files in `references/` with relative paths.

## Example prompts

- `SC4SNMP walk keeps retrying with "Empty SNMP response message" for 10.1.2.3`
- `No traps reach Splunk from our routers, SC4SNMP runs on MicroK8s`
- `SNMPv3 polling fails with "Wrong SNMP PDU digest" after we rotated credentials`
- `UI is enabled and helm upgrade with a new inventory has no effect`
- `MongoDB container exits with code 139 after a kernel update`
- `Prepare an escalation for this issue`

## Maintenance

- Update `references/failure-modes.md` and `references/operator-commands.md` whenever these change: `docs/troubleshooting/`, `values.yaml` keys in `charts/splunk-connect-for-snmp/values.yaml`, `.env` variables in `docker_compose/.env`, or resource names.
- Keep every link public: the published docs, the GitHub repository, the Splunk Support Portal, or the community Slack. Do not add internal wiki, ticketing, or chat links, or people's names.
- Keep commands read-only by default. Mark any command that changes the deployment, and gate it on user confirmation.
