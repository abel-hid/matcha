"""
Generate the deterministic Matcha evaluation dataset.

The root Docker startup executes this command automatically:

    ./start.sh

The script has no command-line options and always creates exactly 500 profiles.

The command preserves non-seed accounts, replaces accounts whose usernames
start with ``seed_``, and creates exactly 500 verified, complete profiles.
"""
import random
import sys
import shutil
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import bcrypt
import psycopg2
from PIL import Image, ImageDraw, ImageFont
from psycopg2.extras import execute_values

from app.config import Config

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = Path(Config.UPLOAD_FOLDER)

SEED_PROFILE_COUNT = 500
SEED_RANDOM_VALUE = 20260801
SEED_PASSWORD = 'lhfTYh6452fdHH9@'
SEED_FILE_PREFIX = 'seed_profile_'

GENDERS = ('male', 'female', 'non-binary')
PREFERENCE_OPTIONS = (
    ('male',),
    ('female',),
    ('non-binary',),
    ('male', 'female'),
    ('female', 'non-binary'),
    ('male', 'non-binary'),
    ('male', 'female', 'non-binary'),
)

TAG_NAMES = (
    'music',
    'movies',
    'gaming',
    'books',
    'travel',
    'fitness',
    'cooking',
    'photography',
    'art',
    'technology',
    'nature',
    'hiking',
    'pets',
    'sports',
    'dancing',
    'fashion',
    'coffee',
    'vegan',
    'anime',
    'volunteering',
)

FIRST_NAMES = (
    'Adam', 'Aicha', 'Amine', 'Aya', 'Bilal', 'Chaimae', 'Dounia', 'Elias',
    'Fatima', 'Hamza', 'Hiba', 'Ilyas', 'Imane', 'Khadija', 'Lina', 'Mariam',
    'Mehdi', 'Nadia', 'Nora', 'Omar', 'Rania', 'Salma', 'Samir', 'Sara',
    'Sofia', 'Soufiane', 'Yasmine', 'Yassine', 'Youssef', 'Zineb',
)

LAST_NAMES = (
    'Alaoui', 'Amrani', 'Bennani', 'Berrada', 'Chafai', 'El Idrissi',
    'El Mansouri', 'Fassi', 'Haddad', 'Karimi', 'Lahlou', 'Mernissi',
    'Naciri', 'Ouazzani', 'Rahmani', 'Saidi', 'Tazi', 'Zahraoui',
)

BIOGRAPHY_TEMPLATES = (
    'I enjoy {tag_a}, {tag_b}, and discovering new places around {location}.',
    'Usually planning something around {tag_a}. I also appreciate {tag_b} and relaxed conversations.',
    'Based near {location}. My free time is mostly about {tag_a}, {tag_b}, and meeting thoughtful people.',
    'Curious, friendly, and always ready to learn something new. Interested in {tag_a} and {tag_b}.',
    'A calm person who values honesty, good humor, {tag_a}, and weekends involving {tag_b}.',
    'Looking to meet people with positive energy. Current interests include {tag_a}, {tag_b}, and local adventures.',
)

