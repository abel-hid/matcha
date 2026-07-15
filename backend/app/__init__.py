from flask import Flask
from app.config import Config
from app.extensions import db, migrate, jwt, mail, cors
from app.auth import auth_bp
import os

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'])

    app.register_blueprint(auth_bp)

    return app