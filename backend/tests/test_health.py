import unittest
from unittest.mock import patch

from app import create_app
from app.config import Config


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-flask-secret-key-with-at-least-32-bytes'
    DATABASE_URL = 'postgresql://test:test@localhost/test'
    JWT_SECRET_KEY = 'test-jwt-secret-key-with-at-least-32-bytes'
    MAIL_SERVER = 'smtp.example.com'
    MAIL_DEFAULT_SENDER = 'noreply@example.com'
    FRONTEND_URL = 'http://localhost:3000'
    CORS_ORIGINS = ['http://localhost:3000']
    FORTYTWO_CLIENT_ID = None
    FORTYTWO_CLIENT_SECRET = None
    FORTYTWO_REDIRECT_URI = None
    GOOGLE_CLIENT_ID = None
    GOOGLE_CLIENT_SECRET = None
    GOOGLE_REDIRECT_URI = None


class HealthRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool_patcher = patch('app.init_pool')
        cls.pool_patcher.start()
        cls.app = create_app(TestConfig)
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.pool_patcher.stop()

    def test_health_checks_database_and_returns_200(self):
        with patch('app.query_one', return_value={'ready': 1}) as query_one:
            response = self.client.get('/api/health')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'ok'})
        query_one.assert_called_once_with('SELECT 1 AS ready')


if __name__ == '__main__':
    unittest.main()
