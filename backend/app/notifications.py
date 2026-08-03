"""Notification list, unread count, and read-state routes."""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app import models
from app.request_helpers import get_authenticated_user
from app.profile_access import complete_profile_required

notifications_bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


@notifications_bp.route('', methods=['GET'])
@jwt_required()
@complete_profile_required
def list_notifications():
    """Return recent notifications and the unread total."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    notifs = models.get_notifications_for_user(user['id'])
    return jsonify({
        'notifications': [models.notification_to_dict(n) for n in notifs],
        'unreadCount': models.count_unread_notifications(user['id']),
    }), 200


@notifications_bp.route('/unread-count', methods=['GET'])
@jwt_required()
@complete_profile_required
def unread_count():
    """Lightweight endpoint for the polling badge - avoids shipping the full list every 8s."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({'unreadCount': models.count_unread_notifications(user['id'])}), 200


@notifications_bp.route('/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
@complete_profile_required
def mark_read(notification_id):
    """Mark one owned notification as read and return the new unread total."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    models.mark_notification_read(notification_id, user['id'])
    return jsonify({'unreadCount': models.count_unread_notifications(user['id'])}), 200


@notifications_bp.route('/read-all', methods=['PUT'])
@jwt_required()
@complete_profile_required
def mark_all_read():
    """Mark every owned notification as read."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    models.mark_all_notifications_read(user['id'])
    return jsonify({'unreadCount': 0}), 200
