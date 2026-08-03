import os
import tempfile
import unittest
from datetime import date, timedelta
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.config import Config
from app.utils import calculate_distance, delete_saved_image, save_image
from app.validation import (
    GENDER_VALUES,
    validate_biography,
    validate_birth_date,
    validate_coordinate,
    validate_gender,
    validate_sexual_preferences,
)


class ProfileValidationTests(unittest.TestCase):
    @staticmethod
    def birth_date_for_age(age, day_offset=0):
        today = date.today()
        target_year = today.year - age

        try:
            result = today.replace(year=target_year)
        except ValueError:
            result = today.replace(year=target_year, month=2, day=28)

        return result + timedelta(days=day_offset)

    def test_user_must_be_at_least_18(self):
        value, error = validate_birth_date(
            self.birth_date_for_age(18, day_offset=1).isoformat()
        )

        self.assertIsNone(value)
        self.assertEqual(error, 'Age must be between 18 and 80 years old')

    def test_exactly_18_years_old_is_valid(self):
        value, error = validate_birth_date(
            self.birth_date_for_age(18).isoformat()
        )

        self.assertIsNone(error)
        self.assertIsNotNone(value)

    def test_exactly_80_years_old_is_valid(self):
        value, error = validate_birth_date(
            self.birth_date_for_age(80).isoformat()
        )

        self.assertIsNone(error)
        self.assertIsNotNone(value)

    def test_user_cannot_be_older_than_80(self):
        value, error = validate_birth_date(
            self.birth_date_for_age(81).isoformat()
        )

        self.assertIsNone(value)
        self.assertEqual(error, 'Age must be between 18 and 80 years old')

    def test_future_birth_date_is_rejected(self):
        value, error = validate_birth_date((date.today() + timedelta(days=1)).isoformat())

        self.assertIsNone(value)
        self.assertEqual(error, 'Birth date cannot be in the future')

    def test_gender_uses_the_approved_values(self):
        value, error = validate_gender('other')

        self.assertIsNone(value)
        self.assertEqual(error, 'Gender must be male, female, or non-binary')

    def test_empty_preferences_are_rejected(self):
        preferences, error = validate_sexual_preferences([])

        self.assertIsNone(preferences)
        self.assertEqual(error, 'Select at least one sexual preference')

    def test_required_profile_values_cannot_be_blank(self):
        birth_date, birth_error = validate_birth_date('', required=True)
        gender, gender_error = validate_gender('', required=True)
        biography, biography_error = validate_biography('   ', required=True)

        self.assertIsNone(birth_date)
        self.assertEqual(birth_error, 'Birth date is required')
        self.assertIsNone(gender)
        self.assertEqual(gender_error, 'Gender is required')
        self.assertIsNone(biography)
        self.assertEqual(biography_error, 'Biography is required')

    def test_invalid_preference_is_rejected(self):
        preferences, error = validate_sexual_preferences(['male', 'unsupported'])

        self.assertIsNone(preferences)
        self.assertEqual(error, 'Sexual preferences contain an unsupported gender')

    def test_zero_coordinate_is_valid(self):
        coordinate, error = validate_coordinate(0, 'longitude', -180, 180)

        self.assertIsNone(error)
        self.assertEqual(coordinate, 0.0)
        self.assertNotEqual(calculate_distance(0, 0, 1, 1), float('inf'))

    def test_biography_length_is_controlled(self):
        biography, error = validate_biography('a' * 501)

        self.assertIsNone(biography)
        self.assertEqual(error, 'Biography must be at most 500 characters long')

    def test_image_validation_uses_content_and_random_filename(self):
        original_upload_folder = Config.UPLOAD_FOLDER
        try:
            with tempfile.TemporaryDirectory() as upload_folder:
                Config.UPLOAD_FOLDER = upload_folder
                image_bytes = BytesIO()
                Image.new('RGB', (20, 20), 'white').save(image_bytes, format='PNG')
                image_bytes.seek(0)

                upload = SimpleNamespace(filename='pretend.txt', stream=image_bytes)
                filename = save_image(upload)

                self.assertIsNotNone(filename)
                self.assertTrue(filename.endswith('.png'))
                self.assertNotIn('pretend', filename)
                self.assertTrue(os.path.exists(os.path.join(upload_folder, filename)))
        finally:
            Config.UPLOAD_FOLDER = original_upload_folder

    def test_invalid_image_bytes_are_rejected(self):
        original_upload_folder = Config.UPLOAD_FOLDER
        try:
            with tempfile.TemporaryDirectory() as upload_folder:
                Config.UPLOAD_FOLDER = upload_folder
                upload = SimpleNamespace(filename='photo.png', stream=BytesIO(b'not an image'))

                self.assertIsNone(save_image(upload))
                self.assertEqual(os.listdir(upload_folder), [])
        finally:
            Config.UPLOAD_FOLDER = original_upload_folder

    def test_upload_deletion_rejects_path_traversal(self):
        self.assertFalse(delete_saved_image('../secret.txt'))


if __name__ == '__main__':
    unittest.main()
