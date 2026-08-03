"""
Generate the deterministic Matcha evaluation dataset.

The root Docker startup executes this command automatically:

    ./start.sh

The script has no command-line options and always creates exactly 500 profiles.

The command preserves non-seed accounts, replaces accounts whose usernames
start with ``seed_``, and creates at least 500 verified, complete profiles.
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
SEED_PASSWORD = 'lhfTYh6452fdHH9'
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
    ('Agdal, Rabat', 33.9904, -6.8480),
    ('Hay Riad, Rabat', 33.9564, -6.8671),
    ('Hassan, Rabat', 34.0209, -6.8277),
    ('Medina, Rabat', 34.0259, -6.8361),
    ('Maarif, Casablanca', 33.5858, -7.6327),
    ('Ain Diab, Casablanca', 33.5922, -7.6767),
    ('Gauthier, Casablanca', 33.5911, -7.6273),
    ('Sidi Maarouf, Casablanca', 33.5299, -7.6461),
    ('Gueliz, Marrakech', 31.6341, -8.0117),
    ('Medina, Marrakech', 31.6295, -7.9811),
    ('Hivernage, Marrakech', 31.6218, -8.0097),
    ('Charaf, Agadir', 30.4317, -9.5797),
    ('Talborjt, Agadir', 30.4220, -9.5912),
    ('Malabata, Tangier', 35.7896, -5.7659),
    ('Bni Makada, Tangier', 35.7511, -5.8188),
    ('City Center, Tangier', 35.7795, -5.8128),
    ('Hamria, Meknes', 33.8951, -5.5473),
    ('Ville Nouvelle, Fes', 34.0349, -5.0026),
    ('Medina, Tetouan', 35.5711, -5.3684),
    ('City Center, Oujda', 34.6814, -1.9086),
)

PHOTO_PALETTE = (
    ((255, 77, 126), (30, 23, 40)),
    ((242, 200, 121), (38, 30, 48)),
    ((90, 188, 216), (22, 32, 46)),
    ((126, 217, 155), (24, 38, 35)),
    ((177, 131, 255), (31, 24, 45)),
    ((255, 151, 91), (44, 29, 25)),
)



def username_for(index):
    return f'seed_{index:03d}'


def birth_date_for_age(age, rng, today=None):
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
        location_name, base_latitude, base_longitude = LOCATIONS[
            (index - 1) % len(LOCATIONS)
        ]
        latitude = round(base_latitude + rng.uniform(-0.018, 0.018), 6)
        longitude = round(base_longitude + rng.uniform(-0.018, 0.018), 6)
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
    width = 360
    height = 360
    foreground, background = PHOTO_PALETTE[
        (profile['index'] + photo_number - 2) % len(PHOTO_PALETTE)
    ]
    image = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    stripe_width = 45 + ((profile['index'] * 3 + photo_number * 11) % 70)
    draw.rectangle(
        (0, 0, stripe_width, height),
        fill=foreground,
    )
    draw.ellipse(
        (
            120 - photo_number * 5,
            60 + photo_number * 4,
            330 - photo_number * 3,
            270 + photo_number * 7,
        ),
        fill=foreground,
    )
    draw.rectangle(
        (35, 285, 325, 335),
        fill=background,
    )

    initials = (
        f"{profile['first_name'][:1]}"
        f"{profile['last_name'][:1]}"
    ).upper()
    label = f"{initials}  {profile['username']}  #{photo_number}"
    draw.text(
        (55, 304),
        label,
        fill=(245, 239, 233),
        font=font,
    )

    image.save(destination, format='PNG', optimize=True)


def prepare_seed_photos(profiles, directory):
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
    if not UPLOAD_FOLDER.exists():
        return

    for path in UPLOAD_FOLDER.glob(f'{SEED_FILE_PREFIX}*.png'):
        if path.name not in expected_filenames:
            path.unlink()


def install_seed_photos(source_directory, expected_filenames):
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
