# Repository Guide

00SWIFT is a contract-aligned SWIFT-style and e-CNY payment sandbox. Read `README.md`, `docs/ARCHITECTURE.md`, and `SECURITY.md` before changing authentication, signing, ledger, or environment behavior.

## Required local gate

```bash
python -m pip install -r backend/requirements-dev.txt
make check
make coverage
make security
```

## Non-negotiable invariants

- Store money as integer minor units.
- Use posted double-entry ledger records as the source of truth.
- Never expose stored secrets or raw bearer tokens.
- Verify signatures over the exact request bytes.
- Reject replayed assertions and unauthorized scopes.
- Keep sandbox convenience paths explicitly sandbox-only.
- Add a regression test for every behavioral fix.
- Never commit `.env`, databases, generated certificates/private keys, research clones, SDK PDFs, or coverage artifacts.

## Main directories

- `backend/auth/`: OAuth, signing, JTI replay protection, dependencies.
- `backend/api/`: SWIFT-style and e-CNY route contracts.
- `backend/ecny/`: ledger, wallets, issuance, bridges, and compliance hooks.
- `backend/core/`: shared errors, middleware, security helpers, BIC/IBAN utilities.
- `backend/tests/`: isolated unit and API integration tests.
- `frontend/`: static sandbox UI.
- `docs/`: architecture, API, operations, threat model, and release guidance.
- `.github/workflows/`: CI, CodeQL, dependency audit, and release validation.
