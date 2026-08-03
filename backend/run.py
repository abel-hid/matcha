from app import create_app, models
from app.sockets import socketio

app = create_app()

if __name__ == '__main__':
    models.reset_online_users()
    socketio.run(
        app,
        debug=app.config['DEBUG'],
        host=app.config['BACKEND_HOST'],
        port=app.config['BACKEND_PORT'],
        use_reloader=False,
        log_output=False,
    )
