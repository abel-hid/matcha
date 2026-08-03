"""Application factory, blueprint registration, health checks, and normalized API errors."""

import psycopg2
from flask import Flask, jsonify, request, send_from_directory

from app.auth import auth_bp
from app.config import Config
from app.dates import dates_bp
from app.db import init_pool, query_one
from app.discover import discover_bp
from app.extensions import cors, jwt, mail
from app.messages import messages_bp
from app.notifications import notifications_bp
from app.oauth import oauth_bp
from app.profile import profile_bp
from app.sockets import socketio
from app.users import users_bp


def create_app(config_class=Config):
    """Build and configure the Flask application and all runtime integrations."""
    app = Flask(__name__)
    config_class.validate()
    app.config.from_object(config_class)

    init_pool(app.config['DATABASE_URL'], app.config['DB_POOL_MIN'], app.config['DB_POOL_MAX'])

    jwt.init_app(app)
    mail.init_app(app)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'], supports_credentials=True)
    socketio.init_app(app, cors_allowed_origins=app.config['CORS_ORIGINS'], async_mode='threading')

    for blueprint in (
        auth_bp,
        profile_bp,
        users_bp,
        notifications_bp,
        discover_bp,
        messages_bp,
        oauth_bp,
        dates_bp,
    ):
        app.register_blueprint(blueprint)

    @app.get('/api/health')
    def health():
        """Verify that the API and PostgreSQL connection are ready."""
        query_one('SELECT 1 AS ready')
        return jsonify({'status': 'ok'}), 200

    @app.get('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Serve a validated uploaded image from the configured upload directory."""
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.after_request
    def add_security_headers(response):
        """Apply conservative headers without changing API status codes or response bodies."""
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(self), geolocation=(self)')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-site')
        if request.path.startswith('/api/'):
            response.headers.setdefault('Cache-Control', 'no-store')
        return response

    register_error_handlers(app)
    return app


def register_error_handlers(app):
    """Register consistent JSON responses for expected and unexpected failures."""

    @app.errorhandler(400)
    def bad_request(_error):
        """Return the normalized response for a malformed request."""
        return jsonify({'message': 'Bad request'}), 400

    @app.errorhandler(401)
    def unauthorized(_error):
        """Return the normalized response for missing authentication."""
        return jsonify({'message': 'Unauthorized'}), 401

    @app.errorhandler(403)
    def forbidden(_error):
        """Return the normalized response for an authorization failure."""
        return jsonify({'message': 'Forbidden'}), 403

    @app.errorhandler(404)
    def not_found(_error):
        """Return the normalized response for an unavailable resource."""
        return jsonify({'message': 'Not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        """Return the normalized response for an unsupported HTTP method."""
        return jsonify({'message': 'Method not allowed'}), 405

    @app.errorhandler(413)
    def payload_too_large(_error):
        """Return the normalized response when an upload exceeds the size limit."""
        return jsonify({'message': 'File too large'}), 413

    @app.errorhandler(psycopg2.errors.UniqueViolation)
    def unique_violation(_error):
        """Return a controlled conflict response for database uniqueness rules."""
        return jsonify({'message': 'That value is already in use'}), 409

    @app.errorhandler(psycopg2.Error)
    def database_error(error):
        """Log unexpected PostgreSQL failures without exposing details to the client."""
        app.logger.exception('Database operation failed: %s', error)
        return jsonify({'message': 'A database error occurred'}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        """Log unexpected server failures and return a stable public response."""
        app.logger.exception('Unhandled application exception: %s', error)
        return jsonify({'message': 'An unexpected error occurred'}), 500
