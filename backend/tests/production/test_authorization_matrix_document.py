from __future__ import annotations

import re
from pathlib import Path


def test_every_production_route_is_present_in_authorization_matrix():
    router = Path(__file__).parents[2] / "production" / "router.py"
    matrix = Path(__file__).parents[3] / "docs" / "security" / "PRODUCTION_API_AUTHORIZATION_MATRIX.md"
    source = router.read_text(encoding="utf-8")
    document = matrix.read_text(encoding="utf-8")
    routes = set(re.findall(r'@router\.(?:get|post|put|patch|delete)\("([^"]+)"', source))
    documented = set(re.findall(r'\| `([^`]+)` \| (?:GET|POST|PUT|PATCH|DELETE)', document))
    assert routes <= documented
    assert len(routes) >= 27
