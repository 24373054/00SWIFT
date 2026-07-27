"""Dry-run-first repair for historical production tenant mismatches."""

from __future__ import annotations

import argparse
import hashlib
import json

from sqlalchemy import create_engine, text


def build_plan(connection) -> list[dict[str, str]]:
    rows = connection.execute(text(
        "SELECT o.order_id, o.tenant_id AS old_tenant, p.tenant_id AS new_tenant "
        "FROM prod_payment_orders o JOIN prod_participants p ON o.initiator_participant=p.participant_id "
        "WHERE o.tenant_id != p.tenant_id"
    )).mappings()
    return [dict(row) for row in rows]


def plan_digest(plan: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def repair(engine, *, execute: bool = False, operator: str | None = None, checker: str | None = None, evidence_id: str | None = None) -> dict[str, object]:
    with engine.begin() as connection:
        plan = build_plan(connection)
        result: dict[str, object] = {"count": len(plan), "plan": plan, "plan_hash": plan_digest(plan), "executed": False}
        if not execute:
            return result
        if not operator or not checker or not evidence_id:
            raise ValueError("execute requires operator, checker and evidence_id")
        if operator == checker:
            raise ValueError("operator and checker must be distinct")
        for item in plan:
            connection.execute(text("UPDATE prod_payment_orders SET tenant_id=:tenant WHERE order_id=:order"), {"tenant": item["new_tenant"], "order": item["order_id"]})
        result.update({"executed": True, "operator": operator, "checker": checker, "evidence_id": evidence_id})
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", default="sqlite:///swift_dev.db")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--operator")
    parser.add_argument("--checker")
    parser.add_argument("--evidence-id")
    args = parser.parse_args()
    report = repair(create_engine(args.db_url), execute=args.execute, operator=args.operator, checker=args.checker, evidence_id=args.evidence_id)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
