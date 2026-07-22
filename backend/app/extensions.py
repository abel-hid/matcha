from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_cors import CORS
from flask_socketio import SocketIO

jwt = JWTManager()
mail = Mail()
cors = CORS()
socketio = SocketIO(cors_allowed_origins="*")