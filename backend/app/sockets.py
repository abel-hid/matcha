
from flask_socketio import SocketIO, join_room, disconnect
from flask_jwt_extended import decode_token

socketio = SocketIO(cors_allowed_origins="*")


def _user_id_from_token(token):
    if not token:
        return None
    try:
        decoded = decode_token(token)
        return int(decoded['sub'])
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


@socketio.on('disconnect')
def handle_disconnect():
    pass