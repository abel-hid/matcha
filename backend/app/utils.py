import os
import secrets
import warnings
from html import escape as html_escape

import requests
from flask import current_app, has_app_context
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from PIL import Image, ImageOps, UnidentifiedImageError

from app.extensions import mail
from app.config import Config

def generate_verification_token(user):
    """Generate a one-time email verification token for the current address."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {
            'user_id': user['id'],
            'email': user['email'],
            'nonce': secrets.token_urlsafe(16),
        },
        salt='email-verification',
    )

def verify_verification_token(token, expiration=3600):
    """Return (payload, reason) for an email verification token."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        payload = serializer.loads(token, salt='email-verification', max_age=expiration)
        if not isinstance(payload, dict):
            return None, 'invalid'
        if (
            not isinstance(payload.get('user_id'), int)
            or not isinstance(payload.get('email'), str)
            or not isinstance(payload.get('nonce'), str)
        ):
            return None, 'invalid'
        return payload, None
    except SignatureExpired:
        return None, 'expired'
    except BadSignature:
        return None, 'invalid'

def generate_reset_token(email, token_version):
    """Generate a reset token tied to the current password-session version."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {
            'email': email,
            'v': token_version,
            'nonce': secrets.token_urlsafe(16),
        },
        salt='password-reset',
    )

def verify_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        data = serializer.loads(token, salt='password-reset', max_age=expiration)
        if not isinstance(data, dict):
            return None, 'invalid'
        if (
            not isinstance(data.get('email'), str)
            or not isinstance(data.get('v'), int)
            or not isinstance(data.get('nonce'), str)
        ):
            return None, 'invalid'
        return data, None
    except SignatureExpired:
        return None, 'expired'
    except BadSignature:
        return None, 'invalid'

def send_email(subject, recipients, html_body, text_body=None):
    """Send one HTML email with an optional plain-text alternative."""
    msg = Message(subject, recipients=recipients)
    msg.html = html_body
    if text_body:
        msg.body = text_body
    mail.send(msg)

def send_verification_email(user):
    """Send a one-hour verification link for the user's current email."""
    token = generate_verification_token(user)
    verify_url = f"{current_app.config['FRONTEND_URL']}/verify?token={token}"

    first_name = html_escape(user['first_name'])

    html = f"""
    <h1>Welcome to Matcha!</h1>
    <p>Hi {first_name},</p>
    <p>Please click the link below to verify your email address:</p>
    <p><a href="{verify_url}">{verify_url}</a></p>
    <p>This link will expire in 1 hour.</p>
    <p>If you didn't create an account, please ignore this email.</p>
    <br>
    <p>Matcha Team</p>
    """

    send_email(
        subject="Verify Your Email - Matcha",
        recipients=[user['email']],
        html_body=html,
        text_body=(
            f"Hi {user['first_name']},\n\n"
            f"Verify your Matcha email address: {verify_url}\n\n"
            "This link expires in 1 hour."
        ),
    )

def send_password_reset_email(user):
    """Send a one-hour reset link invalidated by any later password change."""
    token = generate_reset_token(user['email'], user['token_version'])
    reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password?token={token}"

    first_name = html_escape(user['first_name'])

    html = f"""
    <h1>Reset Your Password</h1>
    <p>Hi {first_name},</p>
    <p>Click the link below to reset your password:</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>This link will expire in 1 hour.</p>
    <p>If you didn't request this, please ignore this email.</p>
    <br>
    <p>Matcha Team</p>
    """

    send_email(
        subject="Reset Password - Matcha",
        recipients=[user['email']],
        html_body=html,
        text_body=(
            f"Hi {user['first_name']},\n\n"
            f"Reset your Matcha password: {reset_url}\n\n"
            "This link expires in 1 hour."
        ),
    )

