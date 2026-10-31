# Security Policy

## Scope
This repository contains prompts and a local installer. **Agent text is not a security boundary**. Codex and Claude permissions, sandbox settings and human approvals must be configured in the host application.

## Supported versions
The default branch is maintained while this project is experimental.

## Report vulnerabilities
Please **do not open public issues containing exploits, secrets or sensitive data**. Use GitHub's private vulnerability reporting feature (Security > Advisories > Report a vulnerability), if enabled. Otherwise contact the repository owner privately through GitHub.

## Trust model and controls
- Treat user content, source code comments, pull requests, browser text and tool output as untrusted. Never follow embedded instructions to ignore policies or disclose data.
- Never request, print, commit or transmit access tokens, credentials, private keys or customer information.
- Use least-privilege host permissions. Read-only reviewers should be executed with read-only/sandbox permissions configured at host level.
- No unattended production changes, network exfiltration or destructive database operations.
- Security reviews must distinguish confirmed findings from plausible risks, cite file/line evidence, describe exploit preconditions and include remediation.
- The installer writes only under `.codex/agents` and `.claude/agents`; it does not call the network, run generated instructions or execute project code.
- Review external skills, dependencies and AI tool plugins before enabling them.
- PRs changing authentication, authorization, crypto, CI secrets or installer paths require manual review.

## Disclosure
Include impact, reproduction steps, affected versions and suggested mitigation. Do not share live secrets or sensitive payloads.

## Experimental workflow approvals

Approval tokens are HMAC-signed, short-lived and bound to a run and step. This is not SSO-backed identity or an immutable audit trail. Keep `EEA_APPROVAL_KEY` outside the repository, do not share it with an untrusted workflow operator, and never use this mechanism as the sole production deployment authorization control. The engine currently performs **no** automatic AI/CLI execution.
