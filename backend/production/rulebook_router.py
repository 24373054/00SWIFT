from fastapi import APIRouter

from .rulebook_api import accept_rulebook, list_rulebooks

rulebook_router = APIRouter(prefix="/production/v1")
rulebook_router.add_api_route("/rulebooks/accept", accept_rulebook, methods=["POST"])
rulebook_router.add_api_route("/participants/{participant_id}/rulebooks", list_rulebooks, methods=["GET"])