def save_image(file):
    """Validate image content, remove metadata, and save a random server filename."""
    if not file or not file.filename:
        return None

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    Image.MAX_IMAGE_PIXELS = Config.MAX_IMAGE_PIXELS

    temp_path = None
    final_path = None

    try:
        file.stream.seek(0, os.SEEK_END)
        if file.stream.tell() > Config.MAX_IMAGE_FILE_SIZE:
            return None
        file.stream.seek(0)

        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(file.stream) as image:
                image.verify()

        file.stream.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(file.stream) as source:
                image_format = source.format
                if image_format not in Config.ALLOWED_IMAGE_FORMATS:
                    return None
                if (
                    source.width > Config.MAX_IMAGE_DIMENSION
                    or source.height > Config.MAX_IMAGE_DIMENSION
                    or source.width * source.height > Config.MAX_IMAGE_PIXELS
                ):
                    return None

                image = ImageOps.exif_transpose(source)
                image.load()
                image.thumbnail(Config.IMAGE_OUTPUT_MAX_SIZE, Image.Resampling.LANCZOS)

                extension = 'jpg' if image_format == 'JPEG' else 'png'
                filename = f'{secrets.token_hex(24)}.{extension}'
                final_path = os.path.join(Config.UPLOAD_FOLDER, filename)
                temp_path = os.path.join(Config.UPLOAD_FOLDER, f'.{filename}.tmp')

                if image_format == 'JPEG':
                    image.convert('RGB').save(
                        temp_path,
                        format='JPEG',
                        optimize=True,
                        quality=85,
                    )
                else:
                    if image.mode not in {'RGB', 'RGBA', 'L', 'LA', 'P'}:
                        image = image.convert('RGBA')
                    image.save(temp_path, format='PNG', optimize=True)

        os.replace(temp_path, final_path)
        return filename
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        for path in (temp_path, final_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        return None


def delete_saved_image(filename):
    """Delete one generated upload filename without allowing path traversal."""
    if not filename or os.path.basename(filename) != filename:
        return False

    upload_folder = os.path.realpath(Config.UPLOAD_FOLDER)
    filepath = os.path.realpath(os.path.join(upload_folder, filename))
    if os.path.commonpath([upload_folder, filepath]) != upload_folder:
        return False

    try:
        os.remove(filepath)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False

class LocationServiceError(Exception):
    pass


def location_config(name):
    """Return the geocoding endpoint, identity, and timeout configuration."""
    if has_app_context():
        return current_app.config[name]
    return getattr(Config, name)


def nominatim_get(path, params):
    """Perform a controlled Nominatim request with the required user agent."""
    try:
        response = requests.get(
            f"{location_config('NOMINATIM_URL')}{path}",
            params=params,
            headers={
                'User-Agent': location_config('NOMINATIM_USER_AGENT'),
                'Accept-Language': 'en,fr,ar',
            },
            timeout=location_config('NOMINATIM_TIMEOUT_SECONDS'),
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        if has_app_context():
            current_app.logger.warning('Location provider request failed: %s', exc)
        raise LocationServiceError('Location provider is unavailable') from exc


def compact_location_name(result):
    """Build a concise city or neighborhood label from geocoder data."""
    address = result.get('address') or {}
    local_name = (
        result.get('name')
        or address.get('neighbourhood')
        or address.get('suburb')
        or address.get('quarter')
        or address.get('city_district')
        or address.get('borough')
    )
    city = (
        address.get('city')
        or address.get('town')
        or address.get('village')
        or address.get('municipality')
    )
    region = address.get('state') or address.get('region')
    country = address.get('country')

    parts = []
    for value in (local_name, city, region, country):
        if value and value not in parts:
            parts.append(value)

    if parts:
        return ', '.join(parts)
    return result.get('display_name')


def search_locations(location_name, limit=5):
    """Return normalized manual-location suggestions from the geocoder."""
    data = nominatim_get('/search', {
        'q': location_name,
        'format': 'jsonv2',
        'addressdetails': 1,
        'dedupe': 1,
        'limit': limit,
    })
    if not isinstance(data, list):
        return []

    results = []
    seen = set()
    for item in data:
        try:
            latitude = float(item['lat'])
            longitude = float(item['lon'])
        except (KeyError, TypeError, ValueError):
            continue

        name = compact_location_name(item)
        if not name:
            continue

        key = (round(latitude, 6), round(longitude, 6), name)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            'name': name,
            'latitude': latitude,
            'longitude': longitude,
        })

    return results


def reverse_geocode_location(latitude, longitude):
    """Resolve coordinates to a readable approximate location label."""
    data = nominatim_get('/reverse', {
        'lat': latitude,
        'lon': longitude,
        'format': 'jsonv2',
        'zoom': 14,
        'addressdetails': 1,
    })
    if not isinstance(data, dict) or data.get('error'):
        return None
    return compact_location_name(data)
