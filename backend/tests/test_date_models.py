import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app import models


class DateModelTests(unittest.TestCase):
    def test_create_date_event_uses_parameterized_insert(self):
        scheduled = datetime(2026, 8, 10, 18, 0, tzinfo=timezone.utc)
        with patch('app.models.execute', return_value={'id': 1}) as execute:
            result = models.create_date_event(
                4,
                8,
                scheduled,
                'Coffee shop',
                'Near the station',
            )

        self.assertEqual(result, {'id': 1})
        sql, params = execute.call_args.args[0:2]
        self.assertIn('INSERT INTO date_events', sql)
        self.assertIn('VALUES (%s, %s, %s, %s, %s)', sql)
        self.assertEqual(params, (4, 8, scheduled, 'Coffee shop', 'Near the station'))

    def test_date_history_excludes_blocked_pairs(self):
        with patch('app.models.query_all', return_value=[]) as query_all:
            models.get_date_events_for_user(4)

        sql = query_all.call_args.args[0]
        self.assertIn('NOT EXISTS', sql)
        self.assertIn('FROM user_blocks blocked', sql)
        self.assertEqual(query_all.call_args.args[1], (4, 4))

    def test_response_only_updates_pending_future_event(self):
        with patch('app.models.execute', return_value={'id': 1}) as execute:
            models.respond_to_date_event(12, 8, 'accepted')

        sql = execute.call_args.args[0]
        self.assertIn("status = 'pending'", sql)
        self.assertIn('scheduled_for > now()', sql)
        self.assertIn('recipient_id = %s', sql)

    def test_cancel_requires_participant_and_active_status(self):
        with patch('app.models.execute', return_value={'id': 1}) as execute:
            models.cancel_date_event(12, 4)

        sql = execute.call_args.args[0]
        self.assertIn('(proposer_id = %s OR recipient_id = %s)', sql)
        self.assertIn("status IN ('pending', 'accepted')", sql)


if __name__ == '__main__':
    unittest.main()
