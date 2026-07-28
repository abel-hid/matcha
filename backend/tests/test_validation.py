import unittest

from app.validation import (
    normalize_email,
    validate_password,
    validate_registration_data,
    validate_username,
)


class ValidationTests(unittest.TestCase):
    def test_registration_normalizes_safe_values(self):
        registration, error = validate_registration_data({
            'username': '  user_42  ',
            'email': '  USER@example.com ',
            'firstName': '  Jean  Luc ',
            'lastName': " O'Connor ",
            'password': 'Strong!Pass42',
        })

        self.assertIsNone(error)
        self.assertEqual(registration['username'], 'user_42')
        self.assertEqual(registration['email'], 'user@example.com')
        self.assertEqual(registration['first_name'], 'Jean Luc')
        self.assertEqual(registration['last_name'], "O'Connor")

    def test_registration_rejects_non_string_values(self):
        registration, error = validate_registration_data({
            'username': 'user_42',
            'email': 123,
            'firstName': 'Jean',
            'lastName': 'Test',
            'password': 'Strong!Pass42',
        })

        self.assertIsNone(registration)
        self.assertEqual(error, 'Email must be a string')

    def test_username_rejects_unsupported_characters(self):
        username, error = validate_username('user name')

        self.assertIsNone(username)
        self.assertEqual(error, 'Username may contain only letters, numbers, and underscores')

    def test_email_is_lowercased(self):
        email, error = normalize_email(' User@Example.COM ')

        self.assertIsNone(error)
        self.assertEqual(email, 'user@example.com')

    def test_common_password_with_suffix_is_rejected(self):
        valid, error = validate_password('Password1!')

        self.assertFalse(valid)
        self.assertEqual(error, 'Password is too common')

    def test_multilingual_common_password_is_rejected(self):
        valid, error = validate_password('Bienvenue1!')

        self.assertFalse(valid)
        self.assertEqual(error, 'Password is too common')

    def test_password_based_on_account_details_is_rejected(self):
        valid, error = validate_password(
            'MatchaUser42!',
            account_values=['user42', 'user42@example.com'],
        )

        self.assertFalse(valid)
        self.assertEqual(error, 'Password must not be based on your account details')

    def test_strong_unrelated_password_is_accepted(self):
        valid, error = validate_password(
            'Maple!Orbit73',
            account_values=['user42', 'user42@example.com', 'Jean', 'Test'],
        )

        self.assertTrue(valid)
        self.assertEqual(error, 'Password is valid')


if __name__ == '__main__':
    unittest.main()
