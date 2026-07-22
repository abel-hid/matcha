from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from datetime import datetime
import psycopg2

from app import models
from app.utils import (
    validate_password, validate_email, send_verification_email,
    verify_verification_token, send_password_reset_email, verify_reset_token
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def get_current_user_or_404():
    """Helper: resolve the JWT identity (always a string) back to a user row."""
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return models.get_user_by_id(int(user_id))


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'user': models.user_to_dict(user, include_private=True)}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    required_fields = ['username', 'email', 'firstName', 'lastName', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'{field} is required'}), 400

    if not validate_email(data['email']):
        return jsonify({'message': 'Invalid email address'}), 400

    is_valid, msg = validate_password(data['password'])
    if not is_valid:
        return jsonify({'message': msg}), 400

    if models.get_user_by_username(data['username']):
        return jsonify({'message': 'Username already exists'}), 400

    if models.get_user_by_email(data['email']):
        return jsonify({'message': 'Email already registered'}), 400

    try:
        user = models.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['firstName'],
            last_name=data['lastName'],
        )
    except psycopg2.errors.UniqueViolation:
        # Race condition: someone registered the same username/email between
        # our check above and the INSERT. Return a clean 400, not a 500.
        return jsonify({'message': 'Username or email already exists'}), 400

    optional_updates = {}
    if data.get('sexualPreferences'):
        optional_updates['sexual_preferences'] = data['sexualPreferences']
    else:
        optional_updates['sexual_preferences'] = 'bisexual'
    optional_updates['gender'] = data.get('gender', '')
    models.update_user_fields(user['id'], optional_updates)
    user = models.get_user_by_id(user['id'])

    try:
        send_verification_email(user)
    except Exception as e:
        print(f"Email error: {e}")

    return jsonify({
        'message': 'User registered successfully. Please verify your email.',
        'user': models.user_to_dict(user),
    }), 201


@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    email = verify_verification_token(token)
    if not email:
        return jsonify({'message': 'Invalid or expired verification token'}), 400

    user = models.get_user_by_email(email)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if user['is_verified']:
        return jsonify({'message': 'Email already verified'}), 400

    models.update_user_fields(user['id'], {'is_verified': True})

    return jsonify({'message': 'Email verified successfully'}), 200


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    data = request.get_json() or {}
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    user = models.get_user_by_email(email)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if user['is_verified']:
        return jsonify({'message': 'Email already verified'}), 400

    try:
        send_verification_email(user)
    except Exception:
        return jsonify({'message': 'Failed to send email'}), 500

    return jsonify({'message': 'Verification email sent'}), 200


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}

    if not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password required'}), 400

    user = models.get_user_by_username(data['username'])

    if not user or not models.check_password(data['password'], user['password_hash']):
        return jsonify({'message': 'Invalid credentials'}), 401

    if not user['is_verified']:
        return jsonify({'message': 'Please verify your email first'}), 401

    models.update_user_fields(user['id'], {
        'is_online': True,
        'last_activity': datetime.utcnow(),
    })
    user = models.get_user_by_id(user['id'])

    access_token, refresh_token = models.get_tokens_for_user(user['id'])

    return jsonify({
        'token': access_token,
        'refreshToken': refresh_token,
        'user': models.user_to_dict(user, include_private=True),
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({
        'token': create_access_token(identity=str(user['id']))
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    user = get_current_user_or_404()

    if user:
        models.update_user_fields(user['id'], {
            'is_online': False,
            'last_activity': datetime.utcnow(),
        })

    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    user = models.get_user_by_email(email)
    if not user:
        # Same response whether or not the account exists, so this endpoint
        # can't be used to enumerate registered emails.
        return jsonify({'message': 'Password reset email sent if account exists'}), 200

    try:
        send_password_reset_email(user)
    except Exception as e:
        print(f"[forgot-password] failed to send email to {user['email']}: {e}")
        return jsonify({'message': 'Failed to send email'}), 500

    return jsonify({'message': 'Password reset email sent'}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    token = data.get('token')
    new_password = data.get('password')

    if not token or not new_password:
        return jsonify({'message': 'Token and password are required'}), 400

    is_valid, msg = validate_password(new_password)
    if not is_valid:
        return jsonify({'message': msg}), 400

    payload, reason = verify_reset_token(token)
    if not payload:
        message = 'This reset link has expired' if reason == 'expired' else 'This reset link is invalid'
        return jsonify({'message': message, 'reason': reason}), 400

    user = models.get_user_by_email(payload['email'])
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if payload.get('v') != user['token_version']:
        return jsonify({
            'message': 'This reset link has already been used',
            'reason': 'used',
        }), 400

    models.update_user_fields(user['id'], {
        'password_hash': models.hash_password(new_password),
        'token_version': user['token_version'] + 1,
    })

    return jsonify({'message': 'Password reset successfully'}), 200


@auth_bp.route('/verify-reset-token/<token>', methods=['GET'])
def verify_reset_token_route(token):
    payload, reason = verify_reset_token(token)
    if not payload:
        return jsonify({'valid': False, 'reason': reason}), 400

    user = models.get_user_by_email(payload['email'])
    if not user:
        return jsonify({'valid': False, 'reason': 'invalid'}), 400

    if payload.get('v') != user['token_version']:
        return jsonify({'valid': False, 'reason': 'used'}), 400

    return jsonify({'valid': True}), 200