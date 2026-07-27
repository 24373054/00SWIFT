from fastapi import APIRouter

from .approval_api import create_pending_approval, decide_approval

approval_router = APIRouter(prefix="/production/v1")
approval_router.add_api_route("/approvals", create_pending_approval, methods=["POST"])
approval_router.add_api_route("/approvals/{approval_id}/decisions", decide_approval, methods=["POST"])
