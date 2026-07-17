from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from datetime import datetime

from app.models import User
from app.extensions import db
from app.utils import (
    validate_password, validate_email, send_verification_email,
    verify_verification_token, send_password_reset_email, verify_reset_token
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def get_current_user_or_404():
    """Helper: resolve the JWT identity (always a string) back to a User row."""
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return User.query.get(int(user_id))


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({
        'user': user.to_dict(include_private=True)
    }), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    required_fields = ['username', 'email', 'firstName', 'lastName', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'{field} is required'}), 400

    if not validate_email(data['email']):
        return jsonify({'message': 'Invalid email address'}), 400

    is_valid, msg = validate_password(data['password'])
    if not is_valid:
        return jsonify({'message': msg}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400

    user = User(
        username=data['username'],
        email=data['email'],
        first_name=data['firstName'],
        last_name=data['lastName']
    )
    user.set_password(data['password'])
    user.sexual_preferences = data.get('sexualPreferences', 'bisexual')
    user.gender = data.get('gender', '')

    db.session.add(user)
    db.session.commit()

    try:
        send_verification_email(user) 
    except Exception as e:
        print(f"Email error: {e}")

    return jsonify({
        'message': 'User registered successfully. Please verify your email.',
        'user': user.to_dict()
    }), 201


@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    email = verify_verification_token(token)
    if not email:
        return jsonify({'message': 'Invalid or expired verification token'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if user.is_verified:
        return jsonify({'message': 'Email already verified'}), 400

    user.is_verified = True
    db.session.commit()

    return jsonify({'message': 'Email verified successfully'}), 200


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if user.is_verified:
        return jsonify({'message': 'Email already verified'}), 400

    try:
        send_verification_email(user)
    except Exception:
        return jsonify({'message': 'Failed to send email'}), 500

    return jsonify({'message': 'Verification email sent'}), 200


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password required'}), 400

    user = User.query.filter_by(username=data['username']).first()

    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401

    # Uncomment when email verification is fully set up
    if not user.is_verified:
        return jsonify({'message': 'Please verify your email first'}), 401

    # Update online status
    user.is_online = True
    user.last_activity = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'token': create_access_token(identity=str(user.id)),
        'refreshToken': create_refresh_token(identity=str(user.id)),
        'user': user.to_dict(include_private=True)
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({
        'token': create_access_token(identity=str(user.id))
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    user = get_current_user_or_404()

    if user:
        user.is_online = False
        user.last_activity = datetime.utcnow()
        db.session.commit()

    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Password reset email sent if account exists'}), 200

    try:
        send_password_reset_email(user)
    except Exception as e:
        print(f"[forgot-password] failed to send email to {user.email}: {e}")
        return jsonify({'message': 'Failed to send email'}), 500

    return jsonify({'message': 'Password reset email sent'}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
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

    user = User.query.filter_by(email=payload['email']).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if payload.get('v') != user.token_version:
        return jsonify({
            'message': 'This reset link has already been used',
            'reason': 'used'
        }), 400

    user.set_password(new_password)
    user.token_version += 1
    db.session.commit()

    return jsonify({'message': 'Password reset successfully'}), 200



@auth_bp.route('/verify-reset-token/<token>', methods=['GET'])
def verify_reset_token_route(token):
    payload, reason = verify_reset_token(token)
    if not payload:
        return jsonify({'valid': False, 'reason': reason}), 400

    user = User.query.filter_by(email=payload['email']).first()
    if not user:
        return jsonify({'valid': False, 'reason': 'invalid'}), 400

    if payload.get('v') != user.token_version:
        return jsonify({'valid': False, 'reason': 'used'}), 400

    return jsonify({'valid': True}), 200