LOCATIONS = (
    ('Agdal, Rabat', 33.9820, 34.0000, -6.8600, -6.8400),
    ('Hay Riad, Rabat', 33.9480, 33.9650, -6.8800, -6.8500),
    ('Hassan, Rabat', 34.0150, 34.0280, -6.8400, -6.8200),
    ('Medina, Rabat', 34.0200, 34.0300, -6.8450, -6.8300),
    ('Maarif, Casablanca', 33.5780, 33.5920, -7.6450, -7.6200),
    ('Ain Diab, Casablanca', 33.5840, 33.5950, -7.6600, -7.6350),
    ('Gauthier, Casablanca', 33.5850, 33.5950, -7.6350, -7.6200),
    ('Sidi Maarouf, Casablanca', 33.5200, 33.5400, -7.6600, -7.6300),
    ('Gueliz, Marrakech', 31.6250, 31.6400, -8.0200, -8.0000),
    ('City Center, Khouribga', 32.8750, 32.8950, -6.9250, -6.8950),
    ('Medina, Marrakech', 31.6200, 31.6350, -7.9950, -7.9750),
    ('Hivernage, Marrakech', 31.6150, 31.6280, -8.0200, -8.0000),
    ('Charaf, Agadir', 30.4250, 30.4380, -9.5900, -9.5700),
    ('Talborjt, Agadir', 30.4170, 30.4280, -9.6000, -9.5800),
    ('Malabata, Tangier', 35.7800, 35.7920, -5.7800, -5.7500),
    ('Bni Makada, Tangier', 35.7420, 35.7600, -5.8300, -5.8000),
    ('City Center, Tangier', 35.7700, 35.7850, -5.8250, -5.8000),
    ('Hamria, Meknes', 33.8880, 33.9020, -5.5550, -5.5350),
    ('Ville Nouvelle, Fes', 34.0280, 34.0420, -5.0150, -4.9950),
    ('Medina, Tetouan', 35.5650, 35.5780, -5.3800, -5.3550),
    ('City Center, Oujda', 34.6750, 34.6880, -1.9200, -1.8950),
    ('Eixample, Barcelona', 41.3820, 41.3980, 2.1600, 2.1800),
    ('Centro, Madrid', 40.4120, 40.4250, -3.7100, -3.6950),
    ('11th Arrondissement, Paris', 48.8500, 48.8650, 2.3700, 2.3900),
    ('Mitte, Berlin', 52.5150, 52.5300, 13.3900, 13.4150),
    ('Navigli, Milan', 45.4450, 45.4600, 9.1650, 9.1900),
    ('Downtown, Cairo', 30.0350, 30.0550, 31.2250, 31.2450),
    ('Plateau, Dakar', 14.6600, 14.6750, -17.4450, -17.4250),
    ('Downtown, Montreal', 45.4950, 45.5100, -73.5800, -73.5550),
    ('Palermo, Buenos Aires', -34.5950, -34.5750, -58.4350, -58.4050),
    ('Shibuya, Tokyo', 35.6520, 35.6660, 139.6950, 139.7150),
    ('Gangnam, Seoul', 37.4900, 37.5050, 127.0200, 127.0450),
    ('CBD, Sydney', -33.8750, -33.8600, 151.2000, 151.2200),
)

PHOTO_COLORS = (
    (255, 77, 126),
    (242, 200, 121),
    (90, 188, 216),
    (126, 217, 155),
    (177, 131, 255),
    (255, 151, 91),
    (75, 123, 236),
    (236, 90, 117),
)

def username_for(index):
    """Return the stable seed username for one one-based index."""
    return f'seed_{index:03d}'


def birth_date_for_age(age, rng, today=None):
    """Build a deterministic birth date for the requested age."""
    today = today or date.today()
    month = rng.randint(1, 12)

    if month == 2:
        max_day = 28
    elif month in {4, 6, 9, 11}:
        max_day = 30
    else:
        max_day = 31

    day = rng.randint(1, max_day)
    birthday_has_passed = (month, day) <= (today.month, today.day)
    year = today.year - age if birthday_has_passed else today.year - age - 1
    return date(year, month, day)


def build_seed_profiles(count, random_seed=SEED_RANDOM_VALUE):
    """Build deterministic complete profile values for all 500 seed users."""
    rng = random.Random(random_seed)
    today = date.today()
    profiles = []

    for index in range(1, count + 1):
        username = username_for(index)
        first_name = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
        last_name = LAST_NAMES[((index - 1) * 7) % len(LAST_NAMES)]
        age = 18 + ((index * 13) % 63)
        birth_date = birth_date_for_age(age, rng, today=today)
        gender = GENDERS[(index - 1) % len(GENDERS)]
        preferences = list(PREFERENCE_OPTIONS[(index - 1) % len(PREFERENCE_OPTIONS)])
        location_name, min_latitude, max_latitude, min_longitude, max_longitude = LOCATIONS[
            (index - 1) % len(LOCATIONS)
        ]
        latitude = round(rng.uniform(min_latitude, max_latitude), 6)
        longitude = round(rng.uniform(min_longitude, max_longitude), 6)
        tag_count = 2 + (index % 6)
        tag_names = rng.sample(list(TAG_NAMES), tag_count)
        biography = BIOGRAPHY_TEMPLATES[(index - 1) % len(BIOGRAPHY_TEMPLATES)].format(
            tag_a=tag_names[0],
            tag_b=tag_names[1],
            location=location_name,
        )
        created_days_ago = rng.randint(30, 730)
        created_at = datetime.utcnow() - timedelta(days=created_days_ago)
        last_activity = datetime.utcnow() - timedelta(
            days=rng.randint(0, 45),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )

        profiles.append({
            'index': index,
            'username': username,
            'email': f'{username}@example.com',
            'first_name': first_name,
            'last_name': last_name,
            'birth_date': birth_date,
            'gender': gender,
            'sexual_preferences': preferences,
            'biography': biography,
            'latitude': latitude,
            'longitude': longitude,
            'location_name': location_name,
            'gps_consent': index % 3 != 0,
            'last_activity': last_activity,
            'created_at': created_at,
            'updated_at': max(created_at, last_activity),
            'tag_names': tag_names,
            'photo_count': 1 + ((index - 1) % 5),
        })

    return profiles


