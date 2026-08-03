"""Authentication routes for registration, verification, sessions, logout, and password recovery."""

from datetime import datetime

import psycopg2
from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    jwt_required,
    set_access_cookies,
    verify_jwt_in_request,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError

from app import models
from app.request_helpers import get_authenticated_user, json_object
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


def attach_session_cookies(response, user):
    """Set access and refresh JWT cookies on an authentication response."""
    expires_at = datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
    session_id = models.create_session(user['id'], expires_at)
    access_token, refresh_token = models.get_tokens_for_user(user, session_id)

    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route('/refresh/bootstrap', methods=['POST'])
def bootstrap_session():
    """Restore an authenticated browser session without producing an expected 401 probe."""
    try:
        verify_jwt_in_request(refresh=True)
    except (JWTExtendedException, PyJWTError):
        response = jsonify({
            'authenticated': False,
            'user': None,
        })
        unset_jwt_cookies(response)
        return response, 200

    user = get_authenticated_user()
    if not user:
        response = jsonify({
            'authenticated': False,
            'user': None,
        })
        unset_jwt_cookies(response)
        return response, 200

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
    response = jsonify({
        'authenticated': True,
        'user': models.user_to_dict(user, include_private=True),
    })
    set_access_cookies(response, access_token)
    return response, 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Return the private profile for the authenticated session."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'user': models.user_to_dict(user, include_private=True)}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    """Validate registration data, create the account, and send verification email."""
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
    """Verify a unique email token and activate the account."""
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
    """Issue a new verification email without exposing account existence."""
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
    """Authenticate credentials and create a revocable server-side session."""
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
    """Rotate an active refresh session and return fresh authentication cookies."""
    user = get_authenticated_user()
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
    """Revoke the current session and clear all authentication cookies."""
    session_id = get_jwt().get('sid')
    models.revoke_session(session_id)

    from app.sockets import disconnect_session
    disconnect_session(session_id)

    response = jsonify({'message': 'Logged out successfully'})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Send a reset link while returning the same response for unknown addresses."""
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
    """Validate a reset token, replace the password, and revoke old sessions."""
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
    """Check whether a password-reset token remains valid."""
    payload, reason = verify_reset_token(token)
    if not payload:
        return jsonify({'valid': False, 'reason': reason}), 400

    user = models.get_user_by_email(payload.get('email'))
    if not user:
        return jsonify({'valid': False, 'reason': 'invalid'}), 400

    if payload.get('v') != user['token_version']:
        return jsonify({'valid': False, 'reason': 'used'}), 400

    return jsonify({'valid': True}), 200
