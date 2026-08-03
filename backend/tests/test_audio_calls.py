import unittest
from unittest.mock import patch

from app import sockets


class AudioCallSocketTests(unittest.TestCase):
    def setUp(self):
        sockets._calls.clear()
        sockets._user_calls.clear()

    def tearDown(self):
        sockets._calls.clear()
        sockets._user_calls.clear()

    @patch('app.sockets.uuid4', return_value='11111111-1111-1111-1111-111111111111')
    @patch('app.sockets.socketio.emit')
    @patch('app.sockets._call_user_payload')
    @patch('app.sockets._call_relationship_allowed', return_value=True)
    @patch('app.sockets._socket_user_id', return_value=4)
    def test_connected_user_can_start_audio_call(
        self,
        socket_user,
        relationship,
        user_payload,
        emit,
        uuid4,
    ):
        user_payload.side_effect = lambda user_id: {'id': user_id}

        response = sockets.handle_call_start({'recipientId': 8})

        self.assertTrue(response['ok'])
        self.assertEqual(response['callId'], str(uuid4.return_value))
        self.assertEqual(sockets._user_calls[4], response['callId'])
        self.assertEqual(sockets._user_calls[8], response['callId'])
        emit.assert_called_once_with(
            'call_incoming',
            {
                'callId': response['callId'],
                'caller': {'id': 4},
            },
            room='user:8',
        )

    @patch('app.sockets._call_relationship_allowed', return_value=False)
    @patch('app.sockets._socket_user_id', return_value=4)
    def test_disconnected_user_cannot_start_audio_call(self, socket_user, relationship):
        response = sockets.handle_call_start({'recipientId': 8})

        self.assertFalse(response['ok'])
        self.assertEqual(sockets._calls, {})

    @patch('app.sockets.socketio.emit')
    @patch('app.sockets._call_relationship_allowed', return_value=True)
    @patch('app.sockets._socket_user_id', return_value=8)
    def test_recipient_can_accept_ringing_call(self, socket_user, relationship, emit):
        call_id = 'call-1'
        sockets._calls[call_id] = {
            'id': call_id,
            'caller_id': 4,
            'recipient_id': 8,
            'status': 'ringing',
        }
        sockets._user_calls.update({4: call_id, 8: call_id})

        response = sockets.handle_call_accept({'callId': call_id})

        self.assertTrue(response['ok'])
        self.assertEqual(sockets._calls[call_id]['status'], 'active')
        self.assertEqual(emit.call_count, 2)


    @patch('app.sockets._socket_user_id', return_value=4)
    def test_malformed_call_id_returns_controlled_error(self, socket_user):
        response = sockets.handle_call_end({'callId': []})

        self.assertFalse(response['ok'])
        self.assertEqual(response['message'], 'Invalid call request')

    @patch('app.sockets.socketio.emit')
    @patch('app.sockets._socket_user_id', return_value=4)
    def test_invalid_webrtc_signal_is_not_relayed(self, socket_user, emit):
        call_id = 'call-1'
        sockets._calls[call_id] = {
            'id': call_id,
            'caller_id': 4,
            'recipient_id': 8,
            'status': 'active',
        }
        sockets._user_calls.update({4: call_id, 8: call_id})

        response = sockets.handle_call_signal({
            'callId': call_id,
            'type': 'offer',
            'signal': {'type': 'offer', 'sdp': None},
        })

        self.assertFalse(response['ok'])
        self.assertEqual(response['message'], 'Invalid call signal')
        emit.assert_not_called()

    @patch('app.sockets.socketio.emit')
    def test_call_owner_socket_disconnect_ends_call(self, emit):
        call_id = 'call-1'
        sockets._calls[call_id] = {
            'id': call_id,
            'caller_id': 4,
            'recipient_id': 8,
            'caller_sid': 'caller-sid',
            'recipient_sid': 'recipient-sid',
            'status': 'active',
        }
        sockets._user_calls.update({4: call_id, 8: call_id})

        ended = sockets.end_socket_call('caller-sid', 4, 'disconnected')

        self.assertTrue(ended)
        self.assertNotIn(call_id, sockets._calls)
        self.assertEqual(emit.call_count, 2)

    @patch('app.sockets.socketio.emit')
    def test_unlike_or_block_ends_call_between_users(self, emit):
        call_id = 'call-1'
        sockets._calls[call_id] = {
            'id': call_id,
            'caller_id': 4,
            'recipient_id': 8,
            'status': 'active',
        }
        sockets._user_calls.update({4: call_id, 8: call_id})

        ended = sockets.end_calls_between(4, 8, 'unlike')

        self.assertTrue(ended)
        self.assertNotIn(call_id, sockets._calls)
        self.assertNotIn(4, sockets._user_calls)
        self.assertNotIn(8, sockets._user_calls)
        self.assertEqual(emit.call_count, 2)


if __name__ == '__main__':
    unittest.main()
