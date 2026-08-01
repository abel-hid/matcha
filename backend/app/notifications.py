from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import models
from app.profile_access import complete_profile_required

notifications_bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


def get_current_user_or_404():
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return models.get_user_by_id(int(user_id))


@notifications_bp.route('', methods=['GET'])
@jwt_required()
@complete_profile_required
def list_notifications():
    user = get_current_user_or_404()
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
    """Lightweight endpoint for the polling badge — avoids shipping the full list every 8s."""
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({'unreadCount': models.count_unread_notifications(user['id'])}), 200


@notifications_bp.route('/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
@complete_profile_required
def mark_read(notification_id):
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    models.mark_notification_read(notification_id, user['id'])
    return jsonify({'unreadCount': models.count_unread_notifications(user['id'])}), 200


@notifications_bp.route('/read-all', methods=['PUT'])
@jwt_required()
@complete_profile_required
def mark_all_read():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    models.mark_all_notifications_read(user['id'])
    return jsonify({'unreadCount': 0}), 200