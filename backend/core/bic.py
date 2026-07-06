"""BIC (Bank Identifier Code) validation.

SWIFT uses two BIC patterns depending on context:

* The ``x-bic`` HTTP header on Pre-validation endpoints is **lowercase** and
  uses the official SWIFT header pattern (no branch code):
  ``^[a-z]{6,6}[a-z2-9][a-np-z0-9]$`` — e.g. ``swhqbebb``.
* SwiftRef data lookups (``GET /bics/{bic}``) use the **uppercase** 8-or-11
  character BICFI pattern: ``^[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?$``.

The old prototype's ``iso20022.validate_bic`` used ``^[A-Z]{6}[A-Z0-9]{2}(...)?$``
which is too loose — it allows ``1``/``O`` in positions 7-8, which the official
pattern forbids (position 7 is ``[A-Z2-9]`` — no ``0``/``1``/``O``; position 8
is ``[A-NP-Z0-9]`` — no ``O``).
"""

import re
from typing import Literal

# Lowercase, no branch code — used for the `x-bic` request header on Pre-validation.
HEADER_BIC_RE = re.compile(r"^[a-z]{6,6}[a-z2-9][a-np-z0-9]$")

# Uppercase, 8 or 11 chars — used for SwiftRef data lookups and message BICFI fields.
DATA_BIC_RE = re.compile(r"^[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?$")

BicMode = Literal["header", "data"]


def validate_bic(bic: str, mode: BicMode = "data") -> bool:
    """Validate a BIC against the official SWIFT pattern.

    Args:
        bic: The BIC string to validate.
        mode: ``"header"`` for the lowercase x-bic header (8 chars, no branch),
            ``"data"`` for the uppercase BICFI (8 or 11 chars).
    """
    if not bic:
        return False
    pattern = HEADER_BIC_RE if mode == "header" else DATA_BIC_RE
    return bool(pattern.match(bic))


def normalize_bic(bic: str) -> str:
    """Uppercase a BIC for storage/lookup. Does not validate."""
    return (bic or "").upper()
