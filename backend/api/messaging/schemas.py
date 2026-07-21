"""Messaging API (Alliance Cloud v2) schemas.

Aligned with ``research/api-sample-code/dotnet/MessagingApi/.../SWIFT-API-Swift-Messaging-2.0.0-swagger.yaml``.
The FIN send endpoint takes a ``FinMessageEmission`` (sender_reference,
message_type, sender BIC12, receiver, base64 payload, network_info{uetr,...}).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NetworkInfo(BaseModel):
    network_priority: str = "Normal"  # Normal|Urgent|System
    uetr: str | None = None
    delivery_monitoring: str | None = None
    possible_duplicate: bool = False


class FinMessageEmission(BaseModel):
    """Body for POST /fin/messages."""

    sender_reference: str = Field(..., max_length=70)  # UUMID
    message_type: str  # e.g. fin.103, fin.202.COV, fin.999
    sender: str = Field(..., min_length=12, max_length=12)  # BIC12
    receiver: str = Field(..., min_length=12, max_length=12)  # BIC12
    payload: str  # base64 of MT block 4 text
    network_info: NetworkInfo = NetworkInfo()


class SendMessageResponse(BaseModel):
    message_cloud_reference: str
    distribution_id: str


class Distribution(BaseModel):
    distribution_id: str
    service: str
    message_type: str | None = None
    sender: str | None = None
    receiver: str | None = None
    status: str
    created_at: str


class AckNakRequest(BaseModel):
    reason: str | None = None
