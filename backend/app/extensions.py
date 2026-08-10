from flask import jsonify
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_cors import CORS

jwt = JWTManager()
mail = Mail()
cors = CORS()


@jwt.token_in_blocklist_loader
def token_is_revoked(jwt_header, jwt_payload):
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
    return jsonify({'message': 'Authentication required'}), 401


@jwt.invalid_token_loader
def invalid_token(reason):
    return jsonify({'message': 'Invalid authentication session'}), 401


@jwt.expired_token_loader
def expired_token(jwt_header, jwt_payload):
    return jsonify({'message': 'Authentication session expired'}), 401


@jwt.revoked_token_loader
def revoked_token(jwt_header, jwt_payload):
    return jsonify({'message': 'Authentication session is no longer valid'}), 401
