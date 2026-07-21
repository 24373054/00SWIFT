# Contributing

Thank you for improving 00SWIFT. Contributions should preserve the project's central promise: a safe, deterministic sandbox with explicit trust boundaries and auditable financial invariants.

## Before opening a change

- Use GitHub Discussions or an issue for broad architectural changes.
- Never include real credentials, private keys, institution data, or production payment records.
- Report suspected vulnerabilities privately according to [SECURITY.md](SECURITY.md).
- Keep changes focused; separate refactors from behavioral changes where possible.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
```

Run the full local gate before opening a pull request:

```bash
make check
make coverage
make security
```

## Engineering rules

1. **Money is integer-based.** Store e-CNY values in fen; do not introduce binary floating-point arithmetic.
2. **The ledger is authoritative.** Derived balances may be cached for display, but business decisions must use posted entries.
3. **Every financial transaction balances.** Debit and credit totals must match within a single database transaction.
4. **Authentication fails closed.** Convenience behavior is allowed only when explicitly limited to local sandbox mode.
5. **Secrets are non-observable.** Never log or return reusable secrets after initial issuance.
6. **Contracts stay explicit.** Validate inputs at the API boundary and keep response/error shapes stable.
7. **Tests describe regressions.** Every bug fix requires a test that fails on the previous behavior.

## Pull requests

A strong pull request includes:

- a concise problem statement and threat/compatibility impact;
- linked issues where applicable;
- tests for changed behavior and failure paths;
- documentation updates for user-facing or operational changes;
- confirmation that CI, security checks, and the Docker build pass.

Use conventional commit prefixes such as `feat:`, `fix:`, `security:`, `docs:`, `test:`, and `chore:`. Maintainers normally squash-merge pull requests.

## Review checklist

Reviewers will verify:

- authorization and scope boundaries;
- replay, signature, and secret-handling behavior;
- transaction atomicity and double-entry balance;
- error-envelope compatibility;
- test determinism and fixture isolation;
- migration and deployment implications;
- documentation and release-note completeness.

By contributing, you agree that your work is licensed under Apache-2.0 and that project interactions follow the [Code of Conduct](CODE_OF_CONDUCT.md).
