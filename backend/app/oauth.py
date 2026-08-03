"""Google and 42 OAuth state, provider exchange, account linking, and login completion."""

import secrets
import time
from urllib.parse import urlencode

import psycopg2
import requests
from flask import Blueprint, current_app, jsonify, redirect, request, session

from app import models
from app.auth import attach_session_cookies
from app.validation import normalize_email


oauth_bp = Blueprint('oauth', __name__, url_prefix='/api/auth/oauth')


class OAuthProviderError(RuntimeError):
    """Carry a safe public reason for an upstream OAuth provider failure."""
    def __init__(self, reason):
        """Store the public OAuth failure reason returned to the callback handler."""
        super().__init__(reason)
        self.reason = reason


def finish_login(user):
    """Create a normal cookie session after successful OAuth authentication."""
    frontend_url = current_app.config['FRONTEND_URL']
    response = redirect(f'{frontend_url}/oauth-callback')
    return attach_session_cookies(response, user)


def redirect_with_error(reason):
    """Redirect to login with a controlled OAuth error code."""
    frontend_url = current_app.config['FRONTEND_URL']
    return redirect(f'{frontend_url}/login?error={reason}')


def oauth_not_configured(provider):
    """Return a controlled service-unavailable response for a disabled provider."""
    return jsonify({'message': f'{provider} OAuth is not configured'}), 503


def provider_config(provider):
    """Return URLs and credentials for one supported OAuth provider."""
    if provider == '42':
        return {
            'label': '42',
            'client_id': current_app.config['FORTYTWO_CLIENT_ID'],
            'client_secret': current_app.config['FORTYTWO_CLIENT_SECRET'],
            'redirect_uri': current_app.config['FORTYTWO_REDIRECT_URI'],
        }

    if provider == 'google':
        return {
            'label': 'Google',
            'client_id': current_app.config['GOOGLE_CLIENT_ID'],
            'client_secret': current_app.config['GOOGLE_CLIENT_SECRET'],
            'redirect_uri': current_app.config['GOOGLE_REDIRECT_URI'],
        }

    raise ValueError('Unsupported OAuth provider')


def create_oauth_state(provider):
    """Create and store a short-lived state token against login CSRF."""
    value = secrets.token_urlsafe(32)
    session[f'oauth_state_{provider}'] = {
        'value': value,
        'createdAt': int(time.time()),
    }
    return value


def validate_oauth_state(provider):
    """Validate and consume the provider callback state token once."""
    supplied_state = request.args.get('state', '')
    stored_state = session.pop(f'oauth_state_{provider}', None)

    if not isinstance(stored_state, dict):
        return False

    stored_value = stored_state.get('value')
    created_at = stored_state.get('createdAt')
    if not isinstance(stored_value, str) or not isinstance(created_at, int):
        return False

    if not supplied_state or not secrets.compare_digest(supplied_state, stored_value):
        return False

    age = int(time.time()) - created_at
    return 0 <= age <= current_app.config['OAUTH_STATE_MAX_AGE_SECONDS']


