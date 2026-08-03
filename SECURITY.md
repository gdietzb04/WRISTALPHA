# Security policy

## Reporting

Do not disclose a suspected vulnerability in a public issue. Use GitHub private vulnerability
reporting for this repository. If that channel is unavailable, contact the repository owner
privately and include reproduction steps, affected versions, and potential impact without
including real credentials or personal data.

## Deployment invariants

- Release actions are pinned to immutable commit SHAs.
- Release containers must have repository-linked provenance attestations.
- Secrets must not be committed, printed, passed on command lines, or embedded in images.
- Host ports remain bound to loopback unless a separately reviewed authentication and network
  boundary is introduced.
- Raw acquisition data remains immutable, and asks or delistings never become verified sales.
- Data-quality and statistical validation gates fail closed and may not be bypassed by deployment
  tooling.

Security changes must preserve these invariants and pass the repository CI checks.
