"""GL bridge contract with explicit outbound acknowledgement states."""

from __future__ import annotations

from dataclasses import dataclass
import json

from .models import ProductionGlBatch, ProductionGlReceipt
from .runtime import ProductionConflict, digest


@dataclass(frozen=True)
class GlBatchPayload:
    batch_id: str
    mapping_version: str
    journal_ids: tuple[str, ...]
    payload_hash: str


class GlBridge:
    """Builds deterministic batches; transport ACK is an injected boundary."""

    def build_batch(self, batch_id: str, journal_ids: list[str], mapping_version: str) -> GlBatchPayload:
        if not journal_ids or not mapping_version:
            raise ProductionConflict("GL batch requires journals and mapping version")
        ordered = tuple(sorted(set(journal_ids)))
        return GlBatchPayload(batch_id, mapping_version, ordered, digest({"batch_id": batch_id, "mapping_version": mapping_version, "journal_ids": ordered}))

    def acknowledge(self, state: str, receipt_hash: str | None = None) -> dict:
        if state not in {"ACK", "REJECTED"}:
            raise ProductionConflict("GL bridge requires explicit ACK or REJECTED")
        if state == "ACK" and not receipt_hash:
            raise ProductionConflict("GL ACK requires receipt hash")
        return {"state": state, "receipt_hash": receipt_hash}

    def persist_batch(self, db, *, batch_id: str, tenant_id: str, mapping_version: str, journal_ids: list[str], debit_total_minor: int, credit_total_minor: int) -> ProductionGlBatch:
        payload = self.build_batch(batch_id, journal_ids, mapping_version)
        if debit_total_minor != credit_total_minor:
            raise ProductionConflict("GL batch totals are not balanced")
        batch = ProductionGlBatch(batch_id=batch_id, tenant_id=tenant_id, mapping_version=mapping_version, journal_scope=json.dumps(payload.journal_ids), debit_total_minor=debit_total_minor, credit_total_minor=credit_total_minor, payload_hash=payload.payload_hash, state="SENT")
        db.add(batch)
        db.flush()
        return batch

    def record_receipt(self, db, *, receipt_id: str, tenant_id: str, batch_id: str, state: str, receipt_hash: str) -> ProductionGlReceipt:
        self.acknowledge(state, receipt_hash if state == "ACK" else None)
        receipt = ProductionGlReceipt(receipt_id=receipt_id, tenant_id=tenant_id, batch_id=batch_id, state=state, receipt_hash=receipt_hash)
        db.add(receipt)
        batch = db.query(ProductionGlBatch).filter_by(batch_id=batch_id).one()
        batch.state = "ACK" if state == "ACK" else "REJECTED"
        batch.receipt_hash = receipt_hash
        db.flush()
        return receipt
