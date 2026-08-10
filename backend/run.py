from app import create_app, models
from app.sockets import socketio

app = create_app()


if __name__ == '__main__':
    models.reset_online_users()

    host = app.config['BACKEND_HOST']
    port = app.config['BACKEND_PORT']

    socketio.run(app, host=host, port=port, debug=app.config['DEBUG'], use_reloader=False, log_output=False, allow_unsafe_werkzeug=True) # use_reloader=False is important to prevent double initialization of the socketio server, allow_unsafe_werkzeug=True for development only, in production use a proper WSGI server like gunicorn or uWSGI