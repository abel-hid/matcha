"""Shared Flask extension instances and JWT session validation callbacks."""

from flask import jsonify
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_cors import CORS

jwt = JWTManager()
mail = Mail()
cors = CORS()


@jwt.token_in_blocklist_loader
def token_is_revoked(jwt_header, jwt_payload):
    """Reject JWTs whose server-side session or token version is no longer active."""
    from app import models

    try:
        user_id = int(jwt_payload.get('sub'))
    except (TypeError, ValueError):
        return True

    return not models.is_session_active(
        jwt_payload.get('sid'),
        user_id,
        jwt_payload.get('ver'),
    )


@jwt.unauthorized_loader
def missing_token(reason):
    """Return the normalized response for a missing authentication cookie."""
    return jsonify({'message': 'Authentication required'}), 401


@jwt.invalid_token_loader
def invalid_token(reason):
    """Return the normalized response for a malformed authentication token."""
    return jsonify({'message': 'Invalid authentication session'}), 401


@jwt.expired_token_loader
def expired_token(jwt_header, jwt_payload):
    """Return the normalized response for an expired authentication token."""
    return jsonify({'message': 'Authentication session expired'}), 401


@jwt.revoked_token_loader
def revoked_token(jwt_header, jwt_payload):
    """Return the normalized response for a revoked authentication session."""
    return jsonify({'message': 'Authentication session is no longer valid'}), 401
