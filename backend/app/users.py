from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import models

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


def get_current_user_or_404():
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return models.get_user_by_id(int(user_id))


@users_bp.route('/blocked', methods=['GET'])
@jwt_required()
def get_blocked_users():
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    blocked_users = models.get_blocked_users(current_user['id'])
    return jsonify({
        'blocks': [models.blocked_user_to_dict(user) for user in blocked_users]
    }), 200


@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_profile(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = models.get_user_by_id(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if models.is_blocked_either_way(current_user['id'], target['id']):
        return jsonify({'message': 'User not found'}), 404

    data = models.user_to_dict(target, include_private=False)
    data['hasLikedThem'] = models.has_liked(current_user['id'], target['id'])
    data['theyLikedMe'] = models.has_liked(target['id'], current_user['id'])
    data['isConnected'] = data['hasLikedThem'] and data['theyLikedMe']
    data['hasReported'] = models.has_reported(current_user['id'], target['id'])

    return jsonify({'user': data}), 200


@users_bp.route('/<int:user_id>/visit', methods=['POST'])
@jwt_required()
def record_profile_visit(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot record a visit to your own profile'}), 400

    target = models.get_user_by_id(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if models.is_blocked_either_way(current_user['id'], target['id']):
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    visit_id = data.get('visitId')
    if not isinstance(visit_id, str):
        return jsonify({'message': 'visitId must be a valid UUID'}), 400

    try:
        visit_id = str(UUID(visit_id))
    except (ValueError, AttributeError):
        return jsonify({'message': 'visitId must be a valid UUID'}), 400

    visit = models.record_view(current_user['id'], target['id'], visit_id)
    if not visit:
        return jsonify({'recorded': False}), 200

    models.create_notification(target['id'], 'view', from_user_id=current_user['id'])
    models.update_fame_rating(target['id'])

    return jsonify({
        'recorded': True,
        'visitId': visit_id,
    }), 201


@users_bp.route('/<int:user_id>/like', methods=['POST'])
@jwt_required()
def like_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot like yourself'}), 400

    target = models.get_user_by_id(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if models.is_blocked_either_way(current_user['id'], target['id']):
        return jsonify({'message': 'User not found'}), 404

    if not models.get_primary_photo(current_user['id']):
        return jsonify({'message': 'Add a profile picture before liking other users'}), 400

    if not models.like_user(current_user['id'], target['id']):
        return jsonify({'message': 'You already liked this user'}), 409

    mutual = models.has_liked(target['id'], current_user['id'])
    if mutual:
        models.create_notification(target['id'], 'match', from_user_id=current_user['id'])
        models.create_notification(current_user['id'], 'match', from_user_id=target['id'])
    else:
        models.create_notification(target['id'], 'like', from_user_id=current_user['id'])

    models.update_fame_rating(target['id'])

    return jsonify({'liked': True, 'isConnected': mutual}), 200


@users_bp.route('/<int:user_id>/like', methods=['DELETE'])
@jwt_required()
def unlike_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot unlike yourself'}), 400

    target = models.get_user_by_id(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if models.is_blocked_either_way(current_user['id'], target['id']):
        return jsonify({'message': 'User not found'}), 404

    removed, was_connected = models.unlike_user(current_user['id'], target['id'])
    if not removed:
        return jsonify({'message': 'You have not liked this user'}), 409

    if was_connected:
        models.create_notification(target['id'], 'unlike', from_user_id=current_user['id'])

    models.update_fame_rating(target['id'])

    return jsonify({'liked': False, 'isConnected': False}), 200


@users_bp.route('/<int:user_id>/block', methods=['POST'])
@jwt_required()
def block_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot block yourself'}), 400

    target = models.get_user_by_id(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    result = models.block_user(current_user['id'], target['id'])
    models.update_fame_rating(current_user['id'])
    models.update_fame_rating(target['id'])

    return jsonify({
        'blocked': True,
        'alreadyBlocked': not result['created'],
        'removedLikes': len(result['removed_likes']),
        'wasConnected': result['was_connected'],
    }), 200


@users_bp.route('/<int:user_id>/block', methods=['DELETE'])
@jwt_required()
def unblock_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if not models.unblock_user(current_user['id'], user_id):
        return jsonify({'message': 'Blocked user not found'}), 404

    return jsonify({'blocked': False}), 200


@users_bp.route('/<int:user_id>/report', methods=['POST'])
@jwt_required()
def report_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot report yourself'}), 400

    target = models.get_user_by_id(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if models.is_blocked_either_way(current_user['id'], target['id']):
        return jsonify({'message': 'User not found'}), 404

    report = models.create_report(current_user['id'], user_id)
    if not report:
        return jsonify({'message': 'You have already reported this user'}), 409

    return jsonify({'message': 'Report submitted'}), 201
