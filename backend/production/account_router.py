from fastapi import APIRouter

from .account_api import activate_account, create_account, create_ownership

account_router = APIRouter(prefix="/production/v1")
account_router.add_api_route("/accounts", create_account, methods=["POST"])
account_router.add_api_route("/accounts/{account_id}/ownerships", create_ownership, methods=["POST"])
account_router.add_api_route("/accounts/{account_id}/activate", activate_account, methods=["POST"])
