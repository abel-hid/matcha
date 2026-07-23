from collections import defaultdict
from threading import Lock

from flask import request
from flask_socketio import SocketIO, join_room, disconnect
from flask_jwt_extended import decode_token

socketio = SocketIO(cors_allowed_origins="*")

_lock = Lock()
_user_connections = defaultdict(set)   # user_id -> {sid, sid, ...}
_sid_to_user = {}                      # sid -> user_id 


def _user_id_from_token(token):
    if not token:
        return None
    try:
        decoded = decode_token(token)
        return int(decoded['sub']) # sub is the user_id we set in create_access_token()
    except Exception:
        return None


@socketio.on('connect')
def handle_connect(auth):
    """
    Client must connect with:  io(url, { auth: { token: accessToken } })
    Rejecting here (return False / disconnect()) fails the handshake, so the
    client's `connect_error` event fires and it can redirect to /login.
    """
    token = auth.get('token') if isinstance(auth, dict) else None
    user_id = _user_id_from_token(token)

    if user_id is None:
        disconnect()
        return False

    join_room(f'user:{user_id}')

    sid = request.sid
    with _lock:
        is_first_connection = len(_user_connections[user_id]) == 0
        _user_connections[user_id].add(sid)
        _sid_to_user[sid] = user_id

    if is_first_connection:
        from app import models
        models.set_user_online(user_id, True)
        socketio.emit('presence', {'userId': user_id, 'isOnline': True, 'lastActivity': None})


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid

    with _lock:
        user_id = _sid_to_user.pop(sid, None)
        if user_id is None:
            return
        _user_connections[user_id].discard(sid)
        is_last_connection = len(_user_connections[user_id]) == 0
        if is_last_connection:
            del _user_connections[user_id]

    if is_last_connection:
        from app import models
        models.set_user_online(user_id, False)
        updated = models.get_user_by_id(user_id)
        socketio.emit('presence', {
            'userId': user_id,
            'isOnline': False,
            'lastActivity': updated['last_activity'].isoformat() if updated and updated['last_activity'] else None,
        })