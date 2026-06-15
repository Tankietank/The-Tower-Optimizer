# Security policy

## Supported versions

Only the newest preview or stable release is actively supported during early development.

## Reporting a vulnerability

Before a private reporting channel is configured, do not include secrets, real profiles, player IDs, tokens, or exploitable details in a public issue. Open a minimal issue stating that you found a security problem and request a private contact method from the repository maintainer.

Relevant issues include:

- Unsafe ZIP extraction
- Arbitrary file writes
- Update-package signature or checksum bypasses
- Exposure of local profile data
- Credential or token leakage
- Remote code execution

## Scope

Tower Optimizer does not currently require game credentials or call a private player API. Any contribution that introduces authentication, remote profile storage, or executable self-updates requires a dedicated security review.
