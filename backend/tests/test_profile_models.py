import unittest
from datetime import date, datetime
from unittest.mock import patch

from app import models


class ProfileModelTests(unittest.TestCase):
    def setUp(self):
        self.user = {
            'id': 7,
            'username': 'profile_user',
            'email': 'profile@example.com',
            'first_name': 'Profile',
            'last_name': 'User',
            'birth_date': date(date.today().year - 25, 1, 1),
            'gender': 'non-binary',
            'sexual_preferences': ['male', 'female'],
            'biography': 'A complete biography.',
            'fame_rating': 21.0,
            'latitude': 0.0,
            'longitude': 0.0,
            'location_name': 'Greenwich',
            'gps_consent': True,
            'is_verified': True,
            'is_online': False,
            'last_activity': datetime(2026, 7, 28, 12, 0, 0),
        }
        self.tags = [{'id': 1, 'name': 'music'}]
        self.photos = [{
            'id': 1,
            'user_id': 7,
            'filename': 'photo.jpg',
            'is_primary': True,
            'position': 0,
        }]

    def test_zero_coordinates_count_as_a_complete_location(self):
        self.assertTrue(models.is_profile_complete(self.user, self.tags, self.photos))

    def test_missing_profile_fields_requires_tags_primary_photo_and_location(self):
        incomplete = dict(self.user)
        incomplete['biography'] = '   '
        photos = [{**self.photos[0], 'is_primary': False}]

        missing = models.missing_profile_fields(incomplete, [], photos)

        self.assertIn('biography', missing)
        self.assertIn('tags', missing)
        self.assertIn('profilePicture', missing)

    def test_photo_query_orders_primary_photo_first(self):
        with patch('app.models.query_all', return_value=[]) as query_all:
            models.get_photos_for_user(7)

        self.assertIn('ORDER BY is_primary DESC, position, id', query_all.call_args.args[0])

    def test_profile_completion_points_have_one_authoritative_total(self):
        self.assertEqual(models.profile_completion_points(self.user, self.tags, 1), 10)

    def test_public_serializer_hides_birth_date_and_exact_coordinates(self):
        with (
            patch('app.models.get_tags_for_user', return_value=self.tags),
            patch('app.models.get_photos_for_user', return_value=self.photos),
            patch('app.models.get_primary_photo', return_value=self.photos[0]),
        ):
            result = models.user_to_dict(self.user)

        self.assertNotIn('birthDate', result)
        self.assertEqual(result['location'], {'name': 'Greenwich'})
        self.assertNotIn('latitude', result['location'])
        self.assertEqual(result['age'], models.calculate_age(self.user['birth_date']))

    def test_private_serializer_includes_editable_birth_date_and_coordinates(self):
        with (
            patch('app.models.get_tags_for_user', return_value=self.tags),
            patch('app.models.get_photos_for_user', return_value=self.photos),
            patch('app.models.get_primary_photo', return_value=self.photos[0]),
        ):
            result = models.user_to_dict(self.user, include_private=True)

        self.assertEqual(result['birthDate'], self.user['birth_date'].isoformat())
        self.assertEqual(result['location']['latitude'], 0.0)
        self.assertEqual(result['location']['longitude'], 0.0)

    def test_fame_rating_is_limited_to_100(self):
        def query_one(sql, params):
            if 'user_likes' in sql:
                return {'c': 100}
            if 'user_views' in sql:
                return {'c': 1000}
            raise AssertionError(sql)

        with (
            patch('app.models.query_one', side_effect=query_one),
            patch('app.models.get_user_by_id', return_value=self.user),
            patch('app.models.get_tags_for_user', return_value=self.tags),
            patch('app.models.count_photos', return_value=1),
        ):
            rating = models.calculate_fame_rating(7)

        self.assertEqual(rating, 100)

    def test_fame_formula_uses_likes_views_and_completion_points(self):
        def query_one(sql, params):
            if 'user_likes' in sql:
                return {'c': 3}
            if 'user_views' in sql:
                return {'c': 4}
            raise AssertionError(sql)

        with (
            patch('app.models.query_one', side_effect=query_one),
            patch('app.models.get_user_by_id', return_value=self.user),
            patch('app.models.get_tags_for_user', return_value=self.tags),
            patch('app.models.count_photos', return_value=1),
        ):
            rating = models.calculate_fame_rating(7)

        self.assertEqual(rating, 21.0)


if __name__ == '__main__':
    unittest.main()
