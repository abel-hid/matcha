import secrets
import requests
from flask import Blueprint, request, redirect, session, current_app, jsonify

from app import models
from app.auth import attach_session_cookies

oauth_bp = Blueprint('oauth', __name__, url_prefix='/api/auth/oauth')


def finish_login(user):
    frontend_url = current_app.config['FRONTEND_URL']
    response = redirect(f"{frontend_url}/oauth-callback")
    return attach_session_cookies(response, user)


def redirect_with_error(reason):
    frontend_url = current_app.config['FRONTEND_URL']
    return redirect(f"{frontend_url}/login?error={reason}")


def oauth_not_configured(provider):
    return jsonify({'message': f'{provider} OAuth is not configured'}), 503


# --------------------------------------------------------------------- 42

@oauth_bp.route('/42/login')
def fortytwo_login():
    client_id = current_app.config['FORTYTWO_CLIENT_ID']
    redirect_uri = current_app.config['FORTYTWO_REDIRECT_URI']
    if not client_id or not redirect_uri:
        return oauth_not_configured('42')

    state = secrets.token_urlsafe(24)
    session['oauth_state_42'] = state
    params = (
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=public&state={state}"
    )
    return redirect(f"https://api.intra.42.fr/oauth/authorize{params}")


@oauth_bp.route('/42/callback')
def fortytwo_callback():
    client_id = current_app.config['FORTYTWO_CLIENT_ID']
    client_secret = current_app.config['FORTYTWO_CLIENT_SECRET']
    redirect_uri = current_app.config['FORTYTWO_REDIRECT_URI']
    if not all([client_id, client_secret, redirect_uri]):
        return oauth_not_configured('42')

    if request.args.get('state') != session.pop('oauth_state_42', None):
        return redirect_with_error('invalid_state')

    code = request.args.get('code')
    if not code:
        return redirect_with_error('missing_code')

    token_res = requests.post('https://api.intra.42.fr/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
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
    client_id = current_app.config['GOOGLE_CLIENT_ID']
    redirect_uri = current_app.config['GOOGLE_REDIRECT_URI']
    if not client_id or not redirect_uri:
        return oauth_not_configured('Google')

    state = secrets.token_urlsafe(24)
    session['oauth_state_google'] = state
    params = (
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=openid%20email%20profile&state={state}"
        f"&access_type=online&prompt=select_account"
    )
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth{params}")


@oauth_bp.route('/google/callback')
def google_callback():
    client_id = current_app.config['GOOGLE_CLIENT_ID']
    client_secret = current_app.config['GOOGLE_CLIENT_SECRET']
    redirect_uri = current_app.config['GOOGLE_REDIRECT_URI']
    if not all([client_id, client_secret, redirect_uri]):
        return oauth_not_configured('Google')

    if request.args.get('state') != session.pop('oauth_state_google', None):
        return redirect_with_error('invalid_state')

    code = request.args.get('code')
    if not code:
        return redirect_with_error('missing_code')

    token_res = requests.post('https://oauth2.googleapis.com/token', data={
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
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
