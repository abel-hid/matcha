import unittest
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from unittest.mock import call, patch

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


class MessageRouteTests(unittest.TestCase):
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
            patch(
                'app.auth.models.get_user_by_username',
                return_value=self.current_user,
            ),
            patch('app.auth.models.check_password', return_value=True),
            patch(
                'app.auth.models.user_to_dict',
                return_value={'id': 4},
            ),
            patch(
                'app.auth.models.create_session',
                return_value=(
                    '11111111-1111-1111-1111-111111111111'
                ),
            ),
        ):
            response = self.client.post('/api/auth/login', json={
                'username': 'current',
                'password': 'Maple!Orbit73',
            })

        self.assertEqual(response.status_code, 200)
        self.csrf = self.client.get_cookie(
            'csrf_access_token'
        ).value

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
    def message_access(self, current_complete=True, target_complete=True):
        def get_user(user_id):
            if user_id == 4:
                return self.current_user
            if user_id == 8:
                return self.target
            return None

        def get_tags(user_id):
            complete = (
                current_complete
                if user_id == 4
                else target_complete
            )
            return [{'id': 1, 'name': 'music'}] if complete else []

        def get_photos(user_id):
            complete = (
                current_complete
                if user_id == 4
                else target_complete
            )
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
            stack.enter_context(patch(
                'app.models.is_session_active',
                return_value=True,
            ))
            stack.enter_context(patch(
                'app.models.get_user_by_id',
                side_effect=get_user,
            ))
            stack.enter_context(patch(
                'app.models.get_tags_for_user',
                side_effect=get_tags,
            ))
            stack.enter_context(patch(
                'app.models.get_photos_for_user',
                side_effect=get_photos,
            ))
            yield

    def post(self, path, json=None):
        return self.client.post(
            path,
            json=json,
            headers={'X-CSRF-TOKEN': self.csrf},
        )

    def put(self, path):
        return self.client.put(
            path,
            headers={'X-CSRF-TOKEN': self.csrf},
        )

    def test_incomplete_user_cannot_access_messages(self):
        with self.message_access(current_complete=False):
            response = self.client.get('/api/messages')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()['code'],
            'PROFILE_INCOMPLETE',
        )

    def test_conversation_list_returns_connected_and_historical_chats(self):
        contact = dict(self.target)
        contact.update({
            'primary_filename': '8.jpg',
            'can_message': True,
            'unread_count': 2,
            'last_message_id': None,
        })

        with (
            self.message_access(),
            patch(
                'app.messages.models.get_chat_contacts',
                return_value=[contact],
            ),
            patch(
                'app.messages.models.count_unread_messages',
                return_value=2,
            ),
        ):
            response = self.client.get('/api/messages')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['unreadCount'], 2)
        self.assertEqual(
            response.get_json()['conversations'][0]['user']['username'],
            'target',
        )

    def test_connected_user_can_send_message_and_receiver_is_notified(self):
        message = {
            'id': 21,
            'sender_id': 4,
            'receiver_id': 8,
            'content': 'Hello there',
            'is_read': False,
            'created_at': datetime(2026, 8, 1, 20, 0),
        }

        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=False,
            ),
            patch(
                'app.messages.models.is_connected',
                return_value=True,
            ),
            patch(
                'app.messages.models.create_message',
                return_value=message,
            ) as create_message,
            patch(
                'app.messages.models.create_notification',
            ) as create_notification,
            patch('app.messages.socketio.emit') as emit,
        ):
            response = self.post(
                '/api/messages/8',
                {'content': '  Hello there  '},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json()['message']['content'],
            'Hello there',
        )
        create_message.assert_called_once_with(4, 8, 'Hello there')
        create_notification.assert_called_once_with(
            8,
            'message',
            from_user_id=4,
        )
        self.assertEqual(emit.call_count, 2)
        self.assertEqual(
            emit.call_args_list,
            [
                call(
                    'message',
                    response.get_json()['message'],
                    room='user:8',
                ),
                call(
                    'message',
                    response.get_json()['message'],
                    room='user:4',
                ),
            ],
        )

    def test_disconnected_user_cannot_send_message(self):
        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=False,
            ),
            patch(
                'app.messages.models.is_connected',
                return_value=False,
            ),
            patch(
                'app.messages.models.create_message',
            ) as create_message,
        ):
            response = self.post(
                '/api/messages/8',
                {'content': 'Not allowed'},
            )

        self.assertEqual(response.status_code, 403)
        create_message.assert_not_called()

    def test_disconnected_conversation_history_remains_read_only(self):
        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=False,
            ),
            patch(
                'app.messages.models.is_connected',
                return_value=False,
            ),
            patch(
                'app.messages.models.has_conversation_history',
                return_value=True,
            ),
            patch(
                'app.messages.models.get_conversation',
                return_value={
                    'messages': [],
                    'total': 0,
                    'total_pages': 0,
                },
            ),
            patch(
                'app.messages.models.chat_user_to_dict',
                return_value={'id': 8, 'username': 'target'},
            ),
        ):
            response = self.client.get('/api/messages/8')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['canMessage'])

    def test_unconnected_user_without_history_cannot_open_chat(self):
        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=False,
            ),
            patch(
                'app.messages.models.is_connected',
                return_value=False,
            ),
            patch(
                'app.messages.models.has_conversation_history',
                return_value=False,
            ),
        ):
            response = self.client.get('/api/messages/8')

        self.assertEqual(response.status_code, 403)

    def test_blocked_conversation_is_hidden(self):
        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=True,
            ),
        ):
            response = self.client.get('/api/messages/8')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()['message'],
            'Conversation not found',
        )

    def test_blank_and_oversized_messages_are_rejected(self):
        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=False,
            ),
            patch(
                'app.messages.models.is_connected',
                return_value=True,
            ),
            patch(
                'app.messages.models.create_message',
            ) as create_message,
        ):
            blank = self.post(
                '/api/messages/8',
                {'content': '   '},
            )
            oversized = self.post(
                '/api/messages/8',
                {'content': 'x' * 1001},
            )

        self.assertEqual(blank.status_code, 400)
        self.assertEqual(oversized.status_code, 400)
        create_message.assert_not_called()

    def test_open_conversation_can_mark_incoming_messages_read(self):
        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=False,
            ),
            patch(
                'app.messages.models.is_connected',
                return_value=True,
            ),
            patch(
                'app.messages.models.has_conversation_history',
                return_value=True,
            ),
            patch(
                'app.messages.models.mark_conversation_read',
                return_value=[31, 32],
            ) as mark_read,
            patch(
                'app.messages.models.count_unread_messages',
                return_value=3,
            ),
            patch('app.messages.socketio.emit') as emit,
        ):
            response = self.put('/api/messages/8/read')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['unreadCount'], 3)
        self.assertEqual(response.get_json()['readMessageIds'], [31, 32])
        mark_read.assert_called_once_with(4, 8)
        emit.assert_called_once_with(
            'message_read',
            {
                'readerId': 4,
                'messageIds': [31, 32],
            },
            room='user:8',
        )

    def test_read_route_does_not_emit_when_nothing_changed(self):
        with (
            self.message_access(),
            patch(
                'app.messages.models.is_blocked_either_way',
                return_value=False,
            ),
            patch(
                'app.messages.models.is_connected',
                return_value=True,
            ),
            patch(
                'app.messages.models.has_conversation_history',
                return_value=True,
            ),
            patch(
                'app.messages.models.mark_conversation_read',
                return_value=[],
            ),
            patch(
                'app.messages.models.count_unread_messages',
                return_value=0,
            ),
            patch('app.messages.socketio.emit') as emit,
        ):
            response = self.put('/api/messages/8/read')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['readMessageIds'], [])
        emit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