def build_like_pairs(user_ids):
    """Build deterministic directional likes and mutual matches."""
    count = len(user_ids)
    likes = set()

    for source_index, source_id in enumerate(user_ids):
        outgoing_count = source_index % 4

        for step in range(outgoing_count):
            offset = 17 + (step * 29)
            target_id = user_ids[(source_index + offset) % count]

            if source_id != target_id:
                likes.add((source_id, target_id))

    for start in range(0, count - 1, 10):
        first_id = user_ids[start]
        second_id = user_ids[start + 1]
        likes.add((first_id, second_id))
        likes.add((second_id, first_id))

    return sorted(likes)


def build_view_rows(user_ids, usernames, random_seed=SEED_RANDOM_VALUE):
    """Build deterministic profile visit history."""
    rng = random.Random(random_seed + 99)
    count = len(user_ids)
    rows = []

    for viewer_index, viewer_id in enumerate(user_ids):
        view_count = viewer_index % 6

        for step in range(view_count):
            target_index = (viewer_index + 11 + (step * 37)) % count
            viewed_id = user_ids[target_index]

            if viewer_id == viewed_id:
                continue

            visit_key = (
                f'{usernames[viewer_id]}:'
                f'{usernames[viewed_id]}:{step}'
            )
            viewed_at = datetime.utcnow() - timedelta(
                days=rng.randint(0, 90),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )
            rows.append((
                viewer_id,
                viewed_id,
                str(uuid5(NAMESPACE_URL, visit_key)),
                viewed_at,
            ))

    return rows


def render_seed_photo(profile, photo_number, destination):
    """Create one plain solid-color square image for a seed profile."""
    rng = random.Random(SEED_RANDOM_VALUE + profile['index'] + photo_number)
    color = rng.choice(PHOTO_COLORS)
    Image.new('RGB', (360, 360), color).save(destination, format='PNG')


def prepare_seed_photos(profiles, directory):
    """Generate seed photos in a staging directory before database writes."""
    photo_rows = []
    filenames = set()

    for profile in profiles:
        for photo_number in range(1, profile['photo_count'] + 1):
            filename = (
                f'{SEED_FILE_PREFIX}'
                f"{profile['index']:03d}_{photo_number}.png"
            )
            destination = directory / filename
            render_seed_photo(profile, photo_number, destination)
            filenames.add(filename)
            photo_rows.append({
                'username': profile['username'],
                'filename': filename,
                'is_primary': photo_number == 1,
                'position': photo_number - 1,
            })

    return photo_rows, filenames


def remove_unused_seed_photos(expected_filenames):
    """Remove obsolete generated photos after reseeding."""
    if not UPLOAD_FOLDER.exists():
        return

    for path in UPLOAD_FOLDER.glob(f'{SEED_FILE_PREFIX}*.png'):
        if path.name not in expected_filenames:
            path.unlink()


def install_seed_photos(source_directory, expected_filenames):
    """Move staged seed photos into persistent upload storage."""
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    for filename in expected_filenames:
        source = source_directory / filename
        destination = UPLOAD_FOLDER / filename

        shutil.move(
            str(source),
            str(destination),
        )

    remove_unused_seed_photos(expected_filenames)


