import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import requests
from app import create_app
from app.config import Config


class OAuthTestConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-flask-secret-key-with-at-least-32-bytes'
    DATABASE_URL = 'postgresql://test:test@localhost/test'
    JWT_SECRET_KEY = 'test-jwt-secret-key-with-at-least-32-bytes'
    JWT_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    MAIL_SERVER = 'smtp.example.com'
    MAIL_DEFAULT_SENDER = 'noreply@example.com'
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    FRONTEND_URL = 'http://localhost:3000'
    CORS_ORIGINS = ['http://localhost:3000']
    FORTYTWO_CLIENT_ID = '42-client'
    FORTYTWO_CLIENT_SECRET = '42-secret'
    FORTYTWO_REDIRECT_URI = 'http://localhost:5000/api/auth/oauth/42/callback'
    GOOGLE_CLIENT_ID = 'google-client'
    GOOGLE_CLIENT_SECRET = 'google-secret'
    GOOGLE_REDIRECT_URI = 'http://localhost:5000/api/auth/oauth/google/callback'
    OAUTH_TIMEOUT_SECONDS = 3
    OAUTH_STATE_MAX_AGE_SECONDS = 600


class OAuthRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool_patcher = patch('app.init_pool')
        cls.pool_patcher.start()
        cls.app = create_app(OAuthTestConfig)

    @classmethod
    def tearDownClass(cls):
        cls.pool_patcher.stop()

    def setUp(self):
        self.client = self.app.test_client()

    def set_state(self, provider, value='valid-state', age=0):
        with self.client.session_transaction() as oauth_session:
            oauth_session[f'oauth_state_{provider}'] = {
                'value': value,
                'createdAt': int(time.time()) - age,
            }

    def test_login_uses_encoded_redirect_uri_and_server_side_state(self):
        response = self.client.get('/api/auth/oauth/google/login')

        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.location)
        query = parse_qs(parsed.query)
        self.assertEqual(query['client_id'], ['google-client'])
        self.assertEqual(
            query['redirect_uri'],
            ['http://localhost:5000/api/auth/oauth/google/callback'],
        )
        self.assertEqual(query['scope'], ['openid email profile'])
        self.assertTrue(query['state'][0])

        with self.client.session_transaction() as oauth_session:
            stored = oauth_session['oauth_state_google']
        self.assertEqual(stored['value'], query['state'][0])
        self.assertIsInstance(stored['createdAt'], int)

    def test_expired_state_is_rejected_before_provider_requests(self):
        self.set_state('google', age=601)
        with patch('app.oauth.requests.request') as provider_request:
            response = self.client.get(
                '/api/auth/oauth/google/callback?state=valid-state&code=code'
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login?error=invalid_state'))
        provider_request.assert_not_called()

    def test_provider_denial_returns_controlled_error(self):
        self.set_state('42')
        response = self.client.get(
            '/api/auth/oauth/42/callback?state=valid-state&error=access_denied'
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login?error=access_denied'))

    def test_provider_timeout_returns_controlled_error(self):
        self.set_state('42')
        with patch(
            'app.oauth.requests.request',
            side_effect=requests.Timeout('provider timeout'),
        ):
            response = self.client.get(
                '/api/auth/oauth/42/callback?state=valid-state&code=code'
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login?error=provider_unavailable'))

    def test_google_requires_verified_email(self):
        self.set_state('google')
        with (
            patch('app.oauth.exchange_access_token', return_value='access-token'),
            patch('app.oauth.fetch_provider_profile', return_value={
                'sub': 'google-1',
                'email': 'user@example.com',
                'email_verified': False,
            }),
        ):
            response = self.client.get(
                '/api/auth/oauth/google/callback?state=valid-state&code=code'
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login?error=email_not_verified'))

    def test_existing_email_is_linked_without_replacing_local_account(self):
        existing = {'id': 7, 'email': 'user@example.com'}
        refreshed = {'id': 7, 'token_version': 0}
        login_result = object()
        with (
            patch('app.oauth.models.get_user_by_oauth', return_value=None),
            patch('app.oauth.models.get_user_by_email', return_value=existing),
            patch('app.oauth.models.link_oauth_to_user') as link_identity,
            patch('app.oauth.models.get_user_by_id', return_value=refreshed),
            patch('app.oauth.finish_login', return_value=login_result),
        ):
            from app.oauth import resolve_user
            with self.app.test_request_context():
                response = resolve_user(
                    provider='google',
                    oauth_id='google-7',
                    email='user@example.com',
                    first_name='User',
                    last_name='Test',
                    preferred_username='user',
                )

        self.assertIs(response, login_result)
        link_identity.assert_called_once_with(
            7,
            'google',
            'google-7',
            'user@example.com',
        )

    def test_new_oauth_user_is_created_with_provider_identity(self):
        created = {'id': 9, 'token_version': 0}
        login_result = object()
        with (
            patch('app.oauth.models.get_user_by_oauth', return_value=None),
            patch('app.oauth.models.get_user_by_email', return_value=None),
            patch('app.oauth.models.generate_unique_username', return_value='new_user'),
            patch('app.oauth.models.create_oauth_user', return_value=created) as create_user,
            patch('app.oauth.finish_login', return_value=login_result),
        ):
            from app.oauth import resolve_user
            with self.app.test_request_context():
                response = resolve_user(
                    provider='42',
                    oauth_id='42-9',
                    email='new@example.com',
                    first_name='New',
                    last_name='User',
                    preferred_username='new',
                )

        self.assertIs(response, login_result)
        create_user.assert_called_once_with(
            'new_user',
            'new@example.com',
            'New',
            'User',
            '42',
            '42-9',
        )


if __name__ == '__main__':
    unittest.main()
