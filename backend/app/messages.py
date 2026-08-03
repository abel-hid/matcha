"""Connected-user conversation routes, unread counts, and real-time delivery."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import models
from app.request_helpers import get_authenticated_user
from app.profile_access import complete_profile_required
from app.sockets import socketio

messages_bp = Blueprint('messages', __name__, url_prefix='/api/messages')

MESSAGE_MAX_LENGTH = 1000
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


def get_available_target(current_user_id, target_user_id):
    """Return a complete, connected, non-blocked target user when allowed."""
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


def parse_page_argument(name, default, minimum, maximum):
    """Parse a positive pagination value with an upper bound."""
    raw_value = request.args.get(name)
    if raw_value in (None, ''):
        return default, None

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, f'{name} must be an integer'

    if value < minimum or value > maximum:
        return None, f'{name} must be between {minimum} and {maximum}'

    return value, None


@messages_bp.route('', methods=['GET'])
@jwt_required()
@complete_profile_required
def list_conversations():
    """Return message contacts with latest message and unread state."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    contacts = models.get_chat_contacts(current_user['id'])

    return jsonify({
        'conversations': [
            models.chat_contact_to_dict(contact)
            for contact in contacts
        ],
        'unreadCount': models.count_unread_messages(current_user['id']),
    }), 200


@messages_bp.route('/unread-count', methods=['GET'])
@jwt_required()
@complete_profile_required
def unread_message_count():
    """Return the unread message total for the current user."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({
        'unreadCount': models.count_unread_messages(current_user['id']),
    }), 200


@messages_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
@complete_profile_required
def get_conversation(user_id):
    """Return one authorized conversation in chronological pages."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = get_available_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'Conversation not found'}), 404

    can_message = models.is_connected(current_user['id'], target['id'])
    has_history = models.has_conversation_history(
        current_user['id'],
        target['id'],
    )

    if not can_message and not has_history:
        return jsonify({
            'message': 'You can only chat with connected users',
        }), 403

    page, error = parse_page_argument('page', 1, 1, 1000000)
    if error:
        return jsonify({'message': error}), 400

    page_size, error = parse_page_argument(
        'pageSize',
        DEFAULT_PAGE_SIZE,
        1,
        MAX_PAGE_SIZE,
    )
    if error:
        return jsonify({'message': error}), 400

    conversation = models.get_conversation(
        current_user['id'],
        target['id'],
        page,
        page_size,
    )

    return jsonify({
        'partner': models.chat_user_to_dict(target),
        'canMessage': can_message,
        'messages': [
            models.message_to_dict(message)
            for message in conversation['messages']
        ],
        'pagination': {
            'page': page,
            'pageSize': page_size,
            'total': conversation['total'],
            'totalPages': conversation['total_pages'],
        },
    }), 200


@messages_bp.route('/<int:user_id>', methods=['POST'])
@jwt_required()
@complete_profile_required
def send_message(user_id):
    """Persist and immediately emit a message between connected users."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = get_available_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'Conversation not found'}), 404

    if not models.is_connected(current_user['id'], target['id']):
        return jsonify({
            'message': 'You can only message connected users',
        }), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    content = data.get('content')
    if not isinstance(content, str):
        return jsonify({'message': 'Message content must be a string'}), 400

    content = content.strip()
    if not content:
        return jsonify({'message': 'Message cannot be empty'}), 400

    if len(content) > MESSAGE_MAX_LENGTH:
        return jsonify({
            'message': (
                f'Message must be at most '
                f'{MESSAGE_MAX_LENGTH} characters long'
            ),
        }), 400

    message = models.create_message(
        current_user['id'],
        target['id'],
        content,
    )
    serialized = models.message_to_dict(message)

    models.create_notification(
        target['id'],
        'message',
        from_user_id=current_user['id'],
    )

    socketio.emit(
        'message',
        serialized,
        room=f"user:{target['id']}",
    )
    socketio.emit(
        'message',
        serialized,
        room=f"user:{current_user['id']}",
    )

    return jsonify({'message': serialized}), 201


@messages_bp.route('/<int:user_id>/read', methods=['PUT'])
@jwt_required()
@complete_profile_required
def mark_conversation_read(user_id):
    """Mark incoming messages as read and emit delivery receipts."""
    current_user = get_authenticated_user()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = get_available_target(current_user['id'], user_id)
    if not target:
        return jsonify({'message': 'Conversation not found'}), 404

    can_message = models.is_connected(current_user['id'], target['id'])
    has_history = models.has_conversation_history(
        current_user['id'],
        target['id'],
    )

    if not can_message and not has_history:
        return jsonify({
            'message': 'Conversation not found',
        }), 404

    read_message_ids = models.mark_conversation_read(
        current_user['id'],
        target['id'],
    )

    if read_message_ids:
        socketio.emit(
            'message_read',
            {
                'readerId': current_user['id'],
                'messageIds': read_message_ids,
            },
            room=f"user:{target['id']}",
        )

    return jsonify({
        'unreadCount': models.count_unread_messages(current_user['id']),
        'readMessageIds': read_message_ids,
    }), 200
