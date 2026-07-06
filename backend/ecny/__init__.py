"""Digital yuan (e-CNY) cross-border payment system.

Layers:
* ledger/      — centralized double-entry ledger engine
* wallet/      — DC/EP wallet grading (tier 1/2/3, controlled anonymity)
* issuance/    — central bank mint/burn + operator <-> wallet exchange
* bridge/      — mBridge multi-CBDC + CIPS bilateral channels
* compliance/  — KYC / AML / regulatory reporting hooks
"""
