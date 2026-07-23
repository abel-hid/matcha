from flask import Flask, send_from_directory, jsonify
import psycopg2

from app.config import Config
from app.extensions import jwt, mail, cors
from app.db import init_pool
from app.sockets import socketio
from app.auth import auth_bp
from app.profile import profile_bp
from app.users import users_bp
from app.notifications import notifications_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    init_pool()  # raw psycopg2 connection pool, replaces db.init_app

    jwt.init_app(app)
    mail.init_app(app)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'])

    # async_mode='eventlet' needs `pip install eventlet` and to be run via
    # socketio.run(app) (see run.py) rather than app.run() / a plain WSGI
    # server, so the websocket transport actually works.
    socketio.init_app(app, cors_allowed_origins=app.config['CORS_ORIGINS'], async_mode='eventlet')

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(notifications_bp)

    from app import sockets 

    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    register_error_handlers(app)

    return app


def register_error_handlers(app):
    """
    Ensures every error — expected or not — returns JSON with an appropriate
    status code instead of an HTML stack trace page or a bare 500.
    """

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'message': 'Bad request'}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'message': 'Unauthorized'}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'message': 'Forbidden'}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'message': 'Not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'message': 'Method not allowed'}), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({'message': 'File too large'}), 413

    @app.errorhandler(psycopg2.errors.UniqueViolation)
    def unique_violation(e):
        return jsonify({'message': 'That value is already in use'}), 400

    @app.errorhandler(psycopg2.Error)
    def db_error(e):
        app.logger.error(f"Database error: {e}")
        return jsonify({'message': 'A database error occurred'}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        app.logger.exception("Unhandled exception")
        return jsonify({'message': 'An unexpected error occurred'}), 500