def load_tag_ids(cursor):
    """Load every fixed tag identifier and fail if schema setup is incomplete."""
    cursor.execute(
        'SELECT id, name FROM tags WHERE name = ANY(%s::TEXT[])',
        (list(TAG_NAMES),),
    )
    tag_ids = {name: tag_id for tag_id, name in cursor.fetchall()}
    missing = sorted(set(TAG_NAMES) - set(tag_ids))

    if missing:
        raise RuntimeError(
            f"Missing predefined tags: {', '.join(missing)}. Run python initdb.py first."
        )

    return tag_ids


def insert_seed_data(profiles, photo_rows):
    """Replace seed accounts and related rows in one database transaction."""
    Config.validate_database()
    password_hash = bcrypt.hashpw(
        SEED_PASSWORD.encode('utf-8'),
        bcrypt.gensalt(),
    ).decode('utf-8')

    conn = psycopg2.connect(Config.DATABASE_URL)
    try:
        with conn.cursor() as cursor:
            tag_ids = load_tag_ids(cursor)

            cursor.execute(
                "DELETE FROM users WHERE username LIKE 'seed\\_%' ESCAPE '\\'"
            )

            user_rows = [
                (
                    profile['username'],
                    profile['email'],
                    password_hash,
                    profile['first_name'],
                    profile['last_name'],
                    profile['birth_date'],
                    profile['gender'],
                    profile['sexual_preferences'],
                    profile['biography'],
                    profile['latitude'],
                    profile['longitude'],
                    profile['location_name'],
                    profile['created_at'],
                    profile['gps_consent'],
                    True,
                    False,
                    profile['last_activity'],
                    profile['created_at'],
                    profile['updated_at'],
                )
                for profile in profiles
            ]

            inserted = execute_values(
                cursor,
                """
                INSERT INTO users (
                    username,
                    email,
                    password_hash,
                    first_name,
                    last_name,
                    birth_date,
                    gender,
                    sexual_preferences,
                    biography,
                    latitude,
                    longitude,
                    location_name,
                    location_updated_at,
                    gps_consent,
                    is_verified,
                    is_online,
                    last_activity,
                    created_at,
                    updated_at
                )
                VALUES %s
                RETURNING id, username
                """,
                user_rows,
                fetch=True,
                page_size=100,
            )
            user_ids_by_username = {
                username: user_id for user_id, username in inserted
            }

            tag_rows = []
            for profile in profiles:
                user_id = user_ids_by_username[profile['username']]
                tag_rows.extend(
                    (user_id, tag_ids[tag_name])
                    for tag_name in profile['tag_names']
                )

            execute_values(
                cursor,
                'INSERT INTO user_tags (user_id, tag_id) VALUES %s',
                tag_rows,
                page_size=500,
            )

            database_photo_rows = [
                (
                    user_ids_by_username[row['username']],
                    row['filename'],
                    row['is_primary'],
                    row['position'],
                )
                for row in photo_rows
            ]
            execute_values(
                cursor,
                """
                INSERT INTO photos (user_id, filename, is_primary, position)
                VALUES %s
                """,
                database_photo_rows,
                page_size=500,
            )

            ordered_user_ids = [
                user_ids_by_username[profile['username']]
                for profile in profiles
            ]
            usernames_by_id = {
                user_id: username
                for username, user_id in user_ids_by_username.items()
            }
            like_pairs = build_like_pairs(ordered_user_ids)
            like_rng = random.Random(SEED_RANDOM_VALUE + 45)
            like_rows = [
                (
                    liker_id,
                    liked_id,
                    datetime.utcnow() - timedelta(
                        days=like_rng.randint(0, 120),
                        hours=like_rng.randint(0, 23),
                    ),
                )
                for liker_id, liked_id in like_pairs
            ]

            execute_values(
                cursor,
                """
                INSERT INTO user_likes (liker_id, liked_id, created_at)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                like_rows,
                page_size=500,
            )

            view_rows = build_view_rows(
                ordered_user_ids,
                usernames_by_id,
            )
            execute_values(
                cursor,
                """
                INSERT INTO user_views (
                    viewer_id,
                    viewed_id,
                    visit_id,
                    viewed_at
                )
                VALUES %s
                ON CONFLICT (viewer_id, visit_id) DO NOTHING
                """,
                view_rows,
                page_size=500,
            )

            cursor.execute(
                """
                UPDATE users u
                SET fame_rating = ROUND((
                    10
                    + 3 * (
                        SELECT COUNT(*)
                        FROM user_likes l
                        WHERE l.liked_id = u.id
                    )
                    + 0.5 * (
                        SELECT COUNT(*)
                        FROM user_views v
                        WHERE v.viewed_id = u.id
                    )
                )::NUMERIC, 2)::DOUBLE PRECISION
                WHERE u.username LIKE 'seed\\_%' ESCAPE '\\'
                """
            )

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS profile_count,
                    COUNT(DISTINCT u.gender) AS gender_count,
                    MIN(u.fame_rating) AS minimum_fame,
                    MAX(u.fame_rating) AS maximum_fame
                FROM users u
                WHERE u.username LIKE 'seed\\_%' ESCAPE '\\'
                """
            )
            profile_count, gender_count, minimum_fame, maximum_fame = cursor.fetchone()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM users u
                WHERE u.username LIKE 'seed\\_%' ESCAPE '\\'
                  AND u.is_verified = true
                  AND u.birth_date IS NOT NULL
                  AND u.gender IS NOT NULL
                  AND cardinality(u.sexual_preferences) >= 1
                  AND length(btrim(u.biography)) > 0
                  AND u.latitude IS NOT NULL
                  AND u.longitude IS NOT NULL
                  AND length(btrim(u.location_name)) > 0
                  AND EXISTS (
                      SELECT 1 FROM user_tags ut WHERE ut.user_id = u.id
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM photos p
                      WHERE p.user_id = u.id AND p.is_primary = true
                  )
                """
            )
            complete_count = cursor.fetchone()[0]

            if profile_count != len(profiles):
                raise RuntimeError(
                    f'Expected {len(profiles)} seed profiles, found {profile_count}'
                )
            if complete_count != len(profiles):
                raise RuntimeError(
                    f'Expected {len(profiles)} complete profiles, found {complete_count}'
                )
            if gender_count != len(GENDERS):
                raise RuntimeError('Seed data does not contain all supported genders')

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    match_count = sum(
        1
        for liker_id, liked_id in like_pairs
        if liker_id < liked_id and (liked_id, liker_id) in set(like_pairs)
    )

    return {
        'profile_count': profile_count,
        'complete_count': complete_count,
        'photo_count': len(photo_rows),
        'like_count': len(like_pairs),
        'match_count': match_count,
        'view_count': len(view_rows),
        'minimum_fame': minimum_fame,
        'maximum_fame': maximum_fame,
    }


def seed_database():
    """Generate and install the exact 500-profile evaluation dataset."""
    profiles = build_seed_profiles(
        SEED_PROFILE_COUNT,
        random_seed=SEED_RANDOM_VALUE,
    )
    temporary_directory = Path(tempfile.mkdtemp(prefix='matcha-seed-'))

    try:
        photo_rows, filenames = prepare_seed_photos(
            profiles,
            temporary_directory,
        )
        result = insert_seed_data(profiles, photo_rows)
        install_seed_photos(temporary_directory, filenames)
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)

    return result


def main():
    """Run the deterministic seed command and print a concise result."""
    if len(sys.argv) != 1:
        raise SystemExit(
            'seed.py does not accept arguments; it always creates exactly 500 profiles'
        )

    result = seed_database()

    print('Matcha evaluation seed completed successfully.')
    print(
        f"Profiles: {result['profile_count']} verified and complete "
        f"({username_for(1)} through {username_for(result['profile_count'])})"
    )
    print(f'Password for every seed account: {SEED_PASSWORD}')
    print(f"Photos: {result['photo_count']}")
    print(f"Likes: {result['like_count']}")
    print(f"Mutual matches: {result['match_count']}")
    print(f"Profile visits: {result['view_count']}")
    print(
        f"Fame rating range: {result['minimum_fame']} "
        f"to {result['maximum_fame']}"
    )


if __name__ == '__main__':
    main()
