"""Next-generation standards and runtime API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from nextgen.runtime import IdempotencyConflict, IdempotencyService, OutboxService
from nextgen.standards import (
    build_iso20022_xml,
    finding_dicts,
    list_profiles,
    parse_iso20022_xml,
    run_conformance,
    validate_message,
)

router = APIRouter(prefix="/nextgen/v1", tags=["NextGen"])


class ValidateRequest(BaseModel):
    profile: str
    message_type: str
    payload: dict[str, Any] | None = None
    xml: str | None = None


class BuildRequest(BaseModel):
    message_type: str
    payload: dict[str, Any]


class Vector(BaseModel):
    name: str
    profile: str
    message_type: str
    payload: dict[str, Any]
    expected_valid: bool


class ConformanceRequest(BaseModel):
    vectors: list[Vector] = Field(min_length=1, max_length=1000)


class OutboxRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    aggregate_id: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any]


@router.get("/standards/profiles")
def profiles():
    return {"profiles": list_profiles()}


@router.post("/standards/validate")
def validate(request: ValidateRequest):
    payload = request.payload
    if request.xml:
        payload = parse_iso20022_xml(request.xml)
    if payload is None:
        raise HTTPException(422, "payload or xml is required")
    findings = validate_message(request.profile, request.message_type, payload)
    return {
        "valid": not any(item.severity == "error" for item in findings),
        "findings": finding_dicts(findings),
    }


@router.post("/standards/build")
def build(request: BuildRequest):
    return {"xml": build_iso20022_xml(request.message_type, request.payload)}


@router.post("/standards/conformance")
def conformance(request: ConformanceRequest):
    return run_conformance([item.model_dump() for item in request.vectors])


@router.post("/runtime/outbox")
def enqueue_outbox(
    request: OutboxRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    idempotency = IdempotencyService(db)
    try:
        record, replay = idempotency.begin(idempotency_key, request.model_dump())
    except IdempotencyConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    if replay and record.status == "completed":
        return json.loads(record.response_body or "{}")
    event = OutboxService(db).enqueue(request.topic, request.aggregate_id, request.payload)
    response = {"event_id": event.event_id, "status": event.status, "replayed": replay}
    idempotency.complete(record, 200, response)
    db.commit()
    return response
