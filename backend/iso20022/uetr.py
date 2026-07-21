"""UETR (Unique End-to-end Transaction Reference) helpers.

A UETR is a UUID v4 that follows a payment through its full lifecycle.
"""

import uuid


def generate_uetr() -> str:
    return str(uuid.uuid4())


def validate_uetr(uetr: str) -> bool:
    try:
        uuid.UUID(uetr)
        return True
    except (ValueError, TypeError):
        return False