def request_provider_json(method, url, *, data=None, headers=None):
    """Call a provider with timeout and normalized upstream failures."""
    try:
        response = requests.request(
            method,
            url,
            data=data,
            headers=headers,
            timeout=current_app.config['OAUTH_TIMEOUT_SECONDS'],
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        current_app.logger.warning('OAuth provider request failed: %s', error)
        raise OAuthProviderError('provider_unavailable') from error
    except ValueError as error:
        current_app.logger.warning('OAuth provider returned invalid JSON')
        raise OAuthProviderError('invalid_provider_response') from error

    if not isinstance(payload, dict):
        raise OAuthProviderError('invalid_provider_response')

    return payload


def exchange_access_token(provider, code):
    """Exchange an authorization code for a provider access token."""
    config = provider_config(provider)

    if provider == '42':
        token_url = 'https://api.intra.42.fr/oauth/token'
    else:
        token_url = 'https://oauth2.googleapis.com/token'

    payload = request_provider_json(
        'POST',
        token_url,
        data={
            'grant_type': 'authorization_code',
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'code': code,
            'redirect_uri': config['redirect_uri'],
        },
    )
    access_token = payload.get('access_token')
    if not isinstance(access_token, str) or not access_token:
        raise OAuthProviderError('token_exchange_failed')

    return access_token


def fetch_provider_profile(provider, access_token):
    """Fetch the authenticated provider profile."""
    if provider == '42':
        return request_provider_json(
            'GET',
            'https://api.intra.42.fr/v2/me',
            headers={'Authorization': f'Bearer {access_token}'},
        )

    return request_provider_json(
        'GET',
        'https://openidconnect.googleapis.com/v1/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
    )


def clean_name(value, fallback):
    """Normalize a provider name and apply a safe fallback when absent."""
    if isinstance(value, str):
        cleaned = ' '.join(value.strip().split())[:50]
        if cleaned:
            return cleaned
    return fallback


def normalize_provider_profile(provider, profile):
    """Normalize Google or 42 profile fields into the local account shape."""
    if provider == '42':
        oauth_id = profile.get('id')
        raw_email = profile.get('email')
        preferred_username = profile.get('login')
        first_name = profile.get('first_name')
        last_name = profile.get('last_name')
    else:
        if profile.get('email_verified') is not True:
            raise OAuthProviderError('email_not_verified')

        oauth_id = profile.get('sub')
        raw_email = profile.get('email')
        preferred_username = (
            raw_email.split('@', 1)[0]
            if isinstance(raw_email, str)
            else None
        )
        first_name = profile.get('given_name')
        last_name = profile.get('family_name')

    oauth_id = str(oauth_id).strip() if oauth_id is not None else ''
    if not oauth_id or len(oauth_id) > 255:
        raise OAuthProviderError('invalid_provider_profile')

    email, email_error = normalize_email(raw_email)
    if email_error:
        raise OAuthProviderError('invalid_provider_profile')

    username_seed = preferred_username if isinstance(preferred_username, str) else ''
    username_seed = username_seed.strip() or email.split('@', 1)[0]

    return {
        'provider': provider,
        'oauth_id': oauth_id,
        'email': email,
        'first_name': clean_name(first_name, 'OAuth'),
        'last_name': clean_name(last_name, 'User'),
        'preferred_username': username_seed,
    }


def resolve_user(provider, oauth_id, email, first_name, last_name, preferred_username):
    """Login, link, or create the local account represented by an OAuth identity."""
    user = models.get_user_by_oauth(provider, oauth_id)
    if user:
        return finish_login(user)

    existing = models.get_user_by_email(email)
    if existing:
        try:
            models.link_oauth_to_user(
                existing['id'],
                provider,
                oauth_id,
                email,
            )
        except models.OAuthIdentityConflictError:
            return redirect_with_error('oauth_identity_conflict')
        return finish_login(models.get_user_by_id(existing['id']))

    username = models.generate_unique_username(preferred_username)
    try:
        user = models.create_oauth_user(
            username,
            email,
            first_name,
            last_name,
            provider,
            oauth_id,
        )
    except (psycopg2.errors.UniqueViolation, models.OAuthIdentityConflictError):
        return redirect_with_error('oauth_identity_conflict')

    return finish_login(user)


def complete_callback(provider):
    """Complete one OAuth callback and redirect with a secure cookie session."""
    config = provider_config(provider)
    if not all([
        config['client_id'],
        config['client_secret'],
        config['redirect_uri'],
    ]):
        return oauth_not_configured(config['label'])

    if not validate_oauth_state(provider):
        return redirect_with_error('invalid_state')

    if request.args.get('error'):
        return redirect_with_error('access_denied')

    code = request.args.get('code', '').strip()
    if not code:
        return redirect_with_error('missing_code')

    try:
        access_token = exchange_access_token(provider, code)
        raw_profile = fetch_provider_profile(provider, access_token)
        profile = normalize_provider_profile(provider, raw_profile)
    except OAuthProviderError as error:
        return redirect_with_error(error.reason)

    return resolve_user(**profile)


# --------------------------------------------------------------------- 42

@oauth_bp.route('/42/login')
def fortytwo_login():
    """Start the 42 authorization flow with a short-lived state token."""
    config = provider_config('42')
    if not config['client_id'] or not config['redirect_uri']:
        return oauth_not_configured(config['label'])

    state = create_oauth_state('42')
    query = urlencode({
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': 'public',
        'state': state,
    })
    return redirect(f'https://api.intra.42.fr/oauth/authorize?{query}')


@oauth_bp.route('/42/callback')
def fortytwo_callback():
    """Complete the 42 callback through the shared provider flow."""
    return complete_callback('42')


# ------------------------------------------------------------------ google

@oauth_bp.route('/google/login')
def google_login():
    """Start the Google authorization flow with a short-lived state token."""
    config = provider_config('google')
    if not config['client_id'] or not config['redirect_uri']:
        return oauth_not_configured(config['label'])

    state = create_oauth_state('google')
    query = urlencode({
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    })
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{query}')


@oauth_bp.route('/google/callback')
def google_callback():
    """Complete the Google callback through the shared provider flow."""
    return complete_callback('google')
