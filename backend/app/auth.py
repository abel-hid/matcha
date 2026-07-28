from datetime import datetime

import psycopg2
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from app import models
from app.utils import (
    send_password_reset_email,
    send_verification_email,
    verify_reset_token,
    verify_verification_token,
)
from app.validation import (
    normalize_email,
    validate_password,
    validate_registration_data,
    validate_username,
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_NEUTRAL_VERIFICATION_MESSAGE = (
    'If the account exists and still needs verification, a verification email has been sent'
)
_NEUTRAL_RESET_MESSAGE = 'Password reset email sent if account exists'


def get_current_user_or_404():
    """Helper: resolve the JWT identity (always a string) back to a user row."""
    user_id = get_jwt_identity()
    if user_id is None:
        return None

    try:
        return models.get_user_by_id(int(user_id))
    except (TypeError, ValueError):
        return None


def attach_session_cookies(response, user):
    expires_at = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
    session_id = models.create_session(user['id'], expires_at)
    access_token, refresh_token = models.get_tokens_for_user(user, session_id)

    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response


def json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    return data


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'user': models.user_to_dict(user, include_private=True)}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    registration, error = validate_registration_data(json_object())
    if error:
        return jsonify({'message': error}), 400

    if models.get_user_by_username(registration['username']):
        return jsonify({'message': 'Username already exists'}), 409

    if models.get_user_by_email(registration['email']):
        return jsonify({'message': 'Email already registered'}), 409

    try:
        user = models.create_user(**registration)
    except psycopg2.errors.UniqueViolation:
        return jsonify({'message': 'Username or email already exists'}), 409

    try:
        send_verification_email(user)
    except Exception:
        current_app.logger.exception('Failed to send registration verification email')
        try:
            models.delete_user(user['id'])
        except Exception:
            current_app.logger.exception('Failed to remove user after email delivery failure')
        return jsonify({
            'message': 'Registration could not be completed because the verification email failed'
        }), 503

    return jsonify({
        'message': 'User registered successfully. Please verify your email.',
        'user': models.user_to_dict(user),
    }), 201


@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    payload, reason = verify_verification_token(token)
    if not payload:
        message = (
            'This verification link has expired'
            if reason == 'expired'
            else 'This verification link is invalid'
        )
        return jsonify({'message': message, 'reason': reason}), 400

    user = models.get_user_by_id(payload['user_id'])
    if not user or user['email'] != payload['email']:
        return jsonify({'message': 'This verification link is invalid', 'reason': 'invalid'}), 400

    if user['is_verified']:
        return jsonify({'message': 'Email already verified', 'reason': 'used'}), 400

    models.update_user_fields(user['id'], {'is_verified': True})

    return jsonify({'message': 'Email verified successfully'}), 200


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    data = json_object()
    if data is None:
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    email, error = normalize_email(data.get('email'))
    if error:
        return jsonify({'message': error}), 400

    user = models.get_user_by_email(email)
    if user and not user['is_verified']:
        try:
            send_verification_email(user)
        except Exception:
            current_app.logger.exception('Failed to resend verification email')

    return jsonify({'message': _NEUTRAL_VERIFICATION_MESSAGE}), 200


@auth_bp.route('/login', methods=['POST'])
def login():
    data = json_object()
    if data is None:
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    username, error = validate_username(data.get('username'))
    password = data.get('password')
    if error or not isinstance(password, str) or not password:
        return jsonify({'message': 'Username and password are required'}), 400
    if len(password.encode('utf-8')) > 72:
        return jsonify({'message': 'Invalid credentials'}), 401

    user = models.get_user_by_username(username)

    if not user or not models.check_password(password, user['password_hash']):
        return jsonify({'message': 'Invalid credentials'}), 401

    if not user['is_verified']:
        return jsonify({'message': 'Please verify your email first'}), 401

    response = jsonify({
        'message': 'Logged in successfully',
        'user': models.user_to_dict(user, include_private=True),
    })
    return attach_session_cookies(response, user), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    claims = get_jwt()
    session_id = claims.get('sid')
    models.touch_session(session_id)

    access_token = create_access_token(
        identity=str(user['id']),
        additional_claims={
            'sid': session_id,
            'ver': user['token_version'],
        },
    )
    response = jsonify({'message': 'Authentication session refreshed'})
    set_access_cookies(response, access_token)
    return response, 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    session_id = get_jwt().get('sid')
    models.revoke_session(session_id)

    from app.sockets import disconnect_session
    disconnect_session(session_id)

    response = jsonify({'message': 'Logged out successfully'})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = json_object()
    if data is None:
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    email, error = normalize_email(data.get('email'))
    if error:
        return jsonify({'message': error}), 400

    user = models.get_user_by_email(email)
    if user:
        try:
            send_password_reset_email(user)
        except Exception:
            current_app.logger.exception('Failed to send password reset email')

    return jsonify({'message': _NEUTRAL_RESET_MESSAGE}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = json_object()
    if data is None:
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    token = data.get('token')
    new_password = data.get('password')
    if not isinstance(token, str) or not token or not isinstance(new_password, str):
        return jsonify({'message': 'Token and password are required'}), 400

    payload, reason = verify_reset_token(token)
    if not payload:
        message = 'This reset link has expired' if reason == 'expired' else 'This reset link is invalid'
        return jsonify({'message': message, 'reason': reason}), 400

    user = models.get_user_by_email(payload.get('email'))
    if not user:
        return jsonify({'message': 'This reset link is invalid', 'reason': 'invalid'}), 400

    if payload.get('v') != user['token_version']:
        return jsonify({
            'message': 'This reset link has already been used',
            'reason': 'used',
        }), 400

    is_valid, error = validate_password(
        new_password,
        account_values=[
            user['username'],
            user['email'],
            user['first_name'],
            user['last_name'],
        ],
    )
    if not is_valid:
        return jsonify({'message': error}), 400

    models.reset_password_and_revoke_sessions(
        user['id'],
        new_password,
        user['token_version'] + 1,
    )

    from app.sockets import disconnect_user
    disconnect_user(user['id'])

    response = jsonify({'message': 'Password reset successfully'})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.route('/verify-reset-token/<token>', methods=['GET'])
def verify_reset_token_route(token):
    payload, reason = verify_reset_token(token)
    if not payload:
        return jsonify({'valid': False, 'reason': reason}), 400

    user = models.get_user_by_email(payload.get('email'))
    if not user:
        return jsonify({'valid': False, 'reason': 'invalid'}), 400

    if payload.get('v') != user['token_version']:
        return jsonify({'valid': False, 'reason': 'used'}), 400

    return jsonify({'valid': True}), 200
