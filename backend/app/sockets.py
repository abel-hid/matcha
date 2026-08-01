from collections import defaultdict
from threading import Lock

from flask import current_app, request
from flask_jwt_extended import decode_token
from flask_socketio import SocketIO, disconnect, join_room

socketio = SocketIO(cors_allowed_origins="*")

_lock = Lock()
_user_connections = defaultdict(set)      # user_id -> {sid, sid, ...}
_session_connections = defaultdict(set)   # session_id -> {sid, sid, ...}
_sid_to_user = {}                         # sid -> user_id
_sid_to_session = {}                      # sid -> session_id


def _authenticated_socket_session():
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
    with _lock:
        socket_ids = list(_session_connections.get(session_id, set()))

    for socket_id in socket_ids:
        socketio.server.disconnect(socket_id, namespace='/')


def disconnect_user(user_id):
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

    if is_last_connection:
        from app import models
        models.set_user_online(user_id, False)
        updated = models.get_user_by_id(user_id)
        socketio.emit('presence', {
            'userId': user_id,
            'isOnline': False,
            'lastActivity': models.to_iso_utc(updated['last_activity']) if updated else None,
        })
