import unittest
from datetime import datetime
from unittest.mock import patch

from app import models


class MessageModelTests(unittest.TestCase):
    def test_chat_contacts_include_matches_history_and_block_exclusion(self):
        with patch('app.models.query_all', return_value=[]) as query_all:
            models.get_chat_contacts(4)

        sql, parameters = query_all.call_args.args
        self.assertIn('FROM user_likes mine', sql)
        self.assertIn('FROM user_likes theirs', sql)
        self.assertIn('last_message.id IS NOT NULL', sql)
        self.assertIn('FROM user_blocks blocked', sql)
        self.assertIn('primary_photo.is_primary = true', sql)
        self.assertEqual(parameters, (4,))

    def test_conversation_is_paginated_and_returned_oldest_first(self):
        with (
            patch(
                'app.models.query_one',
                return_value={'total': 125},
            ),
            patch('app.models.query_all', return_value=[]) as query_all,
        ):
            result = models.get_conversation(4, 8, page=2, page_size=50)

        sql, parameters = query_all.call_args.args
        self.assertIn('ORDER BY created_at DESC, id DESC', sql)
        self.assertIn('ORDER BY created_at ASC, id ASC', sql)
        self.assertEqual(parameters[-2:], (50, 50))
        self.assertEqual(result['total'], 125)
        self.assertEqual(result['total_pages'], 3)

    def test_mark_conversation_read_returns_updated_message_ids(self):
        with patch(
            'app.models.query_all',
            return_value=[{'id': 31}, {'id': 32}],
        ) as query_all:
            result = models.mark_conversation_read(4, 8)

        sql, parameters = query_all.call_args.args
        self.assertIn('receiver_id = %s', sql)
        self.assertIn('sender_id = %s', sql)
        self.assertIn('is_read = false', sql)
        self.assertIn('RETURNING id', sql)
        self.assertEqual(parameters, (4, 8))
        self.assertEqual(result, [31, 32])

    def test_unread_message_count_excludes_blocked_users(self):
        with patch(
            'app.models.query_one',
            return_value={'total': 3},
        ) as query_one:
            result = models.count_unread_messages(4)

        sql, parameters = query_one.call_args.args
        self.assertIn('FROM user_blocks blocked', sql)
        self.assertEqual(parameters, (4, 4, 4))
        self.assertEqual(result, 3)

    def test_message_serializer_uses_utc_timestamp(self):
        message = {
            'id': 9,
            'sender_id': 4,
            'receiver_id': 8,
            'content': 'Hello',
            'is_read': False,
            'created_at': datetime(2026, 8, 1, 20, 30),
        }

        result = models.message_to_dict(message)

        self.assertEqual(result['senderId'], 4)
        self.assertEqual(result['receiverId'], 8)
        self.assertEqual(result['createdAt'], '2026-08-01T20:30:00Z')


if __name__ == '__main__':
    unittest.main()
