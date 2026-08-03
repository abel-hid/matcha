"""Public profile, visit, like, block, unblock, and report routes."""

from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import models
from app.request_helpers import get_authenticated_user
from app.profile_access import complete_profile_required
from app.sockets import emit_conversation_status, end_calls_between
from app.validation import validate_username

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


def get_visible_target(current_user_id, target_user_id):
    """Return a public target only when both profiles are allowed to interact."""
    target = models.get_user_by_id(target_user_id)
    if not target:
        return None
    if not models.is_user_profile_complete(target_user_id):
        return None
    if models.is_blocked_either_way(current_user_id, target_user_id):
        return None
    return target


def get_visible_target_by_username(current_user_id, username):
    """Resolve a visible public target by stable username URL."""
    target = models.get_user_by_username(username)
    if not target:
        return None
    if not models.is_user_profile_complete(target['id']):
        return None
    if models.is_blocked_either_way(current_user_id, target['id']):
        return None
    return target


def profile_response_data(current_user_id, target):
    """Build public profile data plus relationship state for the viewer."""
    data = models.user_to_dict(target, include_private=False)
    data['hasLikedThem'] = models.has_liked(current_user_id, target['id'])
    data['theyLikedMe'] = models.has_liked(target['id'], current_user_id)
    data['isConnected'] = data['hasLikedThem'] and data['theyLikedMe']
    data['hasReported'] = models.has_reported(current_user_id, target['id'])
    return data


@users_bp.route('/blocked', methods=['GET'])
@jwt_required()
@complete_profile_required
def get_blocked_users():
    """Return every profile blocked by the authenticated user."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    blocked_users = models.get_blocked_users(current_user['id'])
    return jsonify({
        'blocks': [models.blocked_user_to_dict(user) for user in blocked_users]
    }), 200


@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
@complete_profile_required
def get_user_profile(user_id):
    """Return one authorized public profile by numeric identifier."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = get_visible_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({
        'user': profile_response_data(current_user['id'], target)
    }), 200


@users_bp.route('/by-username/<string:username>', methods=['GET'])
@jwt_required()
@complete_profile_required
def get_user_profile_by_username(username):
    """Return one authorized public profile by stable username URL."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    username, error = validate_username(username)
    if error:
        return jsonify({'message': 'User not found'}), 404

    target = get_visible_target_by_username(
        current_user['id'],
        username,
    )
    if not target:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({
        'user': profile_response_data(current_user['id'], target)
    }), 200


@users_bp.route('/<int:user_id>/visit', methods=['POST'])
@jwt_required()
@complete_profile_required
def record_profile_visit(user_id):
    """Record one visit and emit the mandatory real-time notification."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot record a visit to your own profile'}), 400

    target = get_visible_target(current_user['id'], user_id)
    if not target:
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
@complete_profile_required
def like_user(user_id):
    """Insert one directional like and clear prior notification suppression."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot like yourself'}), 400

    target = get_visible_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if not models.get_primary_photo(current_user['id']):
        return jsonify({'message': 'Add a profile picture before liking other users'}), 400

    if not models.like_user(current_user['id'], target['id']):
        return jsonify({'message': 'You already liked this user'}), 409

    mutual = models.has_liked(target['id'], current_user['id'])
    if mutual:
        models.create_notification(target['id'], 'match', from_user_id=current_user['id'])
        models.create_notification(current_user['id'], 'match', from_user_id=target['id'])
        emit_conversation_status(
            current_user['id'],
            target['id'],
            True,
            'match',
            current_user['id'],
        )
    else:
        models.create_notification(target['id'], 'like', from_user_id=current_user['id'])

    models.update_fame_rating(target['id'])

    return jsonify({'liked': True, 'isConnected': mutual}), 200


@users_bp.route('/<int:user_id>/like', methods=['DELETE'])
@jwt_required()
@complete_profile_required
def unlike_user(user_id):
    """Remove one directional like and suppress future notifications after disconnect."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot unlike yourself'}), 400

    target = get_visible_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    removed, was_connected = models.unlike_user(current_user['id'], target['id'])
    if not removed:
        return jsonify({'message': 'You have not liked this user'}), 409

    if was_connected:
        models.create_notification(target['id'], 'unlike', from_user_id=current_user['id'])
        emit_conversation_status(
            current_user['id'],
            target['id'],
            False,
            'unlike',
            current_user['id'],
        )
        end_calls_between(
            current_user['id'],
            target['id'],
            'unlike',
        )

    models.update_fame_rating(target['id'])

    return jsonify({'liked': False, 'isConnected': False}), 200


@users_bp.route('/<int:user_id>/block', methods=['POST'])
@jwt_required()
@complete_profile_required
def block_user(user_id):
    """Create the block and remove both directional likes in one transaction."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot block yourself'}), 400

    target = get_visible_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    result = models.block_user(current_user['id'], target['id'])
    models.update_fame_rating(current_user['id'])
    models.update_fame_rating(target['id'])
    emit_conversation_status(
        current_user['id'],
        target['id'],
        False,
        'block',
        current_user['id'],
    )
    end_calls_between(
        current_user['id'],
        target['id'],
        'block',
    )

    return jsonify({
        'blocked': True,
        'alreadyBlocked': not result['created'],
        'removedLikes': len(result['removed_likes']),
        'wasConnected': result['was_connected'],
    }), 200


@users_bp.route('/<int:user_id>/block', methods=['DELETE'])
@jwt_required()
@complete_profile_required
def unblock_user(user_id):
    """Remove an owned block without restoring the deleted likes."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if not models.unblock_user(current_user['id'], user_id):
        return jsonify({'message': 'Blocked user not found'}), 404

    return jsonify({'blocked': False}), 200


@users_bp.route('/<int:user_id>/report', methods=['POST'])
@jwt_required()
@complete_profile_required
def report_user(user_id):
    """Create the one-click fake-account report once per user pair."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user['id'] == user_id:
        return jsonify({'message': 'You cannot report yourself'}), 400

    target = get_visible_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    report = models.create_report(current_user['id'], user_id)
    if not report:
        return jsonify({'message': 'You have already reported this user'}), 409

    return jsonify({'message': 'Report submitted'}), 201
