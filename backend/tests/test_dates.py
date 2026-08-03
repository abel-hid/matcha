import unittest
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta, timezone
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


class DateRouteTests(unittest.TestCase):
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

    @contextmanager
    def date_access(self, current_complete=True, target_complete=True):
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

    def post(self, path, json):
        return self.client.post(
            path,
            json=json,
            headers={'X-CSRF-TOKEN': self.csrf},
        )

    def put(self, path, json=None):
        return self.client.put(
            path,
            json=json,
            headers={'X-CSRF-TOKEN': self.csrf},
        )

    def future_iso(self):
        return (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    def event(self, status='pending'):
        now = datetime.now(timezone.utc)
        return {
            'id': 12,
            'proposer_id': 4,
            'recipient_id': 8,
            'scheduled_for': now + timedelta(days=2),
            'location': 'Coffee shop',
            'note': 'Near the station',
            'status': status,
            'created_at': now,
            'updated_at': now,
        }

    def test_incomplete_user_cannot_access_dates(self):
        with self.date_access(current_complete=False):
            response = self.client.get('/api/dates')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'PROFILE_INCOMPLETE')

    def test_connected_user_can_create_date_proposal(self):
        event = self.event()
        serialized = {'id': 12, 'status': 'pending'}

        with (
            self.date_access(),
            patch('app.dates.models.is_blocked_either_way', return_value=False),
            patch('app.dates.models.is_connected', return_value=True),
            patch('app.dates.models.create_date_event', return_value=event) as create,
            patch('app.dates.emit_date_event', return_value=serialized),
            patch('app.dates.models.create_notification') as notify,
        ):
            response = self.post('/api/dates/8', {
                'scheduledFor': self.future_iso(),
                'location': '  Coffee shop  ',
                'note': '  Near the station  ',
            })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['event'], serialized)
        self.assertEqual(create.call_args.args[0:2], (4, 8))
        self.assertEqual(create.call_args.args[3:], ('Coffee shop', 'Near the station'))
        notify.assert_called_once_with(
            8,
            'date',
            from_user_id=4,
            content='current proposed a date',
        )

    def test_disconnected_user_cannot_create_date_proposal(self):
        with (
            self.date_access(),
            patch('app.dates.models.is_blocked_either_way', return_value=False),
            patch('app.dates.models.is_connected', return_value=False),
            patch('app.dates.models.create_date_event') as create,
        ):
            response = self.post('/api/dates/8', {
                'scheduledFor': self.future_iso(),
                'location': 'Coffee shop',
            })

        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_past_date_is_rejected(self):
        with (
            self.date_access(),
            patch('app.dates.models.is_blocked_either_way', return_value=False),
            patch('app.dates.models.is_connected', return_value=True),
        ):
            response = self.post('/api/dates/8', {
                'scheduledFor': (
                    datetime.now(timezone.utc) - timedelta(minutes=1)
                ).isoformat(),
                'location': 'Coffee shop',
            })

        self.assertEqual(response.status_code, 400)
        self.assertIn('future', response.get_json()['message'])

    def test_recipient_can_accept_pending_proposal(self):
        event = self.event()
        event['recipient_id'] = 4
        event['proposer_id'] = 8
        updated = {**event, 'status': 'accepted'}

        with (
            self.date_access(),
            patch('app.dates.models.get_date_event', return_value=event),
            patch('app.dates.models.is_blocked_either_way', return_value=False),
            patch('app.dates.models.is_connected', return_value=True),
            patch('app.dates.models.respond_to_date_event', return_value=updated),
            patch('app.dates.emit_date_event', return_value={'id': 12, 'status': 'accepted'}),
            patch('app.dates.models.create_notification'),
        ):
            response = self.put('/api/dates/12/respond', {'status': 'accepted'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['event']['status'], 'accepted')

    def test_non_participant_cannot_cancel(self):
        event = self.event()
        event['proposer_id'] = 8
        event['recipient_id'] = 9

        with (
            self.date_access(),
            patch('app.dates.models.get_date_event', return_value=event),
            patch('app.dates.models.cancel_date_event') as cancel,
        ):
            response = self.put('/api/dates/12/cancel')

        self.assertEqual(response.status_code, 404)
        cancel.assert_not_called()


if __name__ == '__main__':
    unittest.main()
