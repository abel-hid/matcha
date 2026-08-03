import unittest
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from unittest.mock import patch

from app import create_app
from app import models
from app.config import Config


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


class DiscoverRouteTests(unittest.TestCase):
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
        self.current_user = {
            'id': 4,
            'username': 'current',
            'email': 'current@example.com',
            'first_name': 'Current',
            'last_name': 'User',
            'password_hash': '$2b$12$valid-for-mocked-check',
            'birth_date': date(2000, 1, 1),
            'gender': 'male',
            'sexual_preferences': ['female'],
            'biography': 'Biography',
            'fame_rating': 10.0,
            'latitude': 33.9904,
            'longitude': -6.8480,
            'location_name': 'Agdal, Rabat',
            'gps_consent': False,
            'is_verified': True,
            'is_online': False,
            'last_activity': datetime(2026, 8, 1, 12, 0),
            'token_version': 0,
        }

        with (
            patch(
                'app.auth.models.get_user_by_username',
                return_value=self.current_user,
            ),
            patch('app.auth.models.check_password', return_value=True),
            patch('app.auth.models.user_to_dict', return_value={'id': 4}),
            patch(
                'app.auth.models.create_session',
                return_value='11111111-1111-1111-1111-111111111111',
            ),
        ):
            response = self.client.post('/api/auth/login', json={
                'username': 'current',
                'password': 'Maple!Orbit73',
            })

        self.assertEqual(response.status_code, 200)

    @contextmanager
    def complete_access(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch('app.models.is_session_active', return_value=True)
            )
            stack.enter_context(
                patch('app.models.get_user_by_id', return_value=self.current_user)
            )
            stack.enter_context(
                patch(
                    'app.models.get_tags_for_user',
                    return_value=[{'id': 1, 'name': 'music'}],
                )
            )
            stack.enter_context(
                patch(
                    'app.models.get_photos_for_user',
                    return_value=[{
                        'id': 1,
                        'user_id': 4,
                        'filename': 'current.png',
                        'is_primary': True,
                        'position': 0,
                    }],
                )
            )
            yield

    def test_default_discover_request_uses_subject_criteria(self):
        with (
            self.complete_access(),
            patch(
                'app.discover.models.discover_users',
                return_value={
                    'profiles': [],
                    'total': 0,
                    'total_pages': 0,
                },
            ) as discover_users,
        ):
            response = self.client.get('/api/discover')

        self.assertEqual(response.status_code, 200)
        filters = discover_users.call_args.args[1]
        self.assertEqual(filters['min_age'], 18)
        self.assertEqual(filters['max_age'], 80)
        self.assertEqual(filters['min_fame'], 0)
        self.assertEqual(filters['max_fame'], 100)
        self.assertEqual(filters['sort'], 'recommended')
        self.assertEqual(filters['tag_ids'], [])

    def test_invalid_age_and_fame_ranges_are_rejected(self):
        with self.complete_access():
            age_response = self.client.get(
                '/api/discover?minAge=50&maxAge=20'
            )
            fame_response = self.client.get(
                '/api/discover?minFame=80&maxFame=20'
            )

        self.assertEqual(age_response.status_code, 400)
        self.assertEqual(
            age_response.get_json()['message'],
            'minAge cannot be greater than maxAge',
        )
        self.assertEqual(fame_response.status_code, 400)
        self.assertEqual(
            fame_response.get_json()['message'],
            'minFame cannot be greater than maxFame',
        )

    def test_invalid_sort_is_rejected(self):
        with self.complete_access():
            response = self.client.get('/api/discover?sort=unknown')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'Invalid sort value')

    def test_map_returns_only_approximate_candidate_coordinates(self):
        candidate = {
            'id': 8,
            'username': 'seed_008',
            'first_name': 'Sara',
            'last_name': 'Alaoui',
            'age': 27,
            'gender': 'female',
            'primary_filename': 'seed_profile_008_1.png',
            'fame_rating': 32.5,
            'tag_names': ['music', 'travel'],
            'is_online': False,
            'last_activity': datetime(2026, 8, 1, 12, 0),
            'location_name': 'Agdal, Rabat',
            'latitude': 33.9904123,
            'longitude': -6.8480456,
            'distance_km': 2.34,
            'common_tag_count': 2,
        }
        with (
            self.complete_access(),
            patch('app.discover.models.get_user_by_id', return_value=self.current_user),
            patch(
                'app.discover.models.discover_users',
                return_value={
                    'profiles': [candidate],
                    'total': 1,
                    'total_pages': 1,
                },
            ) as discover_users,
        ):
            response = self.client.get('/api/discover/map')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['profiles'][0]['location']['latitude'], 33.99)
        self.assertEqual(payload['profiles'][0]['location']['longitude'], -6.85)
        self.assertNotEqual(
            payload['profiles'][0]['location']['latitude'],
            candidate['latitude'],
        )
        filters = discover_users.call_args.args[1]
        self.assertEqual(filters['page_size'], 500)

    def test_selected_tags_are_validated_and_passed_to_the_query(self):
        with (
            self.complete_access(),
            patch(
                'app.discover.models.get_all_tags',
                return_value=[
                    {'id': 1, 'name': 'music'},
                    {'id': 2, 'name': 'travel'},
                ],
            ),
            patch(
                'app.discover.models.discover_users',
                return_value={
                    'profiles': [],
                    'total': 0,
                    'total_pages': 0,
                },
            ) as discover_users,
        ):
            response = self.client.get(
                '/api/discover?tagIds=1,2&location=Rabat'
            )

        self.assertEqual(response.status_code, 200)
        filters = discover_users.call_args.args[1]
        self.assertEqual(filters['tag_ids'], [1, 2])
        self.assertEqual(filters['location'], 'Rabat')


