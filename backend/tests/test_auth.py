import unittest
from unittest.mock import patch

from app import create_app
from app.config import Config


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-flask-secret'
    DATABASE_URL = 'postgresql://test:test@localhost/test'
    JWT_SECRET_KEY = 'test-jwt-secret'
    JWT_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    MAIL_SERVER = 'smtp.example.com'
    MAIL_DEFAULT_SENDER = 'noreply@example.com'
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    FRONTEND_URL = 'http://localhost:3000'
    CORS_ORIGINS = ['http://localhost:3000']
    FORTYTWO_CLIENT_ID = None
    FORTYTWO_CLIENT_SECRET = None
    FORTYTWO_REDIRECT_URI = None
    GOOGLE_CLIENT_ID = None
    GOOGLE_CLIENT_SECRET = None
    GOOGLE_REDIRECT_URI = None


class AuthRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool_patcher = patch('app.init_pool')
        cls.pool_patcher.start()
        cls.app = create_app(TestConfig)

    @classmethod
    def tearDownClass(cls):
        cls.pool_patcher.stop()

    def setUp(self):
        self.client = self.app.test_client()
        self.user = {
            'id': 7,
            'username': 'user_42',
            'email': 'user@example.com',
            'first_name': 'Jean',
            'last_name': 'Test',
            'password_hash': '$2b$12$valid-for-mocked-check',
            'is_verified': True,
            'token_version': 0,
        }

    def login(self):
        with (
            patch('app.auth.models.get_user_by_username', return_value=self.user),
            patch('app.auth.models.check_password', return_value=True),
            patch('app.auth.models.user_to_dict', return_value={'id': 7, 'username': 'user_42'}),
            patch('app.auth.models.create_session', return_value='11111111-1111-1111-1111-111111111111'),
        ):
            return self.client.post('/api/auth/login', json={
                'username': 'user_42',
                'password': 'Maple!Orbit73',
            })

    def test_login_sets_httponly_cookies_without_returning_tokens(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('token', response.get_json())
        self.assertNotIn('refreshToken', response.get_json())

        cookies = '\n'.join(response.headers.getlist('Set-Cookie'))
        self.assertIn('access_token_cookie=', cookies)
        self.assertIn('refresh_token_cookie=', cookies)
        self.assertIn('HttpOnly', cookies)
        self.assertIn('csrf_access_token=', cookies)
        self.assertIn('csrf_refresh_token=', cookies)


    def test_bootstrap_without_refresh_cookie_returns_clean_200_state(self):
        response = self.client.post('/api/auth/refresh/bootstrap')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'authenticated': False,
            'user': None,
        })

    def test_bootstrap_refreshes_access_cookie_and_returns_user(self):
        login_response = self.login()
        self.assertEqual(login_response.status_code, 200)

        csrf_cookie = self.client.get_cookie('csrf_refresh_token')
        self.assertIsNotNone(csrf_cookie)

        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.auth.models.get_user_by_id', return_value=self.user),
            patch('app.auth.models.touch_session') as touch_session,
            patch(
                'app.auth.models.user_to_dict',
                return_value={'id': 7, 'username': 'user_42'},
            ),
        ):
            response = self.client.post(
                '/api/auth/refresh/bootstrap',
                headers={'X-CSRF-TOKEN': csrf_cookie.value},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['authenticated'])
        self.assertEqual(response.get_json()['user']['id'], 7)
        touch_session.assert_called_once_with(
            '11111111-1111-1111-1111-111111111111'
        )
        cookies = '\n'.join(response.headers.getlist('Set-Cookie'))
        self.assertIn('access_token_cookie=', cookies)

    def test_oauth_only_account_returns_invalid_credentials(self):
        oauth_user = dict(self.user)
        oauth_user['password_hash'] = None

        with patch('app.auth.models.get_user_by_username', return_value=oauth_user):
            response = self.client.post('/api/auth/login', json={
                'username': 'user_42',
                'password': 'Maple!Orbit73',
            })

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['message'], 'Invalid credentials')

    def test_logout_revokes_the_server_session_and_clears_cookies(self):
        login_response = self.login()
        self.assertEqual(login_response.status_code, 200)

        csrf_cookie = self.client.get_cookie('csrf_access_token')
        self.assertIsNotNone(csrf_cookie)

        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.auth.models.revoke_session') as revoke_session,
        ):
            response = self.client.post(
                '/api/auth/logout',
                headers={'X-CSRF-TOKEN': csrf_cookie.value},
            )

        self.assertEqual(response.status_code, 200)
        revoke_session.assert_called_once_with('11111111-1111-1111-1111-111111111111')
        cookies = '\n'.join(response.headers.getlist('Set-Cookie'))
        self.assertIn('access_token_cookie=', cookies)
        self.assertIn('refresh_token_cookie=', cookies)
        self.assertTrue(
            'Max-Age=0' in cookies
            or 'Expires=Thu, 01 Jan 1970 00:00:00 GMT' in cookies
        )
    def test_forgot_password_is_neutral_for_unknown_and_mail_failure(self):
        with patch('app.auth.models.get_user_by_email', return_value=None):
            unknown_response = self.client.post(
                '/api/auth/forgot-password',
                json={'email': 'unknown@example.com'},
            )

        with (
            patch('app.auth.models.get_user_by_email', return_value=self.user),
            patch('app.auth.send_password_reset_email', side_effect=RuntimeError('smtp down')),
        ):
            existing_response = self.client.post(
                '/api/auth/forgot-password',
                json={'email': 'user@example.com'},
            )

        self.assertEqual(unknown_response.status_code, 200)
        self.assertEqual(existing_response.status_code, 200)
        self.assertEqual(unknown_response.get_json(), existing_response.get_json())

    def test_registration_email_failure_removes_the_new_account(self):
        with (
            patch('app.auth.models.get_user_by_username', return_value=None),
            patch('app.auth.models.get_user_by_email', return_value=None),
            patch('app.auth.models.create_user', return_value=self.user),
            patch('app.auth.send_verification_email', side_effect=RuntimeError('smtp down')),
            patch('app.auth.models.delete_user') as delete_user,
        ):
            response = self.client.post('/api/auth/register', json={
                'username': 'user_42',
                'email': 'user@example.com',
                'firstName': 'Jean',
                'lastName': 'Test',
                'password': 'Maple!Orbit73',
            })

        self.assertEqual(response.status_code, 503)
        delete_user.assert_called_once_with(7)

    def test_password_reset_increments_version_and_revokes_sessions(self):
        with (
            patch('app.auth.verify_reset_token', return_value=({'email': 'user@example.com', 'v': 0}, None)),
            patch('app.auth.models.get_user_by_email', return_value=self.user),
            patch('app.auth.models.reset_password_and_revoke_sessions') as reset_password,
        ):
            response = self.client.post('/api/auth/reset-password', json={
                'token': 'valid-token',
                'password': 'Maple!Orbit73',
            })

        self.assertEqual(response.status_code, 200)
        reset_password.assert_called_once_with(7, 'Maple!Orbit73', 1)

    def test_malformed_registration_value_returns_controlled_400(self):
        response = self.client.post('/api/auth/register', json={
            'username': 'user_42',
            'email': 123,
            'firstName': 'Jean',
            'lastName': 'Test',
            'password': 'Maple!Orbit73',
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'Email must be a string')


if __name__ == '__main__':
    unittest.main()
