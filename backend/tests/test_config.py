import unittest

from app.config import Config


class ValidConfig(Config):
    SECRET_KEY = 'test-secret'
    DATABASE_URL = 'postgresql://matcha:test@localhost:5432/matcha'
    JWT_SECRET_KEY = 'test-jwt-secret'
    MAIL_SERVER = 'smtp.example.com'
    MAIL_DEFAULT_SENDER = 'noreply@example.com'
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    FRONTEND_URL = 'http://localhost:3000'

    FORTYTWO_CLIENT_ID = None
    FORTYTWO_CLIENT_SECRET = None
    FORTYTWO_REDIRECT_URI = None

    GOOGLE_CLIENT_ID = None
    GOOGLE_CLIENT_SECRET = None
    GOOGLE_REDIRECT_URI = None


class ConfigValidationTests(unittest.TestCase):
    def test_required_configuration_is_accepted(self):
        ValidConfig.validate()

    def test_missing_required_configuration_is_rejected(self):
        class MissingSecretConfig(ValidConfig):
            SECRET_KEY = None

        with self.assertRaisesRegex(RuntimeError, 'SECRET_KEY'):
            MissingSecretConfig.validate()

    def test_optional_oauth_configuration_may_be_absent(self):
        ValidConfig.validate()

    def test_partial_google_oauth_configuration_is_rejected(self):
        class PartialGoogleConfig(ValidConfig):
            GOOGLE_CLIENT_ID = 'google-client-id'

        with self.assertRaisesRegex(RuntimeError, 'GOOGLE_CLIENT_SECRET'):
            PartialGoogleConfig.validate()

    def test_mail_credentials_must_be_set_together(self):
        class PartialMailConfig(ValidConfig):
            MAIL_USERNAME = 'user@example.com'

        with self.assertRaisesRegex(RuntimeError, 'MAIL_PASSWORD'):
            PartialMailConfig.validate()


if __name__ == '__main__':
    unittest.main()
