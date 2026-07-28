import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app import models


class SocialModelTests(unittest.TestCase):
    def test_every_profile_view_inserts_a_new_history_row(self):
        with patch('app.models.execute', return_value={'id': 12}) as execute:
            result = models.record_view(4, 8, '11111111-1111-1111-1111-111111111111')

        self.assertEqual(result, {'id': 12})
        sql = execute.call_args.args[0]
        self.assertIn('INSERT INTO user_views', sql)
        self.assertNotIn('UPDATE user_views', sql)
        self.assertIn('ON CONFLICT (viewer_id, visit_id) DO NOTHING', sql)

    def test_like_is_duplicate_safe_and_clears_old_suppression(self):
        with (
            patch('app.models.execute', return_value={'liker_id': 4}),
            patch('app.models.clear_notification_suppression') as clear_suppression,
        ):
            created = models.like_user(4, 8)

        self.assertTrue(created)
        clear_suppression.assert_called_once_with(4, 8)

    def test_connected_unlike_suppresses_future_notifications_from_that_user(self):
        with (
            patch('app.models.is_connected', return_value=True),
            patch('app.models.execute', return_value={'liker_id': 4}),
            patch('app.models.suppress_notifications_from') as suppress,
        ):
            removed, was_connected = models.unlike_user(4, 8)

        self.assertTrue(removed)
        self.assertTrue(was_connected)
        suppress.assert_called_once_with(4, 8)

    def test_block_removes_both_directed_likes_in_the_same_transaction(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {'blocker_id': 4}
        cursor.fetchall.return_value = [
            {'liker_id': 4, 'liked_id': 8},
            {'liker_id': 8, 'liked_id': 4},
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        context = MagicMock()
        context.__enter__.return_value = conn

        with patch('app.models.get_conn', return_value=context):
            result = models.block_user(4, 8)

        self.assertTrue(result['created'])
        self.assertTrue(result['was_connected'])
        self.assertEqual(len(result['removed_likes']), 2)
        delete_sql = cursor.execute.call_args_list[1].args[0]
        self.assertIn('DELETE FROM user_likes', delete_sql)
        self.assertIn('(liker_id = %s AND liked_id = %s)', delete_sql)

    def test_activity_queries_split_pending_likes_and_matches(self):
        with patch('app.models.query_all', return_value=[]) as query_all:
            models.get_outgoing_pending_likes(4)
            outgoing_sql = query_all.call_args.args[0]
            models.get_incoming_pending_likes(4)
            incoming_sql = query_all.call_args.args[0]
            models.get_matches(4)
            matches_sql = query_all.call_args.args[0]

        self.assertIn('NOT EXISTS', outgoing_sql)
        self.assertIn('reverse_like', outgoing_sql)
        self.assertIn('my_like', incoming_sql)
        self.assertIn('GREATEST', matches_sql)

    def test_notification_is_not_created_for_blocked_users(self):
        with (
            patch('app.models.is_blocked_either_way', return_value=True),
            patch('app.models.execute') as execute,
        ):
            result = models.create_notification(8, 'view', from_user_id=4)

        self.assertIsNone(result)
        execute.assert_not_called()

    def test_notification_is_not_created_after_connected_unlike(self):
        with (
            patch('app.models.is_blocked_either_way', return_value=False),
            patch('app.models.notifications_are_suppressed', return_value=True),
            patch('app.models.execute') as execute,
        ):
            result = models.create_notification(4, 'view', from_user_id=8)

        self.assertIsNone(result)
        execute.assert_not_called()

    def test_view_serializer_keeps_viewer_and_timestamp(self):
        view = {
            'view_id': 22,
            'viewed_at': datetime(2026, 7, 28, 16, 30),
        }
        with patch('app.models.user_to_dict', return_value={'id': 4}):
            result = models.view_to_dict(view)

        self.assertEqual(result['id'], 22)
        self.assertEqual(result['viewer'], {'id': 4})
        self.assertEqual(result['viewedAt'], '2026-07-28T16:30:00Z')


if __name__ == '__main__':
    unittest.main()
