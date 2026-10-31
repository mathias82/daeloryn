# Opt-in task-aware model routing for Copilot CLI

`model_router.py` selects a requested model from a live Copilot runtime catalog,
then can launch one CLI task with an explicit model and Daeloryn agent. It does
not change IDE/global settings, install software automatically or grant permissions.
Copilot already provides its own Auto selection; this utility adds a separately
reviewable Daeloryn policy, not a claim that routing is unique or superior.

## Policy

- `auto` is conservative: a clearly lightweight translation/rephrasing/summary task
  without engineering/risk terms uses the small tier. Ambiguous tasks default to code.
- `small` prefers available Haiku, then Sonnet. `code`, `review`, `security` and
  `architecture` prefer available Sonnet, then Opus. These are operator policy
  preferences, not measured quality or price guarantees for every family/version.
- Recognized financial/security/retry/concurrency indicators (including selected
  Greek terms) or a declared previous failure exclude Haiku from the small tier.
  A previous failure prefers Opus, then Sonnet; it never automatically replays a task.
- Only IDs in the returned catalog (excluding explicit disabled/unconfigured policies) and optional exact `--allowed-model` allowlist
  can be selected. Within a family the runtime's catalog order is retained; no
  version ID, pricing or "latest/best model" is invented. No matching model stops.
- Prompt heuristics are incomplete. The operator owns task/risk classification and
  can set `--kind` explicitly. This is not an AST/security classifier or an authority
  to downgrade security-sensitive work based on a small diff.

Discovery is a point-in-time catalog, not a guarantee of quota, organizational
permission, capabilities or successful invocation. The native host validates the
actual request. If it rejects the request, the router does not retry or switch
models silently. Do not use Haiku/Sonnet policy with the OpenAI-only Responses
adapter; provider availability and credentials are separate.

## Discovery and dry run

Requires an already installed/authenticated `copilot` executable and an optional
compatible `github-copilot-sdk` exposing `CopilotClient`, `RuntimeConnection.for_stdio`
and `list_models()`. Provision/review that SDK explicitly in your own environment.
The router uses the explicit installed CLI path, rather than asking the SDK to
fetch its default runtime. SDK/CLI version compatibility remains required.

Save the task in an operator-owned UTF-8 file, then run from the tools checkout:

```bash
python3 scripts/model_router.py --discover-copilot --kind auto \
  --prompt-file /private/task.txt
```

This lists/discovers models and prints a routing decision without sending a task
for inference. It uses the existing host authentication and makes no login changes.
Catalog access can use the network. Prompt text is not printed in the decision;
only its hash, selection time, catalog hash, requested model and reasons are emitted.

For policy tests without credentials, use `--models-json /private/models.json`
with an array of model IDs or objects having `id` and optional boolean
`enabled`/`available`. This offline catalog is marked as operator-supplied and cannot
be used with `--execute`; the utility will not pretend it queried a host.

## Explicit execution

```bash
python3 scripts/model_router.py --discover-copilot --kind code \
  --prompt-file /private/task.txt \
  --project /path/to/project --agent java-developer --execute
```

Use `--allowed-model EXACT_ID` repeatedly to restrict acceptable models. The agent
must already be installed in the target host project. The router runs shell-free
argv with `--model`, `--agent`, `--prompt`, preserving native host permissions and
interactive approvals. It does not automatically install definitions or approve
commands, change directory outside the explicit project, commit or deploy.
Native Copilot/agent tools can edit/run code under their existing permissions;
this is not the data-only Responses adapter or a sandbox.

The printed selection is **requested**, not proof of the effective provider model.
The router deliberately reports `actual_model=not_verified_by_router`: retain the
native Copilot execution timeline/model record to verify it, particularly when
agent profiles, personal overrides or host routing policies apply. CLI exit 0
means that the host task completed, not that tests passed or code is accepted.
There is no execution deadline/cost cap on a native CLI session in this utility;
use a host/operator-controlled session budget. Repair stage budgets are separate.
A failed/interrupted launch is not automatically retried: edits or remote effects
may already have occurred. Review/reconcile before a new attempt.

## Validation

Offline tests cover policy selection, exclusion of small models for recognized
risk/failed attempts, allowlists, unavailable/unknown catalog entries, mocked SDK
lifecycle, no discovery retry, opt-in and single shell-free launch. Live SDK/CLI
catalog access, effective model selection and cost savings have not been validated
in the development environment. No Copilot CLI or provider credentials were available.

Primary interfaces consulted:
- https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/choose-a-model
- https://docs.github.com/en/copilot/concepts/models/auto-model-selection
- https://github.com/github/copilot-sdk/blob/main/python/README.md
