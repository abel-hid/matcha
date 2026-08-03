import inspect
import unittest
from datetime import date

import seed


class SeedDataTests(unittest.TestCase):
    def test_usernames_are_zero_padded(self):
        self.assertEqual(seed.username_for(1), 'seed_001')
        self.assertEqual(seed.username_for(500), 'seed_500')

    def test_profiles_are_complete_and_cover_required_ranges(self):
        profiles = seed.build_seed_profiles(500)

        self.assertEqual(len(profiles), 500)
        self.assertEqual(profiles[0]['username'], 'seed_001')
        self.assertEqual(profiles[-1]['username'], 'seed_500')
        self.assertEqual(
            {profile['gender'] for profile in profiles},
            set(seed.GENDERS),
        )

        for profile in profiles:
            age = (
                date.today().year
                - profile['birth_date'].year
                - (
                    (date.today().month, date.today().day)
                    < (
                        profile['birth_date'].month,
                        profile['birth_date'].day,
                    )
                )
            )

            self.assertGreaterEqual(age, 18)
            self.assertLessEqual(age, 80)
            self.assertTrue(profile['sexual_preferences'])
            self.assertTrue(profile['biography'])
            self.assertTrue(profile['tag_names'])
            self.assertGreaterEqual(profile['photo_count'], 1)
            self.assertLessEqual(profile['photo_count'], 5)
            self.assertIsNotNone(profile['latitude'])
            self.assertIsNotNone(profile['longitude'])

    def test_relationships_have_no_self_likes_and_include_matches(self):
        user_ids = list(range(1, 501))
        pairs = set(seed.build_like_pairs(user_ids))

        self.assertTrue(all(liker_id != liked_id for liker_id, liked_id in pairs))
        self.assertIn((1, 2), pairs)
        self.assertIn((2, 1), pairs)
        self.assertIn((11, 12), pairs)
        self.assertIn((12, 11), pairs)

    def test_view_rows_have_valid_distinct_users(self):
        user_ids = list(range(1, 501))
        usernames = {
            user_id: seed.username_for(user_id)
            for user_id in user_ids
        }
        rows = seed.build_view_rows(user_ids, usernames)

        self.assertTrue(rows)
        self.assertTrue(
            all(viewer_id != viewed_id for viewer_id, viewed_id, _, _ in rows)
        )
        self.assertEqual(
            len({(viewer_id, visit_id) for viewer_id, _, visit_id, _ in rows}),
            len(rows),
        )

    def test_seed_database_has_one_fixed_500_profile_mode(self):
        self.assertEqual(seed.SEED_PROFILE_COUNT, 500)
        self.assertEqual(
            list(inspect.signature(seed.seed_database).parameters),
            [],
        )

    def test_seed_cli_rejects_every_argument(self):
        original_argv = seed.sys.argv
        seed.sys.argv = ['seed.py', '--count', '600']
        try:
            with self.assertRaisesRegex(
                SystemExit,
                'does not accept arguments',
            ):
                seed.main()
        finally:
            seed.sys.argv = original_argv


if __name__ == '__main__':
    unittest.main()
