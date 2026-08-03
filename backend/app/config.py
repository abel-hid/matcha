"""Local Docker configuration and startup validation for Matcha."""

import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')


def get_boolean(name, default=False):
    """Read a strict true-or-false environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized not in {'true', 'false'}:
        raise RuntimeError(f'{name} must be either true or false')
    return normalized == 'true'


def get_integer(name, default):
    """Read an integer environment variable with a controlled startup error."""
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f'{name} must be an integer') from exc


class Config:
    """Settings for the supported local Docker runtime."""

    SECRET_KEY = os.environ.get('SECRET_KEY')
    DATABASE_URL = os.environ.get('DATABASE_URL')

    # The backend always runs inside Docker and is exposed only through the
    # localhost port binding defined in docker-compose.yml.
    DEBUG = False
    BACKEND_HOST = '0.0.0.0'
    BACKEND_PORT = 5000
    DB_POOL_MIN = 1
    DB_POOL_MAX = 20

    # JWT cookies are HttpOnly and CSRF protected. Secure cookies remain off
    # because the supported evaluation URL is local HTTP on localhost.
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = True
    JWT_ACCESS_COOKIE_PATH = '/'
    JWT_REFRESH_COOKIE_PATH = '/api/auth/refresh'
    JWT_ACCESS_CSRF_COOKIE_PATH = '/'
    JWT_REFRESH_CSRF_COOKIE_PATH = '/'

    # Flask's session cookie stores only temporary OAuth state.
    SESSION_COOKIE_NAME = 'matcha_oauth_state'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False

    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = get_integer('MAIL_PORT', 587)
    MAIL_USE_TLS = get_boolean('MAIL_USE_TLS', True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    CORS_ORIGINS = ['http://localhost:3000']
    FRONTEND_URL = 'http://localhost:3000'

    NOMINATIM_URL = os.environ.get(
        'NOMINATIM_URL',
        'https://nominatim.openstreetmap.org',
    ).rstrip('/')
    NOMINATIM_USER_AGENT = os.environ.get(
        'NOMINATIM_USER_AGENT',
        'MatchaSchoolProject/1.0',
    )
    NOMINATIM_TIMEOUT_SECONDS = get_integer('NOMINATIM_TIMEOUT_SECONDS', 8)

    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    MAX_IMAGE_FILE_SIZE = 5 * 1024 * 1024
    ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG'}
    MAX_IMAGE_PIXELS = 20_000_000
    MAX_IMAGE_DIMENSION = 8_000
    IMAGE_OUTPUT_MAX_SIZE = (1_600, 1_600)

    FORTYTWO_CLIENT_ID = os.environ.get('FORTYTWO_CLIENT_ID')
    FORTYTWO_CLIENT_SECRET = os.environ.get('FORTYTWO_CLIENT_SECRET')
    FORTYTWO_REDIRECT_URI = 'http://localhost:5000/api/auth/oauth/42/callback'

    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = 'http://localhost:5000/api/auth/oauth/google/callback'

    OAUTH_TIMEOUT_SECONDS = 8
    OAUTH_STATE_MAX_AGE_SECONDS = 600

    @classmethod
    def validate(cls):
        """Fail startup when required secrets or grouped settings are missing."""
        required = {
            'SECRET_KEY': cls.SECRET_KEY,
            'DATABASE_URL': cls.DATABASE_URL,
            'JWT_SECRET_KEY': cls.JWT_SECRET_KEY,
            'MAIL_SERVER': cls.MAIL_SERVER,
            'MAIL_DEFAULT_SENDER': cls.MAIL_DEFAULT_SENDER,
        }
        missing = [name for name, value in required.items() if not value]
        errors = []

        if missing:
            errors.append(f"Missing required environment variables: {', '.join(missing)}")

        if cls.SECRET_KEY and (cls.SECRET_KEY.startswith('replace_with_') or len(cls.SECRET_KEY) < 32):
            errors.append('SECRET_KEY must be a private random value of at least 32 characters')
        if cls.JWT_SECRET_KEY and (cls.JWT_SECRET_KEY.startswith('replace_with_') or len(cls.JWT_SECRET_KEY) < 32):
            errors.append('JWT_SECRET_KEY must be a different private random value of at least 32 characters')
        if cls.SECRET_KEY and cls.JWT_SECRET_KEY and cls.SECRET_KEY == cls.JWT_SECRET_KEY:
            errors.append('SECRET_KEY and JWT_SECRET_KEY must be different')
        if cls.DATABASE_URL and 'replace_with_' in cls.DATABASE_URL:
            errors.append('POSTGRES_PASSWORD must be replaced with a private value')

        mail_credentials = {
            'MAIL_USERNAME': cls.MAIL_USERNAME,
            'MAIL_PASSWORD': cls.MAIL_PASSWORD,
        }
        if any(mail_credentials.values()) and not all(mail_credentials.values()):
            errors.append('MAIL_USERNAME and MAIL_PASSWORD must be set together')

        cls._validate_optional_group(errors, '42 OAuth', {
            'FORTYTWO_CLIENT_ID': cls.FORTYTWO_CLIENT_ID,
            'FORTYTWO_CLIENT_SECRET': cls.FORTYTWO_CLIENT_SECRET,
        })
        cls._validate_optional_group(errors, 'Google OAuth', {
            'GOOGLE_CLIENT_ID': cls.GOOGLE_CLIENT_ID,
            'GOOGLE_CLIENT_SECRET': cls.GOOGLE_CLIENT_SECRET,
        })

        if cls.MAIL_PORT <= 0:
            errors.append('MAIL_PORT must be greater than zero')
        if cls.NOMINATIM_TIMEOUT_SECONDS <= 0:
            errors.append('NOMINATIM_TIMEOUT_SECONDS must be greater than zero')

        if errors:
            raise RuntimeError('; '.join(errors))

    @classmethod
    def validate_database(cls):
        """Fail database utilities when the Compose database URL is missing."""
        if not cls.DATABASE_URL:
            raise RuntimeError('Missing required environment variable: DATABASE_URL')

    @staticmethod
    def _validate_optional_group(errors, group_name, values):
        """Require optional provider settings to be configured as a complete group."""
        configured = [name for name, value in values.items() if value]
        if configured and len(configured) != len(values):
            missing = [name for name, value in values.items() if not value]
            errors.append(f"Incomplete {group_name} configuration: {', '.join(missing)}")
