import os
import secrets
import requests
from flask import Blueprint, request, redirect, session

from app import models

oauth_bp = Blueprint('oauth', __name__, url_prefix='/api/auth/oauth')

FRONTEND_URL = os.environ.get('FRONTEND_URL')

FORTYTWO_CLIENT_ID = os.environ['FORTYTWO_CLIENT_ID']
FORTYTWO_CLIENT_SECRET = os.environ['FORTYTWO_CLIENT_SECRET']
FORTYTWO_REDIRECT_URI = os.environ['FORTYTWO_REDIRECT_URI']

GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_REDIRECT_URI = os.environ['GOOGLE_REDIRECT_URI']


def finish_login(user):
    """Log the OAuth user in the same way password login does, then bounce
    back to the frontend with tokens as query params (frontend reads them
    once and stores them, same as it would after a normal /login call)."""
    models.update_user_fields(user['id'], {'is_online': True})
    access, refresh = models.get_tokens_for_user(user['id'])
    return redirect(f"{FRONTEND_URL}/oauth-callback?token={access}&refreshToken={refresh}")


def redirect_with_error(reason):
    return redirect(f"{FRONTEND_URL}/login?error={reason}")


# --------------------------------------------------------------------- 42

@oauth_bp.route('/42/login')
def fortytwo_login():
    state = secrets.token_urlsafe(24)
    session['oauth_state_42'] = state
    params = (
        f"?client_id={FORTYTWO_CLIENT_ID}"
        f"&redirect_uri={FORTYTWO_REDIRECT_URI}"
        f"&response_type=code&scope=public&state={state}"
    )
    return redirect(f"https://api.intra.42.fr/oauth/authorize{params}")


@oauth_bp.route('/42/callback')
def fortytwo_callback():
    if request.args.get('state') != session.pop('oauth_state_42', None):
        return redirect_with_error('invalid_state')

    code = request.args.get('code')
    if not code:
        return redirect_with_error('missing_code')

    token_res = requests.post('https://api.intra.42.fr/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': FORTYTWO_CLIENT_ID,
        'client_secret': FORTYTWO_CLIENT_SECRET,
        'code': code,
        'redirect_uri': FORTYTWO_REDIRECT_URI,
    })
    if token_res.status_code != 200:
        return redirect_with_error('token_exchange_failed')
    access_token = token_res.json()['access_token']

    me_res = requests.get(
        'https://api.intra.42.fr/v2/me',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    if me_res.status_code != 200:
        return redirect_with_error('profile_fetch_failed')
    profile = me_res.json()

    return resolve_user(
        provider='42',
        oauth_id=str(profile['id']),
        email=profile['email'],
        first_name=profile.get('first_name', ''),
        last_name=profile.get('last_name', ''),
        preferred_username=profile.get('login'),
    )


# ------------------------------------------------------------------ google

@oauth_bp.route('/google/login')
def google_login():
    state = secrets.token_urlsafe(24)
    session['oauth_state_google'] = state
    params = (
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code&scope=openid%20email%20profile&state={state}"
        f"&access_type=online&prompt=select_account"
    )
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth{params}")


@oauth_bp.route('/google/callback')
def google_callback():
    if request.args.get('state') != session.pop('oauth_state_google', None):
        return redirect_with_error('invalid_state')

    code = request.args.get('code')
    if not code:
        return redirect_with_error('missing_code')

    token_res = requests.post('https://oauth2.googleapis.com/token', data={
        'grant_type': 'authorization_code',
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'code': code,
        'redirect_uri': GOOGLE_REDIRECT_URI,
    })
    if token_res.status_code != 200:
        return redirect_with_error('token_exchange_failed')
    access_token = token_res.json()['access_token']

    me_res = requests.get(
        'https://www.googleapis.com/oauth2/v3/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    if me_res.status_code != 200:
        return redirect_with_error('profile_fetch_failed')
    profile = me_res.json()

    if not profile.get('email_verified', False):
        return redirect_with_error('email_not_verified')

    return resolve_user(
        provider='google',
        oauth_id=profile['sub'],
        email=profile['email'],
        first_name=profile.get('given_name', ''),
        last_name=profile.get('family_name', ''),
        preferred_username=profile.get('email', '').split('@')[0],
    )


# ------------------------------------------------------------- resolve user

def resolve_user(provider, oauth_id, email, first_name, last_name, preferred_username):
    user = models.get_user_by_oauth(provider, oauth_id)
    if user:
        return finish_login(user)

    existing = models.get_user_by_email(email)
    if existing:
        models.link_oauth_to_user(existing['id'], provider, oauth_id)
        return finish_login(models.get_user_by_id(existing['id']))

    username = models.generate_unique_username(preferred_username or email.split('@')[0])
    user = models.create_oauth_user(username, email, first_name, last_name, provider, oauth_id)
    return finish_login(user)