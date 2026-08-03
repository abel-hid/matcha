import unittest
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from unittest.mock import patch

from app import create_app
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


class SocialRouteTests(unittest.TestCase):
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
        self.current_user = self.make_user(4, 'current')
        self.target = self.make_user(8, 'target')

        with (
            patch('app.auth.models.get_user_by_username', return_value=self.current_user),
            patch('app.auth.models.check_password', return_value=True),
            patch('app.auth.models.user_to_dict', return_value={'id': 4}),
            patch('app.auth.models.create_session', return_value='11111111-1111-1111-1111-111111111111'),
        ):
            response = self.client.post('/api/auth/login', json={
                'username': 'current',
                'password': 'Maple!Orbit73',
            })

        self.assertEqual(response.status_code, 200)
        self.csrf = self.client.get_cookie('csrf_access_token').value

    @staticmethod
    def make_user(user_id, username):
        return {
            'id': user_id,
            'username': username,
            'email': f'{username}@example.com',
            'first_name': username.title(),
            'last_name': 'User',
            'password_hash': '$2b$12$valid-for-mocked-check',
            'birth_date': date(2000, 1, 1),
            'gender': 'male',
            'sexual_preferences': ['female'],
            'biography': 'Biography',
            'fame_rating': 10.0,
            'latitude': 35.7,
            'longitude': -5.8,
            'location_name': 'Tangier',
            'gps_consent': False,
            'is_verified': True,
            'is_online': False,
            'last_activity': datetime(2026, 7, 28, 12, 0),
            'token_version': 0,
        }

    def post(self, path):
        return self.client.post(path, headers={'X-CSRF-TOKEN': self.csrf})

    def delete(self, path):
        return self.client.delete(path, headers={'X-CSRF-TOKEN': self.csrf})

    @contextmanager
    def social_access(self, current_complete=True, target_complete=True):
        def get_user(user_id):
            if user_id == 4:
                return self.current_user
            if user_id == 8:
                return self.target
            return None

        def get_tags(user_id):
            complete = current_complete if user_id == 4 else target_complete
            return [{'id': 1, 'name': 'music'}] if complete else []

        def get_photos(user_id):
            complete = current_complete if user_id == 4 else target_complete
            if not complete:
                return []
            return [{
                'id': user_id,
                'user_id': user_id,
                'filename': f'{user_id}.jpg',
                'is_primary': True,
                'position': 0,
            }]

        with ExitStack() as stack:
            stack.enter_context(patch('app.models.is_session_active', return_value=True))
            stack.enter_context(patch('app.models.get_user_by_id', side_effect=get_user))
            stack.enter_context(patch('app.models.get_tags_for_user', side_effect=get_tags))
            stack.enter_context(patch('app.models.get_photos_for_user', side_effect=get_photos))
            yield

    def test_incomplete_user_cannot_access_social_routes(self):
        with self.social_access(current_complete=False):
            response = self.client.get('/api/users/8')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'PROFILE_INCOMPLETE')
        self.assertIn('tags', response.get_json()['missingFields'])

    def test_incomplete_target_is_not_public(self):
        with self.social_access(target_complete=False):
            response = self.client.get('/api/users/8')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['message'], 'User not found')

    def test_profile_get_is_read_only_and_visit_id_is_duplicate_safe(self):
        visit_id = '22222222-2222-2222-2222-222222222222'
        with (
            self.social_access(),
            patch('app.users.models.is_blocked_either_way', return_value=False),
            patch('app.users.models.record_view', side_effect=[{'id': 1}, None]) as record_view,
            patch('app.users.models.create_notification') as create_notification,
            patch('app.users.models.update_fame_rating') as update_fame,
            patch('app.users.models.user_to_dict', return_value={'id': 8}),
            patch('app.users.models.has_liked', return_value=False),
            patch('app.users.models.has_reported', return_value=False),
        ):
            profile = self.client.get('/api/users/8')
            first_visit = self.client.post(
                '/api/users/8/visit',
                json={'visitId': visit_id},
                headers={'X-CSRF-TOKEN': self.csrf},
            )
            repeated_visit = self.client.post(
                '/api/users/8/visit',
                json={'visitId': visit_id},
                headers={'X-CSRF-TOKEN': self.csrf},
            )

        self.assertEqual(profile.status_code, 200)
        self.assertEqual(first_visit.status_code, 201)
        self.assertEqual(repeated_visit.status_code, 200)
        self.assertFalse(repeated_visit.get_json()['recorded'])
        self.assertEqual(record_view.call_count, 2)
        create_notification.assert_called_once_with(8, 'view', from_user_id=4)
        update_fame.assert_called_once_with(8)

    def test_duplicate_like_returns_controlled_409(self):
        with (
            self.social_access(),
            patch('app.users.models.is_blocked_either_way', return_value=False),
            patch('app.users.models.get_primary_photo', return_value={'id': 1}),
            patch('app.users.models.like_user', return_value=False),
        ):
            response = self.post('/api/users/8/like')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['message'], 'You already liked this user')

    def test_connected_unlike_creates_the_required_notification(self):
        with (
            self.social_access(),
            patch('app.users.models.is_blocked_either_way', return_value=False),
            patch('app.users.models.unlike_user', return_value=(True, True)),
            patch('app.users.models.create_notification') as create_notification,
            patch('app.users.models.update_fame_rating'),
            patch('app.users.emit_conversation_status') as emit_status,
        ):
            response = self.delete('/api/users/8/like')

        self.assertEqual(response.status_code, 200)
        create_notification.assert_called_once_with(8, 'unlike', from_user_id=4)
        emit_status.assert_called_once_with(4, 8, False, 'unlike', 4)

    def test_block_removes_both_likes_and_recalculates_both_fame_ratings(self):
        with (
            self.social_access(),
            patch('app.users.models.block_user', return_value={
                'created': True,
                'removed_likes': [
                    {'liker_id': 4, 'liked_id': 8},
                    {'liker_id': 8, 'liked_id': 4},
                ],
                'was_connected': True,
            }) as block_user,
            patch('app.users.models.update_fame_rating') as update_fame,
            patch('app.users.emit_conversation_status') as emit_status,
        ):
            response = self.post('/api/users/8/block')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['removedLikes'], 2)
        self.assertTrue(response.get_json()['wasConnected'])
        block_user.assert_called_once_with(4, 8)
        self.assertEqual(update_fame.call_args_list[0].args, (4,))
        self.assertEqual(update_fame.call_args_list[1].args, (8,))
        emit_status.assert_called_once_with(4, 8, False, 'block', 4)

    def test_blocked_user_cannot_trigger_unlike(self):
        with (
            self.social_access(),
            patch('app.users.models.is_blocked_either_way', return_value=True),
            patch('app.users.models.unlike_user') as unlike_user,
            patch('app.users.models.create_notification') as create_notification,
        ):
            response = self.delete('/api/users/8/like')

        self.assertEqual(response.status_code, 404)
        unlike_user.assert_not_called()
        create_notification.assert_not_called()

    def test_activity_endpoint_returns_four_relationship_groups(self):
        with (
            self.social_access(),
            patch('app.profile.models.get_viewers', return_value=[]),
            patch('app.profile.models.get_outgoing_pending_likes', return_value=[]),
            patch('app.profile.models.get_incoming_pending_likes', return_value=[]),
            patch('app.profile.models.get_matches', return_value=[]),
        ):
            response = self.client.get('/api/profile/activity')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'visits': [],
            'likedByMe': [],
            'likedMe': [],
            'matches': [],
        })

    def test_duplicate_report_returns_controlled_409(self):
        with (
            self.social_access(),
            patch('app.users.models.is_blocked_either_way', return_value=False),
            patch('app.users.models.create_report', return_value=None),
        ):
            response = self.post('/api/users/8/report')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['message'], 'You have already reported this user')

    def test_blocked_users_endpoint_returns_the_settings_list(self):
        blocked_row = dict(self.target)
        blocked_row['blocked_at'] = datetime(2026, 7, 28, 15, 0)
        with (
            self.social_access(),
            patch('app.users.models.get_blocked_users', return_value=[blocked_row]),
            patch('app.users.models.blocked_user_to_dict', return_value={
                'blockedAt': '2026-07-28T15:00:00Z',
                'user': {'id': 8},
            }),
        ):
            response = self.client.get('/api/users/blocked')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['blocks'][0]['user']['id'], 8)


if __name__ == '__main__':
    unittest.main()
