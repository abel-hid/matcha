"""Socket.IO presence, conversation state, notifications, and audio-call signaling."""

from collections import defaultdict
from threading import Lock
from uuid import uuid4

from flask import current_app, request
from flask_jwt_extended import decode_token
from flask_socketio import SocketIO, disconnect, join_room

socketio = SocketIO(async_mode='threading')

_lock = Lock()
_user_connections = defaultdict(set)      # user_id -> {sid, sid, ...}
_session_connections = defaultdict(set)   # session_id -> {sid, sid, ...}
_sid_to_user = {}                         # sid -> user_id
_sid_to_session = {}                      # sid -> session_id

_call_lock = Lock()
_calls = {}                                  # call_id -> call data
_user_calls = {}                             # user_id -> call_id

CALL_ID_MAX_LENGTH = 64
CALL_SDP_MAX_LENGTH = 65_536
CALL_ICE_CANDIDATE_MAX_LENGTH = 4_096


def _authenticated_socket_session():
    """Authenticate the Socket.IO handshake from HttpOnly JWT cookies."""
    cookie_name = current_app.config.get('JWT_ACCESS_COOKIE_NAME', 'access_token_cookie')
    token = request.cookies.get(cookie_name)
    if not token:
        return None

    try:
        decoded = decode_token(token)
        if decoded.get('type') != 'access':
            return None

        user_id = int(decoded['sub'])
        session_id = decoded.get('sid')
        from app import models
        if not models.is_session_active(
            session_id,
            user_id,
            decoded.get('ver'),
        ):
            return None
        if not models.is_user_profile_complete(user_id):
            return None
        return user_id, session_id
    except (KeyError, TypeError, ValueError):
        return None
    except Exception:
        return None


def disconnect_session(session_id):
    """Disconnect every socket associated with a revoked authentication session."""
    with _lock:
        socket_ids = list(_session_connections.get(session_id, set()))

    for socket_id in socket_ids:
        socketio.server.disconnect(socket_id, namespace='/')


def disconnect_user(user_id):
    """Disconnect all tabs currently connected for one user."""
    with _lock:
        socket_ids = list(_user_connections.get(user_id, set()))

    for socket_id in socket_ids:
        socketio.server.disconnect(socket_id, namespace='/')


@socketio.on('connect')
def handle_connect(auth):
    """
    The browser sends the HttpOnly access-token cookie during the Socket.IO
    handshake. A connection is accepted only while the server-side session
    row is active.
    """
    authenticated_session = _authenticated_socket_session()
    if authenticated_session is None:
        disconnect()
        return False

    user_id, session_id = authenticated_session
    join_room(f'user:{user_id}')

    sid = request.sid
    with _lock:
        is_first_connection = len(_user_connections[user_id]) == 0
        _user_connections[user_id].add(sid)
        _session_connections[session_id].add(sid)
        _sid_to_user[sid] = user_id
        _sid_to_session[sid] = session_id

    if is_first_connection:
        from app import models
        models.set_user_online(user_id, True)
        socketio.emit('presence', {'userId': user_id, 'isOnline': True, 'lastActivity': None})


@socketio.on('disconnect')
def handle_disconnect():
    """Remove one socket and update final-tab presence and active calls."""
    sid = request.sid

    with _lock:
        user_id = _sid_to_user.pop(sid, None)
        session_id = _sid_to_session.pop(sid, None)
        if user_id is None:
            return

        _user_connections[user_id].discard(sid)
        is_last_connection = len(_user_connections[user_id]) == 0
        if is_last_connection:
            del _user_connections[user_id]

        if session_id is not None:
            _session_connections[session_id].discard(sid)
            if not _session_connections[session_id]:
                del _session_connections[session_id]

    end_socket_call(sid, user_id, 'disconnected')

    if is_last_connection:
        from app import models
        models.set_user_online(user_id, False)
        updated = models.get_user_by_id(user_id)
        socketio.emit('presence', {
            'userId': user_id,
            'isOnline': False,
            'lastActivity': models.to_iso_utc(updated['last_activity']) if updated else None,
        })
        end_user_call(user_id, 'disconnected')


def emit_conversation_status(user_a_id, user_b_id, can_message, reason, actor_id):
    """Tell both users when a relationship change enables or disables chat."""
    socketio.emit(
        'conversation_status',
        {
            'userId': user_b_id,
            'canMessage': can_message,
            'reason': reason,
            'actorId': actor_id,
        },
        room=f'user:{user_a_id}',
    )
    socketio.emit(
        'conversation_status',
        {
            'userId': user_a_id,
            'canMessage': can_message,
            'reason': reason,
            'actorId': actor_id,
        },
        room=f'user:{user_b_id}',
    )


def _socket_user_id():
    """Return the authenticated user identifier associated with the current socket."""
    with _lock:
        return _sid_to_user.get(request.sid)


def _socket_id():
    """Return the current Socket.IO connection identifier."""
    try:
        return request.sid
    except RuntimeError:
        return None


