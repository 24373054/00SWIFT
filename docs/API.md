# API Integration Guide

The running OpenAPI document at `/docs` is the authoritative machine-readable inventory for the checked-out version. This guide describes authentication and the principal route families.

## Common headers

| Header | Use |
| --- | --- |
| `Authorization: Bearer <token>` | OAuth-protected endpoints |
| `X-SWIFT-Signature: <jwt>` | Signed write endpoints |
| `x-bic: <bic>` | Calling institution identity where required |
| `X-Admin-Token: <token>` | Internal administration and local e-CNY sandbox access |
| `X-Request-ID: <id>` | Optional caller correlation ID; generated when absent |
| `Content-Type: application/json` | JSON APIs |

## OAuth2 sequence

1. Create a sandbox application credential through the local admin route.
2. Store the returned consumer secret immediately; list operations will never reveal it again.
3. Sign a JWT client assertion with the generated/supplied private key. Include `iss`, `sub`, `aud`, `iat`, `exp`, and a unique `jti`, plus the certificate chain in the protected header where required.
4. Exchange the assertion at `POST /oauth2/token` using the JWT-bearer grant.
5. Request only scopes included in the application's allow-list.
6. Send the returned bearer token on protected requests.
7. Revoke through `POST /oauth2/revoke`; revocation is client-bound.

Raw access tokens are not recoverable from the database. A lost token must be reissued.

## Request signatures

Signed endpoints verify an RS256 JWT in `X-SWIFT-Signature`. The signature contains a digest derived from the exact transmitted body. Changing whitespace, encoding, fields, or body bytes after signing invalidates the request. Never reuse a signature for another request.

Use `backend/client/swift_signature.py` as a sandbox reference, not as a substitute for an official integration SDK.

## Error envelope

SWIFT-style failures use a consistent shape:

```json
{
  "errors": [
    {
      "code": "SwAP509",
      "severity": "Fatal",
      "text": "Request signature validation failed"
    }
  ]
}
```

Clients should branch on `code` and HTTP status, retain `X-Request-ID`, and avoid parsing human-readable text.

## Route families

### OAuth2 — `/oauth2`

- `POST /token`: exchange a certificate-bound client assertion for a scoped bearer token.
- `POST /revoke`: revoke a token owned by the authenticated client.

### Pre-validation — `/swift-preval/v2`

- `POST /payment/payment-instruction`: orchestrated BIC, account, country, currency, amount, and context checks.
- `POST /payment/financial-institution-identity`: BIC validation.
- `POST /payment/account-format`: account/IBAN format validation.
- `POST /payment/amount`: amount and currency minor-unit validation.

Amounts are parsed using decimal arithmetic and reject `NaN`, infinity, zero, and negatives.

### SwiftRef — `/swiftrefdata/v4`

- `GET /bics/{bic}/validity`
- `GET /bics/{bic}`
- `GET /ibans/{iban}/validity`
- `GET /ibans/{iban}/bic`
- `GET /ibans/{iban}`
- `GET /currency_codes/{code}`

Sandbox responses use local ISO/reference fixtures. They are intentionally limited and must not be treated as a current production directory.

### GPI Tracker — `/swift-apitracker/v4`

- retrieve payment transaction state by UETR;
- list changed transactions in a bounded time window;
- post status confirmations;
- request cancellation and report cancellation status.

State changes are validated against the supported ISO 20022 status set and signed where mutating.

### Messaging — `/alliancecloud/v2`

- send a FIN fixture;
- list message distributions;
- acknowledge or negatively acknowledge a distribution.

Messaging is a deterministic sandbox queue, not a SWIFT network connection.

### e-CNY — `/ecny/v1`

Principal operations:

- create/read tiered wallets;
- wallet-to-wallet transfers;
- central-bank mint/burn and operator-wallet exchange;
- cross-border settlement simulation through an automatically selected or explicit mBridge/CIPS channel;
- transaction and account-balance queries;
- compliance report queries.

Amounts use integer fen. Route scopes are split by capability: `ecny.wallet`, `ecny.issuance`, `ecny.bridge`, and `ecny.ledger`.

### Internal administration — `/api`

Creates sandbox credentials and fixtures, exposes the API catalogue/status metadata, and supports the local UI. Do not expose these routes without a separate management-plane design.

## Pagination and limits

Collection limits are clamped server-side to prevent unbounded reads. Callers should request modest pages and tolerate server-selected maximums.

## Idempotency and retries

The current sandbox protects authentication replay but does not provide a universal idempotency-key contract for every business route. Retrying a mutating request can therefore duplicate an operation unless the route's domain identifier (for example UETR) naturally de-duplicates it. Production adapters should add explicit idempotency records, bounded retry policies, and reconciliation.
