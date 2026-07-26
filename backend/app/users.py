from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import models

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


def get_current_user_or_404():
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return models.get_user_by_id(int(user_id))


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

    if current_user['id'] != target['id']:
        is_new_view = models.record_view(current_user['id'], target['id'])
        if is_new_view:
            models.create_notification(target['id'], 'view', from_user_id=current_user['id'])
        models.update_fame_rating(target['id'])
        target = models.get_user_by_id(user_id)
    data = models.user_to_dict(target, include_private=False)
    data['hasLikedThem'] = models.has_liked(current_user['id'], target['id'])
    data['theyLikedMe'] = models.has_liked(target['id'], current_user['id'])
    data['isConnected'] = data['hasLikedThem'] and data['theyLikedMe']

    return jsonify({'user': data}), 200


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

    if models.has_liked(current_user['id'], target['id']):
        return jsonify({'message': 'Already liked'}), 400

    models.like_user(current_user['id'], target['id'])

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

    target = models.get_user_by_id(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    was_connected = (
        models.has_liked(current_user['id'], target['id'])
        and models.has_liked(target['id'], current_user['id'])
    )

    models.unlike_user(current_user['id'], target['id'])

    if was_connected:
        models.create_notification(target['id'], 'unlike', from_user_id=current_user['id'])

    models.update_fame_rating(target['id'])

    return jsonify({'liked': False}), 200


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

    models.block_user(current_user['id'], target['id'])
    return jsonify({'blocked': True}), 200


@users_bp.route('/<int:user_id>/block', methods=['DELETE'])
@jwt_required()
def unblock_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    models.unblock_user(current_user['id'], user_id)
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

    if models.has_reported(current_user['id'], user_id):
        return jsonify({'message': 'You have already reported this user'}), 400

    models.create_report(current_user['id'], user_id)
    return jsonify({'message': 'Report submitted'}), 201