def _call_user_payload(user_id):
    """Serialize the minimal public identity shown in call controls."""
    from app import models

    user = models.get_user_by_id(user_id)
    if not user:
        return None

    photo = models.get_primary_photo(user_id)
    return {
        'id': user['id'],
        'username': user['username'],
        'firstName': user['first_name'],
        'lastName': user['last_name'],
        'profilePicture': (
            f"/uploads/{photo['filename']}"
            if photo
            else None
        ),
    }


def _other_call_user(call, user_id):
    """Return the opposite participant identifier for a call."""
    if call['caller_id'] == user_id:
        return call['recipient_id']
    if call['recipient_id'] == user_id:
        return call['caller_id']
    return None


def _remove_call(call_id):
    """Remove a call and both participant indexes under the call lock."""
    with _call_lock:
        call = _calls.pop(call_id, None)
        if not call:
            return None
        _user_calls.pop(call['caller_id'], None)
        _user_calls.pop(call['recipient_id'], None)
        return call


def _emit_call_end(call, reason, ended_by=None):
    """Emit a consistent call termination reason to both participants."""
    payload = {
        'callId': call['id'],
        'reason': reason,
        'endedBy': ended_by,
    }
    socketio.emit(
        'call_ended',
        payload,
        room=f"user:{call['caller_id']}",
    )
    socketio.emit(
        'call_ended',
        payload,
        room=f"user:{call['recipient_id']}",
    )


def end_socket_call(socket_id, user_id, reason='ended'):
    """End the call owned by a closing browser tab."""
    with _call_lock:
        call_id = _user_calls.get(user_id)
        call = _calls.get(call_id) if call_id else None
        if not call:
            return False

        owns_call = (
            call['caller_id'] == user_id
            and call.get('caller_sid') == socket_id
        ) or (
            call['recipient_id'] == user_id
            and call.get('recipient_sid') == socket_id
        )
        if not owns_call:
            return False

    removed = _remove_call(call_id)
    if not removed:
        return False

    _emit_call_end(removed, reason, ended_by=user_id)
    return True


def end_user_call(user_id, reason='ended'):
    """End any active call involving a user."""
    with _call_lock:
        call_id = _user_calls.get(user_id)
    if not call_id:
        return False

    call = _remove_call(call_id)
    if not call:
        return False

    _emit_call_end(call, reason, ended_by=user_id)
    return True


def end_calls_between(user_a_id, user_b_id, reason):
    """End active calls between two users after unlike or block."""
    with _call_lock:
        call_id = _user_calls.get(user_a_id)
        call = _calls.get(call_id) if call_id else None
        if not call or {
            call['caller_id'],
            call['recipient_id'],
        } != {user_a_id, user_b_id}:
            return False

    removed = _remove_call(call_id)
    if not removed:
        return False

    _emit_call_end(removed, reason, ended_by=user_a_id)
    return True


def _call_relationship_allowed(user_a_id, user_b_id):
    """Verify both profiles remain complete, connected, and non-blocked."""
    from app import models

    if user_a_id == user_b_id:
        return False
    if not models.get_user_by_id(user_b_id):
        return False
    if not models.is_user_profile_complete(user_b_id):
        return False
    if models.is_blocked_either_way(user_a_id, user_b_id):
        return False
    return models.is_connected(user_a_id, user_b_id)


def _call_id_from_data(data):
    """Validate and normalize a call identifier from a socket payload."""
    if not isinstance(data, dict):
        return None

    call_id = data.get('callId')
    if (
        not isinstance(call_id, str)
        or not call_id
        or len(call_id) > CALL_ID_MAX_LENGTH
    ):
        return None
    return call_id


def _valid_call_signal(signal_type, signal):
    """Validate bounded WebRTC SDP or ICE signaling data."""
    if not isinstance(signal_type, str) or not isinstance(signal, dict):
        return False

    if signal_type in {'offer', 'answer'}:
        sdp = signal.get('sdp')
        return (
            signal.get('type') == signal_type
            and isinstance(sdp, str)
            and 0 < len(sdp) <= CALL_SDP_MAX_LENGTH
        )

    if signal_type == 'ice':
        candidate = signal.get('candidate')
        return (
            isinstance(candidate, str)
            and len(candidate) <= CALL_ICE_CANDIDATE_MAX_LENGTH
        )

    return False


