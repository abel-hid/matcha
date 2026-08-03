import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

load_dotenv(os.path.join(BASE_DIR, '.env'))


def get_boolean(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized not in {'true', 'false'}:
        raise RuntimeError(f'{name} must be either true or false')

    return normalized == 'true'


def get_integer(name, default):
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f'{name} must be an integer') from exc


def get_list(name, default):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DATABASE_URL = os.environ.get('DATABASE_URL')

    DEBUG = get_boolean('FLASK_DEBUG', False)
    BACKEND_HOST = os.environ.get('BACKEND_HOST', '127.0.0.1')
    BACKEND_PORT = get_integer('BACKEND_PORT', 5000)

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=get_integer('JWT_ACCESS_TOKEN_MINUTES', 15)
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=get_integer('JWT_REFRESH_TOKEN_DAYS', 7)
    )
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_SECURE = get_boolean('JWT_COOKIE_SECURE', False)
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = True
    JWT_ACCESS_COOKIE_PATH = '/'
    JWT_REFRESH_COOKIE_PATH = '/api/auth/refresh'
    JWT_ACCESS_CSRF_COOKIE_PATH = '/'
    JWT_REFRESH_CSRF_COOKIE_PATH = '/'

    # Flask session cookie used only for temporary OAuth state
    SESSION_COOKIE_NAME = 'matcha_oauth_state'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = JWT_COOKIE_SECURE

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = get_integer('MAIL_PORT', 587)
    MAIL_USE_TLS = get_boolean('MAIL_USE_TLS', True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # CORS
    CORS_ORIGINS = get_list('CORS_ORIGINS', 'http://localhost:3000')

    # Location provider
    NOMINATIM_URL = os.environ.get(
        'NOMINATIM_URL',
        'https://nominatim.openstreetmap.org',
    ).rstrip('/')
    NOMINATIM_USER_AGENT = os.environ.get(
        'NOMINATIM_USER_AGENT',
        'MatchaSchoolProject/1.0',
    )
    NOMINATIM_TIMEOUT_SECONDS = get_integer('NOMINATIM_TIMEOUT_SECONDS', 8)

    # Upload
    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024  # 5MB image plus multipart overhead
    MAX_IMAGE_FILE_SIZE = 5 * 1024 * 1024
    ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG'}
    MAX_IMAGE_PIXELS = 20_000_000
    MAX_IMAGE_DIMENSION = 8_000
    IMAGE_OUTPUT_MAX_SIZE = (1_600, 1_600)

    # Frontend URL for email links
    FRONTEND_URL = os.environ.get('FRONTEND_URL')

    # Optional OAuth providers
    FORTYTWO_CLIENT_ID = os.environ.get('FORTYTWO_CLIENT_ID')
    FORTYTWO_CLIENT_SECRET = os.environ.get('FORTYTWO_CLIENT_SECRET')
    FORTYTWO_REDIRECT_URI = os.environ.get('FORTYTWO_REDIRECT_URI')

    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')

    OAUTH_TIMEOUT_SECONDS = get_integer('OAUTH_TIMEOUT_SECONDS', 8)
    OAUTH_STATE_MAX_AGE_SECONDS = get_integer('OAUTH_STATE_MAX_AGE_SECONDS', 600)

    @classmethod
    def validate(cls):
        required = {
            'SECRET_KEY': cls.SECRET_KEY,
            'DATABASE_URL': cls.DATABASE_URL,
            'JWT_SECRET_KEY': cls.JWT_SECRET_KEY,
            'MAIL_SERVER': cls.MAIL_SERVER,
            'MAIL_DEFAULT_SENDER': cls.MAIL_DEFAULT_SENDER,
            'FRONTEND_URL': cls.FRONTEND_URL,
        }
        missing = [name for name, value in required.items() if not value]

        errors = []
        if missing:
            errors.append(f"Missing required environment variables: {', '.join(missing)}")

        mail_credentials = {
            'MAIL_USERNAME': cls.MAIL_USERNAME,
            'MAIL_PASSWORD': cls.MAIL_PASSWORD,
        }
        if any(mail_credentials.values()) and not all(mail_credentials.values()):
            errors.append('MAIL_USERNAME and MAIL_PASSWORD must be set together')

        cls._validate_optional_group(
            errors,
            '42 OAuth',
            {
                'FORTYTWO_CLIENT_ID': cls.FORTYTWO_CLIENT_ID,
                'FORTYTWO_CLIENT_SECRET': cls.FORTYTWO_CLIENT_SECRET,
                'FORTYTWO_REDIRECT_URI': cls.FORTYTWO_REDIRECT_URI,
            },
        )
        cls._validate_optional_group(
            errors,
            'Google OAuth',
            {
                'GOOGLE_CLIENT_ID': cls.GOOGLE_CLIENT_ID,
                'GOOGLE_CLIENT_SECRET': cls.GOOGLE_CLIENT_SECRET,
                'GOOGLE_REDIRECT_URI': cls.GOOGLE_REDIRECT_URI,
            },
        )

        if cls.OAUTH_TIMEOUT_SECONDS <= 0:
            errors.append('OAUTH_TIMEOUT_SECONDS must be greater than zero')
        if cls.OAUTH_STATE_MAX_AGE_SECONDS <= 0:
            errors.append('OAUTH_STATE_MAX_AGE_SECONDS must be greater than zero')

        if errors:
            raise RuntimeError('; '.join(errors))

    @classmethod
    def validate_database(cls):
        if not cls.DATABASE_URL:
            raise RuntimeError('Missing required environment variable: DATABASE_URL')

    @staticmethod
    def _validate_optional_group(errors, group_name, values):
        configured = [name for name, value in values.items() if value]
        if configured and len(configured) != len(values):
            missing = [name for name, value in values.items() if not value]
            errors.append(f"Incomplete {group_name} configuration: {', '.join(missing)}")
