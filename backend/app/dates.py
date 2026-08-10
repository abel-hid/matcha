from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import models
from app.request_helpers import get_authenticated_user
from app.profile_access import complete_profile_required
from app.sockets import socketio


dates_bp = Blueprint('dates', __name__, url_prefix='/api/dates')

DATE_LOCATION_MAX_LENGTH = 150
DATE_NOTE_MAX_LENGTH = 500


def get_available_target(current_user_id, target_user_id):
    if current_user_id == target_user_id:
        return None

    target = models.get_user_by_id(target_user_id)
    if not target:
        return None

    if not models.is_user_profile_complete(target_user_id):
        return None

    if models.is_blocked_either_way(current_user_id, target_user_id):
        return None

    return target


def parse_scheduled_for(value):
    if not isinstance(value, str):
        return None, 'scheduledFor must be an ISO date-time string'

    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None, 'scheduledFor must be a valid ISO date-time string'

    if parsed.tzinfo is None:
        return None, 'scheduledFor must include a timezone'

    parsed = parsed.astimezone(timezone.utc)
    if parsed <= datetime.now(timezone.utc):
        return None, 'The date must be scheduled in the future'

    return parsed, None


def validate_text(value, name, maximum, required=True):
    if value is None and not required:
        return None, None

    if not isinstance(value, str):
        return None, f'{name} must be a string'

    value = value.strip()
    if required and not value:
        return None, f'{name} is required'

    if len(value) > maximum:
        return None, f'{name} must be at most {maximum} characters long'

    return value or None, None


def emit_date_event(event):
    serialized = models.date_event_to_dict(event)
    for user_id in (event['proposer_id'], event['recipient_id']):
        socketio.emit(
            'date_event',
            serialized,
            room=f'user:{user_id}',
        )
    return serialized


@dates_bp.route('', methods=['GET'])
@jwt_required()
@complete_profile_required
def list_date_events():
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    events = models.get_date_events_for_user(current_user['id'])
    return jsonify({
        'events': [
            models.date_event_to_dict(event)
            for event in events
        ],
    }), 200


@dates_bp.route('/<int:user_id>', methods=['POST'])
@jwt_required()
@complete_profile_required
def create_date_event(user_id):
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = get_available_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if not models.is_connected(current_user['id'], target['id']):
        return jsonify({
            'message': 'You can only schedule dates with connected users',
        }), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    scheduled_for, error = parse_scheduled_for(data.get('scheduledFor'))
    if error:
        return jsonify({'message': error}), 400

    location, error = validate_text(
        data.get('location'),
        'Location',
        DATE_LOCATION_MAX_LENGTH,
    )
    if error:
        return jsonify({'message': error}), 400

    note, error = validate_text(
        data.get('note'),
        'Note',
        DATE_NOTE_MAX_LENGTH,
        required=False,
    )
    if error:
        return jsonify({'message': error}), 400

    event = models.create_date_event(
        current_user['id'],
        target['id'],
        scheduled_for,
        location,
        note,
    )
    serialized = emit_date_event(event)

    models.create_notification(
        target['id'],
        'date',
        from_user_id=current_user['id'],
        content=f'{current_user["username"]} proposed a date',
    )

    return jsonify({'event': serialized}), 201


@dates_bp.route('/<int:event_id>/respond', methods=['PUT'])
@jwt_required()
@complete_profile_required
def respond_to_date_event(event_id):
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    status = data.get('status')
    if status not in {'accepted', 'declined'}:
        return jsonify({
            'message': 'status must be accepted or declined',
        }), 400

    existing = models.get_date_event(event_id)
    if not existing or existing['recipient_id'] != current_user['id']:
        return jsonify({'message': 'Date proposal not found'}), 404

    other_user_id = existing['proposer_id']
    if (
        models.is_blocked_either_way(current_user['id'], other_user_id)
        or not models.is_connected(current_user['id'], other_user_id)
    ):
        return jsonify({
            'message': 'You must still be connected to respond',
        }), 403

    event = models.respond_to_date_event(
        event_id,
        current_user['id'],
        status,
    )
    if not event:
        return jsonify({
            'message': 'This date proposal is no longer pending',
        }), 409

    serialized = emit_date_event(event)
    models.create_notification(
        other_user_id,
        'date',
        from_user_id=current_user['id'],
        content=f'{current_user["username"]} {status} your date proposal',
    )

    return jsonify({'event': serialized}), 200


@dates_bp.route('/<int:event_id>/cancel', methods=['PUT'])
@jwt_required()
@complete_profile_required
def cancel_date_event(event_id):
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    existing = models.get_date_event(event_id)
    if not existing or current_user['id'] not in {
        existing['proposer_id'],
        existing['recipient_id'],
    }:
        return jsonify({'message': 'Date proposal not found'}), 404

    other_user_id = (
        existing['recipient_id']
        if existing['proposer_id'] == current_user['id']
        else existing['proposer_id']
    )

    if (
        models.is_blocked_either_way(current_user['id'], other_user_id)
        or not models.is_connected(current_user['id'], other_user_id)
    ):
        return jsonify({
            'message': 'You must still be connected to cancel this date',
        }), 403

    event = models.cancel_date_event(event_id, current_user['id'])
    if not event:
        return jsonify({
            'message': 'This date can no longer be cancelled',
        }), 409

    serialized = emit_date_event(event)
    models.create_notification(
        other_user_id,
        'date',
        from_user_id=current_user['id'],
        content=f'{current_user["username"]} cancelled a date',
    )

    return jsonify({'event': serialized}), 200