class DiscoverModelTests(unittest.TestCase):
    def test_discovery_query_uses_parameters_and_recommended_order(self):
        filters = {
            'min_age': 20,
            'max_age': 35,
            'min_fame': 10,
            'max_fame': 80,
            'location': 'Rabat',
            'tag_ids': [1, 2],
            'sort': 'recommended',
            'order': 'asc',
            'page': 2,
            'page_size': 12,
        }

        with (
            patch('app.models.query_one', return_value={'total': 25}),
            patch('app.models.query_all', return_value=[]) as query_all,
        ):
            result = models.discover_users(4, filters)

        sql, parameters = query_all.call_args.args
        self.assertIn(
            'same_area DESC, distance_km ASC, common_tag_count DESC',
            sql,
        )
        self.assertNotIn('Rabat', sql)
        self.assertIn('%Rabat%', parameters)
        self.assertIn([1, 2], parameters)
        self.assertEqual(parameters[-2:], (12, 12))
        self.assertEqual(result['total'], 25)
        self.assertEqual(result['total_pages'], 3)

    def test_discovery_serializer_exposes_ranking_information(self):
        profile = {
            'id': 8,
            'username': 'seed_008',
            'first_name': 'Sara',
            'last_name': 'Alaoui',
            'age': 27,
            'gender': 'female',
            'primary_filename': 'seed_profile_008_1.png',
            'fame_rating': 32.5,
            'tag_names': ['music', 'travel'],
            'is_online': False,
            'last_activity': datetime(2026, 8, 1, 12, 0),
            'location_name': 'Agdal, Rabat',
            'distance_km': 2.34,
            'common_tag_count': 2,
        }

        data = models.discovery_user_to_dict(profile)

        self.assertEqual(data['username'], 'seed_008')
        self.assertEqual(data['distanceKm'], 2.3)
        self.assertEqual(data['commonTagCount'], 2)
        self.assertEqual(data['tags'], ['music', 'travel'])

    def test_map_serializer_rounds_private_coordinates(self):
        profile = {
            'id': 8,
            'username': 'seed_008',
            'first_name': 'Sara',
            'last_name': 'Alaoui',
            'age': 27,
            'gender': 'female',
            'primary_filename': 'seed_profile_008_1.png',
            'fame_rating': 32.5,
            'tag_names': [],
            'is_online': False,
            'last_activity': datetime(2026, 8, 1, 12, 0),
            'location_name': 'Agdal, Rabat',
            'latitude': 33.9904123,
            'longitude': -6.8480456,
            'distance_km': 2.34,
            'common_tag_count': 0,
        }

        result = models.map_user_to_dict(profile)

        self.assertEqual(result['location'], {
            'name': 'Agdal, Rabat',
            'latitude': 33.99,
            'longitude': -6.85,
        })


if __name__ == '__main__':
    unittest.main()
