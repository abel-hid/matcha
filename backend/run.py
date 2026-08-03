"""Start the Flask and Socket.IO backend."""

from app import create_app, models
from app.sockets import socketio

app = create_app()


if __name__ == '__main__':
    # A stopped server can leave users marked online in PostgreSQL. Resetting
    # presence at startup ensures everyone begins with the correct offline state.
    models.reset_online_users()

    host = app.config['BACKEND_HOST']
    port = app.config['BACKEND_PORT']
    print(f'Matcha backend running on http://{host}:{port}', flush=True)

    socketio.run(app, host=host, port=port, debug=app.config['DEBUG'], use_reloader=False, log_output=False, allow_unsafe_werkzeug=True)