import os
import re
import unicodedata
from datetime import date
from functools import lru_cache

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
EMAIL_MAX_LENGTH = 100
NAME_MAX_LENGTH = 50
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72
BIOGRAPHY_MAX_LENGTH = 500
LOCATION_MAX_LENGTH = 100
MIN_BIRTH_DATE = date(1900, 1, 1)
GENDER_VALUES = ('male', 'female', 'non-binary')

_USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_]+$')
_EMAIL_PATTERN = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
_NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$", re.UNICODE)
_SPECIAL_PATTERN = re.compile(r'[!@#$%^&*(),.?":{}|<>]')


def validate_username(value):
    if not isinstance(value, str):
        return None, 'Username must be a string'

    username = value.strip()
    if len(username) < USERNAME_MIN_LENGTH:
        return None, f'Username must be at least {USERNAME_MIN_LENGTH} characters long'
    if len(username) > USERNAME_MAX_LENGTH:
        return None, f'Username must be at most {USERNAME_MAX_LENGTH} characters long'
    if not _USERNAME_PATTERN.fullmatch(username):
        return None, 'Username may contain only letters, numbers, and underscores'

    return username, None


def normalize_email(value):
    if not isinstance(value, str):
        return None, 'Email must be a string'

    email = value.strip().lower()
    if not email:
        return None, 'Email is required'
    if len(email) > EMAIL_MAX_LENGTH:
        return None, f'Email must be at most {EMAIL_MAX_LENGTH} characters long'
    if not _EMAIL_PATTERN.fullmatch(email):
        return None, 'Invalid email address'

    return email, None


def validate_email(value):
    email, error = normalize_email(value)
    return email is not None and error is None


def validate_name(value, field_name):
    if not isinstance(value, str):
        return None, f'{field_name} must be a string'

    name = ' '.join(value.strip().split())
    if not name:
        return None, f'{field_name} is required'
    if len(name) > NAME_MAX_LENGTH:
        return None, f'{field_name} must be at most {NAME_MAX_LENGTH} characters long'
    if not _NAME_PATTERN.fullmatch(name):
        return None, f'{field_name} contains invalid characters'

    return name, None


def validate_birth_date(value, required=False):
    if value is None or value == '':
        if required:
            return None, 'Birth date is required'
        return None, None
    if not isinstance(value, str):
        return None, 'Birth date must be a string in YYYY-MM-DD format'

    try:
        birth_date = date.fromisoformat(value)
    except ValueError:
        return None, 'Birth date must use the YYYY-MM-DD format'

    if birth_date < MIN_BIRTH_DATE:
        return None, 'Birth date is outside the supported range'
    if birth_date > date.today():
        return None, 'Birth date cannot be in the future'

    return birth_date, None


def validate_gender(value, required=False):
    if value is None or value == '':
        if required:
            return None, 'Gender is required'
        return None, None
    if not isinstance(value, str):
        return None, 'Gender must be a string'
    if value not in GENDER_VALUES:
        return None, 'Gender must be male, female, or non-binary'
    return value, None


def validate_sexual_preferences(value):
    if not isinstance(value, list):
        return None, 'Sexual preferences must be a list'

    preferences = []
    for preference in value:
        if not isinstance(preference, str):
            return None, 'Every sexual preference must be a string'
        if preference not in GENDER_VALUES:
            return None, 'Sexual preferences contain an unsupported gender'
        if preference not in preferences:
            preferences.append(preference)

    if not preferences:
        return None, 'Select at least one sexual preference'

    return preferences, None


def validate_biography(value, required=False):
    if value is None:
        if required:
            return None, 'Biography is required'
        return None, None
    if not isinstance(value, str):
        return None, 'Biography must be a string'

    biography = value.strip()
    if required and not biography:
        return None, 'Biography is required'
    if len(biography) > BIOGRAPHY_MAX_LENGTH:
        return None, f'Biography must be at most {BIOGRAPHY_MAX_LENGTH} characters long'

    return biography or None, None


def validate_location_name(value, required=False):
    if value is None:
        if required:
            return None, 'locationName is required when gpsConsent is false'
        return None, None
    if not isinstance(value, str):
        return None, 'locationName must be a string'

    location_name = ' '.join(value.strip().split())
    if not location_name:
        if required:
            return None, 'locationName is required when gpsConsent is false'
        return None, None
    if len(location_name) > LOCATION_MAX_LENGTH:
        return None, f'locationName must be at most {LOCATION_MAX_LENGTH} characters long'

    return location_name, None


def validate_coordinate(value, field_name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, f'{field_name} must be a number'

    coordinate = float(value)
    if not minimum <= coordinate <= maximum:
        return None, f'{field_name} must be between {minimum} and {maximum}'

    return coordinate, None


def validate_password(password, account_values=None):
    if not isinstance(password, str):
        return False, 'Password must be a string'
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f'Password must be at least {PASSWORD_MIN_LENGTH} characters long'
    if len(password.encode('utf-8')) > PASSWORD_MAX_BYTES:
        return False, f'Password must be at most {PASSWORD_MAX_BYTES} bytes long'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one number'
    if not _SPECIAL_PATTERN.search(password):
        return False, 'Password must contain at least one special character'

    normalized_password = _normalize_word(password)
    if normalized_password in _common_passwords():
        return False, 'Password is too common'

    for value in account_values or []:
        if not isinstance(value, str):
            continue

        account_value = value.split('@', 1)[0]
        normalized_value = _normalize_word(account_value)
        if len(normalized_value) < 3:
            continue

        if normalized_password == normalized_value:
            return False, 'Password must not be based on your account details'

        common_affixes = ('password', 'matcha', 'welcome', 'love', 'secure')
        for affix in common_affixes:
            if normalized_password in {
                f'{normalized_value}{affix}',
                f'{affix}{normalized_value}',
            }:
                return False, 'Password must not be based on your account details'

    return True, 'Password is valid'


def validate_registration_data(data):
    if not isinstance(data, dict):
        return None, 'Request body must be a JSON object'

    username, error = validate_username(data.get('username'))
    if error:
        return None, error

    email, error = normalize_email(data.get('email'))
    if error:
        return None, error

    first_name, error = validate_name(data.get('firstName'), 'First name')
    if error:
        return None, error

    last_name, error = validate_name(data.get('lastName'), 'Last name')
    if error:
        return None, error

    password = data.get('password')
    is_valid, error = validate_password(
        password,
        account_values=[username, email, first_name, last_name],
    )
    if not is_valid:
        return None, error

    return {
        'username': username,
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'password': password,
    }, None


def _normalize_word(value):
    normalized = unicodedata.normalize('NFKD', value).casefold()
    return ''.join(character for character in normalized if character.isalpha())


@lru_cache(maxsize=1)
def _common_passwords():
    path = os.path.join(os.path.dirname(__file__), 'common_passwords.txt')
    with open(path, 'r', encoding='utf-8') as password_file:
        return {
            _normalize_word(line.strip())
            for line in password_file
            if line.strip() and not line.startswith('#')
        }
