"""Small request helpers shared by route modules."""

from flask import request
from flask_jwt_extended import get_jwt_identity

from app import models


def get_authenticated_user():
    """Resolve the JWT identity to a user row, returning None for invalid sessions."""
    identity = get_jwt_identity()
    try:
        return models.get_user_by_id(int(identity)) if identity is not None else None
    except (TypeError, ValueError):
        return None


def json_object():
    """Return a JSON object body, or None when the request body has another shape."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None
