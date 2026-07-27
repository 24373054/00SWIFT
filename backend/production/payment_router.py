"""Payment and value-movement route registration."""

from fastapi import APIRouter

from .router import (
    accept_quote,
    cancellation_request,
    create_payment,
    get_payment,
    get_payment_facts,
    list_payments,
    open_investigation_case,
    request_quote,
    return_request,
)

payment_router = APIRouter(prefix="/production/v1")
payment_router.add_api_route("/payments", create_payment, methods=["POST"], status_code=202)
payment_router.add_api_route("/payments", list_payments, methods=["GET"])
payment_router.add_api_route("/payments/{order_id}", get_payment, methods=["GET"])
payment_router.add_api_route("/payments/{order_id}/facts", get_payment_facts, methods=["GET"])
payment_router.add_api_route("/payments/{order_id}/investigation-cases", open_investigation_case, methods=["POST"])
payment_router.add_api_route("/fx-quotes", request_quote, methods=["POST"])
payment_router.add_api_route("/payments/{order_id}/fx-acceptance-intents", accept_quote, methods=["POST"], status_code=202)
payment_router.add_api_route("/payments/{order_id}/cancellation-requests", cancellation_request, methods=["POST"], status_code=202)
payment_router.add_api_route("/payments/{order_id}/return-requests", return_request, methods=["POST"], status_code=202)
