import os
import re
from datetime import datetime, timedelta
from flask import url_for
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from werkzeug.utils import secure_filename
from PIL import Image
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import bcrypt

from app.extensions import mail
from app.config import Config

# Password validation
def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"

    common_passwords = ['password', '123456', 'qwerty', 'admin', 'letmein', 'welcome']
    if password.lower() in common_passwords:
        return False, "Password is too common"

    return True, "Password is valid"

# Email validation
def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Generate verification token
def generate_verification_token(email):
    """Generate email verification token"""
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    return serializer.dumps(email, salt='email-verification')

# Verify token
def verify_verification_token(token, expiration=3600):
    """Verify email verification token"""
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    try:
        email = serializer.loads(token, salt='email-verification', max_age=expiration)
        return email
    except (SignatureExpired, BadSignature):
        return None

# Generate password reset token
def generate_reset_token(email, token_version):
    """Generate a single-use password reset token, tied to the user's current token_version"""
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    return serializer.dumps({'email': email, 'v': token_version}, salt='password-reset')

# Verify password reset token
def verify_reset_token(token, expiration=3600):
    """
    Verify password reset token.
    Returns (payload, None) on success, or (None, reason) on failure,
    where reason is 'expired' or 'invalid'.
    """
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    try:
        data = serializer.loads(token, salt='password-reset', max_age=expiration)
        return data, None
    except SignatureExpired:
        return None, 'expired'
    except BadSignature:
        return None, 'invalid'

# Send email
def send_email(subject, recipients, html_body, text_body=None):
    """Send email"""
    msg = Message(subject, recipients=recipients)
    msg.html = html_body
    if text_body:
        msg.body = text_body
    mail.send(msg)

# Send verification email
def send_verification_email(user):
    """Send email verification link. `user` is a dict from app.models."""
    token = generate_verification_token(user['email'])
    verify_url = f"{Config.FRONTEND_URL}/verify?token={token}"

    html = f"""
    <h1>Welcome to Matcha!</h1>
    <p>Hi {user['first_name']},</p>
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
        html_body=html
    )

# Send password reset email
def send_password_reset_email(user):
    """Send password reset link. `user` is a dict from app.models."""
    token = generate_reset_token(user['email'], user['token_version'])
    reset_url = f"{Config.FRONTEND_URL}/reset-password?token={token}"

    html = f"""
    <h1>Reset Your Password</h1>
    <p>Hi {user['first_name']},</p>
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
        html_body=html
    )

# File upload validation
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

# Save uploaded image
def save_image(file):
    """Save uploaded image with validation and optimization"""
    if not allowed_file(file.filename):
        return None

    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(filepath) 

    try:
        img = Image.open(filepath)
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        img.save(filepath, optimize=True, quality=85)
    except Exception:
        os.remove(filepath)
        return None

    return filepath

# Calculate distance between two locations
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers"""
    if not all([lat1, lon1, lat2, lon2]):
        return float('inf')
    return geodesic((lat1, lon1), (lat2, lon2)).kilometers

# Geocode location name to coordinates
def geocode_location(location_name):
    """Convert location name to coordinates"""
    if not location_name:
        return None, None

    geolocator = Nominatim(user_agent="matcha-app")
    try:
        location = geolocator.geocode(location_name, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None

# Calculate fame rating
def calculate_fame_rating(user_id):
    """
    Kept for backward compatibility with any caller that just wants a number
    without persisting it. `app.models.update_fame_rating` is the version
    used by the routes — it computes this same way and saves it.
    """
    from app.db import query_one
    likes_count = query_one(
        "SELECT COUNT(*) AS c FROM user_likes WHERE liked_id = %s", (user_id,)
    )['c']
    views_count = query_one(
        "SELECT COUNT(*) AS c FROM user_views WHERE viewed_id = %s", (user_id,)
    )['c']

    rating = (likes_count * 2) + (views_count * 0.5)
    return round(rating, 2)

# Check if two users are connected (mutual like)
def are_connected(user1_id, user2_id):
    """Check if two users have mutual likes"""
    from app.models import has_liked
    return has_liked(user1_id, user2_id) and has_liked(user2_id, user1_id)