@socketio.on('call_start')
def handle_call_start(data):
    """Authorize and send an audio-call invitation to a connected user."""
    caller_id = _socket_user_id()
    if caller_id is None:
        return {'ok': False, 'message': 'Unauthorized'}

    if not isinstance(data, dict):
        return {'ok': False, 'message': 'Invalid call request'}

    recipient_id = data.get('recipientId')
    if isinstance(recipient_id, bool):
        return {'ok': False, 'message': 'Invalid recipient'}

    try:
        recipient_id = int(recipient_id)
    except (TypeError, ValueError):
        return {'ok': False, 'message': 'Invalid recipient'}

    if not _call_relationship_allowed(caller_id, recipient_id):
        return {
            'ok': False,
            'message': 'Audio calls require an active connection',
        }

    with _call_lock:
        if caller_id in _user_calls:
            return {'ok': False, 'message': 'You are already in a call'}
        if recipient_id in _user_calls:
            return {'ok': False, 'message': 'This user is currently busy'}

        call_id = str(uuid4())
        call = {
            'id': call_id,
            'caller_id': caller_id,
            'recipient_id': recipient_id,
            'caller_sid': _socket_id(),
            'recipient_sid': None,
            'status': 'ringing',
        }
        _calls[call_id] = call
        _user_calls[caller_id] = call_id
        _user_calls[recipient_id] = call_id

    caller = _call_user_payload(caller_id)
    recipient = _call_user_payload(recipient_id)
    socketio.emit(
        'call_incoming',
        {
            'callId': call_id,
            'caller': caller,
        },
        room=f'user:{recipient_id}',
    )

    return {
        'ok': True,
        'callId': call_id,
        'recipient': recipient,
    }


@socketio.on('call_accept')
def handle_call_accept(data):
    """Accept a ringing call from the invited participant."""
    user_id = _socket_user_id()
    call_id = _call_id_from_data(data)
    if call_id is None:
        return {'ok': False, 'message': 'Invalid call request'}

    with _call_lock:
        call = _calls.get(call_id)
        if (
            user_id is None
            or not call
            or call['recipient_id'] != user_id
            or call['status'] != 'ringing'
        ):
            return {'ok': False, 'message': 'Call is no longer available'}
        caller_id = call['caller_id']
        recipient_id = call['recipient_id']

    if not _call_relationship_allowed(caller_id, recipient_id):
        removed = _remove_call(call_id)
        if removed:
            _emit_call_end(
                removed,
                'connection_lost',
                ended_by=user_id,
            )
        return {'ok': False, 'message': 'Connection is no longer active'}

    with _call_lock:
        call = _calls.get(call_id)
        if not call or call['status'] != 'ringing':
            return {'ok': False, 'message': 'Call is no longer available'}
        call['recipient_sid'] = _socket_id()
        call['status'] = 'active'

    payload = {'callId': call_id}
    socketio.emit(
        'call_accepted',
        payload,
        room=f"user:{call['caller_id']}",
    )
    socketio.emit(
        'call_accepted',
        payload,
        room=f"user:{call['recipient_id']}",
    )
    return {'ok': True}


@socketio.on('call_decline')
def handle_call_decline(data):
    """Decline a ringing call and notify its caller."""
    user_id = _socket_user_id()
    call_id = _call_id_from_data(data)
    if call_id is None:
        return {'ok': False, 'message': 'Invalid call request'}

    with _call_lock:
        call = _calls.get(call_id)
        if (
            user_id is None
            or not call
            or call['recipient_id'] != user_id
            or call['status'] != 'ringing'
        ):
            return {'ok': False, 'message': 'Call is no longer available'}

    removed = _remove_call(call_id)
    if removed:
        payload = {'callId': call_id, 'reason': 'declined'}
        socketio.emit(
            'call_declined',
            payload,
            room=f"user:{removed['caller_id']}",
        )
        socketio.emit(
            'call_declined',
            payload,
            room=f"user:{removed['recipient_id']}",
        )
    return {'ok': True}


@socketio.on('call_signal')
def handle_call_signal(data):
    """Relay validated WebRTC signaling only between call participants."""
    user_id = _socket_user_id()
    if user_id is None or not isinstance(data, dict):
        return {'ok': False, 'message': 'Unauthorized'}

    call_id = _call_id_from_data(data)
    signal_type = data.get('type')
    signal = data.get('signal')
    if call_id is None:
        return {'ok': False, 'message': 'Invalid call request'}
    if not _valid_call_signal(signal_type, signal):
        return {'ok': False, 'message': 'Invalid call signal'}

    with _call_lock:
        call = _calls.get(call_id)
        if not call or call['status'] != 'active':
            return {'ok': False, 'message': 'Call is not active'}
        other_user_id = _other_call_user(call, user_id)
        if other_user_id is None:
            return {'ok': False, 'message': 'Unauthorized'}

    if not _call_relationship_allowed(user_id, other_user_id):
        end_calls_between(user_id, other_user_id, 'connection_lost')
        return {'ok': False, 'message': 'Connection is no longer active'}

    socketio.emit(
        'call_signal',
        {
            'callId': call_id,
            'type': signal_type,
            'signal': signal,
        },
        room=f'user:{other_user_id}',
    )
    return {'ok': True}


@socketio.on('call_end')
def handle_call_end(data):
    """End an owned call from either participant."""
    user_id = _socket_user_id()
    call_id = _call_id_from_data(data)
    if call_id is None:
        return {'ok': False, 'message': 'Invalid call request'}

    with _call_lock:
        call = _calls.get(call_id)
        if user_id is None or not call or _other_call_user(call, user_id) is None:
            return {'ok': False, 'message': 'Call not found'}

    removed = _remove_call(call_id)
    if removed:
        _emit_call_end(removed, 'ended', ended_by=user_id)
    return {'ok': True}
