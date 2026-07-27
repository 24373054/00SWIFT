"""GL bridge contract with explicit outbound acknowledgement states."""

from __future__ import annotations

from dataclasses import dataclass

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
