import unittest
from datetime import date, datetime
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.utils import LocationServiceError
from app.validation import GENDER_VALUES


class TestConfig(Config):
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
    FORTYTWO_CLIENT_ID = None
    FORTYTWO_CLIENT_SECRET = None
    FORTYTWO_REDIRECT_URI = None
    GOOGLE_CLIENT_ID = None
    GOOGLE_CLIENT_SECRET = None
    GOOGLE_REDIRECT_URI = None


class ProfileRouteTests(unittest.TestCase):
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
            'username': 'profile_user',
            'email': 'profile@example.com',
            'first_name': 'Profile',
            'last_name': 'User',
            'password_hash': '$2b$12$valid-for-mocked-check',
            'birth_date': date(2000, 1, 1),
            'gender': None,
            'sexual_preferences': list(GENDER_VALUES),
            'biography': None,
            'fame_rating': 0.0,
            'latitude': None,
            'longitude': None,
            'location_name': None,
            'gps_consent': False,
            'is_verified': True,
            'is_online': False,
            'last_activity': datetime(2026, 7, 28, 12, 0, 0),
            'token_version': 0,
        }

        with (
            patch('app.auth.models.get_user_by_username', return_value=self.user),
            patch('app.auth.models.check_password', return_value=True),
            patch('app.auth.models.user_to_dict', return_value={'id': 7}),
            patch('app.auth.models.create_session', return_value='11111111-1111-1111-1111-111111111111'),
        ):
            response = self.client.post('/api/auth/login', json={
                'username': 'profile_user',
                'password': 'Maple!Orbit73',
            })

        self.assertEqual(response.status_code, 200)
        self.csrf = self.client.get_cookie('csrf_access_token').value

    def authenticated_put(self, path, payload):
        return self.client.put(
            path,
            json=payload,
            headers={'X-CSRF-TOKEN': self.csrf},
        )

    def authenticated_get(self, path):
        return self.client.get(path)

    def test_invalid_gender_returns_controlled_400(self):
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
        ):
            response = self.authenticated_put('/api/profile', {'gender': 'other'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'Gender must be male, female, or non-binary')

    def test_empty_preferences_are_rejected(self):
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch('app.profile.models.update_user_fields') as update_fields,
        ):
            response = self.authenticated_put('/api/profile', {'sexualPreferences': []})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['message'],
            'Select at least one sexual preference',
        )
        update_fields.assert_not_called()

    def test_blank_required_profile_fields_are_rejected(self):
        payloads = (
            ({'firstName': '   '}, 'First name is required'),
            ({'lastName': ''}, 'Last name is required'),
            ({'email': '   '}, 'Email is required'),
            ({'birthDate': ''}, 'Birth date is required'),
            ({'gender': ''}, 'Gender is required'),
            ({'biography': '   '}, 'Biography is required'),
        )

        for payload, expected_message in payloads:
            with self.subTest(payload=payload):
                with (
                    patch('app.models.is_session_active', return_value=True),
                    patch('app.profile.models.get_user_by_id', return_value=self.user),
                    patch('app.profile.models.update_user_fields') as update_fields,
                ):
                    response = self.authenticated_put('/api/profile', payload)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()['message'], expected_message)
                update_fields.assert_not_called()

    def test_string_false_is_not_accepted_as_gps_consent(self):
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
        ):
            response = self.authenticated_put('/api/profile/location', {
                'gpsConsent': 'false',
                'locationName': 'Rabat',
            })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'gpsConsent must be true or false')

    def test_zero_gps_coordinates_are_saved(self):
        private_user = {
            'location': {'name': 'Greenwich', 'latitude': 0.0, 'longitude': 0.0},
            'gpsConsent': True,
        }
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch('app.profile.reverse_geocode_location', return_value='Greenwich'),
            patch('app.profile.models.update_user_fields') as update_fields,
            patch('app.profile.models.update_fame_rating'),
            patch('app.profile.private_user_response', return_value=private_user),
        ):
            response = self.authenticated_put('/api/profile/location', {
                'gpsConsent': True,
                'latitude': 0,
                'longitude': 0,
            })

        self.assertEqual(response.status_code, 200)
        saved_fields = update_fields.call_args.args[1]
        self.assertEqual(saved_fields['latitude'], 0.0)
        self.assertEqual(saved_fields['longitude'], 0.0)

    def test_gps_coordinates_are_saved_when_reverse_lookup_is_unavailable(self):
        private_user = {
            'location': {
                'name': 'Approximate GPS location',
                'latitude': 35.7,
                'longitude': -5.8,
            },
            'gpsConsent': True,
        }
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch(
                'app.profile.reverse_geocode_location',
                side_effect=LocationServiceError('provider unavailable'),
            ),
            patch('app.profile.models.update_user_fields') as update_fields,
            patch('app.profile.models.update_fame_rating'),
            patch('app.profile.private_user_response', return_value=private_user),
        ):
            response = self.authenticated_put('/api/profile/location', {
                'gpsConsent': True,
                'latitude': 35.7,
                'longitude': -5.8,
            })

        self.assertEqual(response.status_code, 200)
        saved_fields = update_fields.call_args.args[1]
        self.assertEqual(saved_fields['location_name'], 'Approximate GPS location')

    def test_location_search_returns_candidates(self):
        results = [{
            'name': 'Bni Makada, Tangier, Morocco',
            'latitude': 35.75113,
            'longitude': -5.81877,
        }]
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch('app.profile.search_locations', return_value=results),
        ):
            response = self.authenticated_get(
                '/api/profile/location/search?q=Bni%20Makada%2C%20Tangier%2C%20Morocco'
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['results'], results)

    def test_location_search_provider_failure_returns_controlled_503(self):
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch(
                'app.profile.search_locations',
                side_effect=LocationServiceError('provider unavailable'),
            ),
        ):
            response = self.authenticated_get('/api/profile/location/search?q=Tangier')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()['message'],
            'Location search is temporarily unavailable. Try again shortly.',
        )

    def test_manual_location_saves_the_selected_coordinates(self):
        private_user = {
            'location': {
                'name': 'Bni Makada, Tangier, Morocco',
                'latitude': 35.75113,
                'longitude': -5.81877,
            },
            'gpsConsent': False,
        }
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch('app.profile.models.update_user_fields') as update_fields,
            patch('app.profile.models.update_fame_rating'),
            patch('app.profile.private_user_response', return_value=private_user),
        ):
            response = self.authenticated_put('/api/profile/location', {
                'gpsConsent': False,
                'locationName': 'Bni Makada, Tangier, Morocco',
                'latitude': 35.75113,
                'longitude': -5.81877,
            })

        self.assertEqual(response.status_code, 200)
        saved_fields = update_fields.call_args.args[1]
        self.assertFalse(saved_fields['gps_consent'])
        self.assertEqual(saved_fields['latitude'], 35.75113)
        self.assertEqual(saved_fields['longitude'], -5.81877)

    def test_manual_location_without_selected_coordinates_returns_400(self):
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch('app.profile.models.update_user_fields') as update_fields,
        ):
            response = self.authenticated_put('/api/profile/location', {
                'gpsConsent': False,
                'locationName': 'Tangier, Morocco',
            })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'latitude must be a number')
        self.assertFalse(update_fields.called)

    def test_empty_tag_selection_is_rejected(self):
        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch('app.profile.models.set_user_tags') as set_user_tags,
        ):
            response = self.authenticated_put('/api/profile/tags', {'tagIds': []})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'Select at least one interest')
        set_user_tags.assert_not_called()

    def test_last_photo_cannot_be_deleted(self):
        from app import models

        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch(
                'app.profile.models.delete_photo_and_promote',
                side_effect=models.LastPhotoError('At least one profile photo is required'),
            ),
            patch('app.profile.delete_saved_image') as delete_file,
        ):
            response = self.client.delete(
                '/api/profile/photos/1',
                headers={'X-CSRF-TOKEN': self.csrf},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()['message'],
            'At least one profile photo is required',
        )
        delete_file.assert_not_called()

    def test_unknown_tag_id_does_not_replace_existing_tags(self):
        from app import models

        with (
            patch('app.models.is_session_active', return_value=True),
            patch('app.profile.models.get_user_by_id', return_value=self.user),
            patch(
                'app.profile.models.set_user_tags',
                side_effect=models.InvalidTagIdsError('One or more selected tags are invalid'),
            ),
        ):
            response = self.authenticated_put('/api/profile/tags', {'tagIds': [999]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'One or more selected tags are invalid')


if __name__ == '__main__':
    unittest.main()
