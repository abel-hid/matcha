from datetime import date, timezone
from uuid import uuid4
import re

import bcrypt
from psycopg2.extras import RealDictCursor
from flask_jwt_extended import create_access_token, create_refresh_token

from app.db import query_one, query_all, execute, get_conn
from app.validation import MAX_PROFILE_AGE, MIN_PROFILE_AGE

MAX_PHOTOS_PER_USER = 5
MAX_FAME_RATING = 100
PROFILE_LOCK_NAMESPACE = 4242


class InvalidTagIdsError(ValueError):
    pass


class PhotoLimitError(ValueError):
    pass


class LastPhotoError(ValueError):
    pass


class OAuthIdentityConflictError(ValueError):
    pass


# ---------------------------------------------------------------- passwords

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, password_hash):
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False

    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def get_tokens_for_user(user, session_id): # Return a new access and refresh token pair for a user and session.
    claims = {
        'sid': session_id,
        'ver': user['token_version'],
    }
    identity = str(user['id'])
    return (
        create_access_token(identity=identity, additional_claims=claims),
        create_refresh_token(identity=identity, additional_claims=claims),
    )


def to_iso_utc(dt): # Convert a datetime to an ISO 8601 string in UTC.
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace('+00:00', 'Z')


# --------------------------------------------------------------------- users

def get_user_by_id(user_id):
    return query_one("SELECT * FROM users WHERE id = %s", (user_id,))


def get_user_by_username(username):
    return query_one("SELECT * FROM users WHERE username = %s", (username,))


def get_user_by_email(email):
    return query_one("SELECT * FROM users WHERE email = %s", (email,))


def create_user(username, email, password, first_name, last_name):
    return execute(
        """
        INSERT INTO users (username, email, password_hash, first_name, last_name)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (username, email, hash_password(password), first_name, last_name),
        returning=True,
    )


_UPDATABLE_USER_FIELDS = {
    'first_name', 'last_name', 'email', 'is_verified', 'birth_date', 'gender',
    'sexual_preferences', 'biography', 'password_hash', 'token_version',
    'is_online', 'last_activity', 'gps_consent', 'latitude', 'longitude',
    'location_name', 'location_updated_at', 'fame_rating',
}


def update_user_fields(user_id, fields: dict):
    fields = {k: v for k, v in fields.items() if k in _UPDATABLE_USER_FIELDS}
    if not fields:
        return
    set_clause = ', '.join(f"{col} = %s" for col in fields)
    params = list(fields.values()) + [user_id]
    execute(f"UPDATE users SET {set_clause}, updated_at = now() WHERE id = %s", params)


def delete_user(user_id):
    execute("DELETE FROM users WHERE id = %s", (user_id,))


# ------------------------------------------------------------------- sessions

def create_session(user_id, expires_at):
    """Create one revocable server-side authentication session."""
    session_id = str(uuid4())
    execute(
        """
        INSERT INTO auth_sessions (id, user_id, expires_at)
        VALUES (%s, %s, %s)
        """,
        (session_id, user_id, expires_at),
    )
    return session_id


def is_session_active(session_id, user_id, token_version):
    if not session_id or user_id is None or token_version is None:
        return False

    return query_one(
        """
        SELECT 1
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.id = %s
          AND s.user_id = %s
          AND s.revoked_at IS NULL
          AND s.expires_at > now()
          AND u.token_version = %s
        """,
        (session_id, user_id, token_version),
    ) is not None


def touch_session(session_id):
    """Record that an active authentication session was used."""
    execute(
        """
        UPDATE auth_sessions
        SET last_used_at = now()
        WHERE id = %s AND revoked_at IS NULL
        """,
        (session_id,),
    )


def revoke_session(session_id):
    """Remove or invalidate session safely."""
    if not session_id:
        return

    execute(
        """
        UPDATE auth_sessions
        SET revoked_at = COALESCE(revoked_at, now())
        WHERE id = %s
        """,
        (session_id,),
    )



def reset_password_and_revoke_sessions(user_id, password, token_version):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    token_version = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (hash_password(password), token_version, user_id),
            )
            cursor.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = COALESCE(revoked_at, now())
                WHERE user_id = %s
                """,
                (user_id,),
            )


# ---------------------------------------------------------------------- tags

def get_all_tags():
    return query_all("SELECT * FROM tags ORDER BY name")


def get_tags_for_user(user_id):
    return query_all(
        """
        SELECT t.* FROM tags t
        JOIN user_tags ut ON ut.tag_id = t.id
        WHERE ut.user_id = %s
        ORDER BY t.name
        """,
        (user_id,),
    )


def set_user_tags(user_id, tag_ids):
    unique_tag_ids = list(dict.fromkeys(tag_ids))

    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM tags WHERE id = ANY(%s::INTEGER[])",
                (unique_tag_ids,),
            )
            valid_ids = {row[0] for row in cursor.fetchall()}
            if valid_ids != set(unique_tag_ids):
                raise InvalidTagIdsError('One or more selected tags are invalid')

            cursor.execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))
            cursor.executemany(
                "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s)",
                [(user_id, tag_id) for tag_id in unique_tag_ids],
            )

    return get_tags_for_user(user_id)


# -------------------------------------------------------------------- photos

def get_photos_for_user(user_id):
    return query_all(
        "SELECT * FROM photos WHERE user_id = %s ORDER BY is_primary DESC, position, id",
        (user_id,),
    )


def count_photos(user_id):
    row = query_one("SELECT COUNT(*) AS c FROM photos WHERE user_id = %s", (user_id,))
    return row['c'] if row else 0


def get_primary_photo(user_id):
    return query_one("SELECT * FROM photos WHERE user_id = %s AND is_primary = true", (user_id,))


def add_photo(user_id, filename):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (PROFILE_LOCK_NAMESPACE, user_id),
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS photo_count,
                       COALESCE(MAX(position), -1) AS max_position
                FROM photos
                WHERE user_id = %s
                """,
                (user_id,),
            )
            state = dict(cursor.fetchone())
            if state['photo_count'] >= MAX_PHOTOS_PER_USER:
                raise PhotoLimitError(
                    f'You can have at most {MAX_PHOTOS_PER_USER} photos'
                )

            cursor.execute(
                """
                INSERT INTO photos (user_id, filename, is_primary, position)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (
                    user_id,
                    filename,
                    state['photo_count'] == 0,
                    state['max_position'] + 1,
                ),
            )
            return dict(cursor.fetchone())



def replace_photo_filename(user_id, photo_id, filename):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (PROFILE_LOCK_NAMESPACE, user_id),
            )
            cursor.execute(
                """
                SELECT *
                FROM photos
                WHERE id = %s AND user_id = %s
                """,
                (photo_id, user_id),
            )
            previous = cursor.fetchone()
            if not previous:
                return None

            cursor.execute(
                """
                UPDATE photos
                SET filename = %s
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (filename, photo_id, user_id),
            )
            photo = dict(cursor.fetchone())
            photo['previous_filename'] = previous['filename']
            return photo


def delete_photo_and_promote(user_id, photo_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (PROFILE_LOCK_NAMESPACE, user_id),
            )
            cursor.execute(
                "SELECT * FROM photos WHERE id = %s AND user_id = %s",
                (photo_id, user_id),
            )
            photo = cursor.fetchone()
            if not photo:
                return None

            cursor.execute(
                "SELECT COUNT(*) AS photo_count FROM photos WHERE user_id = %s",
                (user_id,),
            )
            if cursor.fetchone()['photo_count'] <= 1:
                raise LastPhotoError('At least one profile photo is required')

            cursor.execute(
                """
                DELETE FROM photos
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (photo_id, user_id),
            )
            deleted = cursor.fetchone()

            cursor.execute(
                """
                WITH ordered AS (
                    SELECT id, (row_number() OVER (
                        ORDER BY is_primary DESC, position, id
                    ) - 1)::INTEGER AS new_position
                    FROM photos
                    WHERE user_id = %s
                )
                UPDATE photos p
                SET position = ordered.new_position
                FROM ordered
                WHERE p.id = ordered.id
                """,
                (user_id,),
            )

            if deleted['is_primary']:
                cursor.execute(
                    """
                    UPDATE photos
                    SET is_primary = true,
                        position = 0
                    WHERE id = (
                        SELECT id
                        FROM photos
                        WHERE user_id = %s
                        ORDER BY position, id
                        LIMIT 1
                    )
                    """,
                    (user_id,),
                )

            return dict(deleted)


def set_primary_photo(photo_id, user_id):
    """Set an owned image as the single primary profile photo."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (PROFILE_LOCK_NAMESPACE, user_id),
            )
            cursor.execute(
                "SELECT position FROM photos WHERE id = %s AND user_id = %s",
                (photo_id, user_id),
            )
            target = cursor.fetchone()
            if not target:
                return False

            cursor.execute(
                "UPDATE photos SET is_primary = false WHERE user_id = %s",
                (user_id,),
            )
            cursor.execute(
                """
                UPDATE photos
                SET position = position + 1
                WHERE user_id = %s
                  AND id <> %s
                  AND position < %s
                """,
                (user_id, photo_id, target['position']),
            )
            cursor.execute(
                """
                UPDATE photos
                SET is_primary = true,
                    position = 0
                WHERE id = %s AND user_id = %s
                """,
                (photo_id, user_id),
            )
            return True


# ---------------------------------------------------------- likes/views/blocks

def has_liked(liker_id, liked_id):
    """Return whether liked is true."""
    return query_one(
        "SELECT 1 FROM user_likes WHERE liker_id = %s AND liked_id = %s",
        (liker_id, liked_id),
    ) is not None


def is_connected(user_a_id, user_b_id):
    """Return whether connected is true."""
    return has_liked(user_a_id, user_b_id) and has_liked(user_b_id, user_a_id)


def like_user(liker_id, liked_id):
    """Insert one directional like and clear prior notification suppression."""
    inserted = execute(
        """
        INSERT INTO user_likes (liker_id, liked_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        RETURNING liker_id
        """,
        (liker_id, liked_id),
        returning=True,
    )
    if not inserted:
        return False

    clear_notification_suppression(liker_id, liked_id)
    return True


def unlike_user(liker_id, liked_id):
    """Remove one directional like and suppress future notifications after disconnect."""
    was_connected = is_connected(liker_id, liked_id)
    deleted = execute(
        """
        DELETE FROM user_likes
        WHERE liker_id = %s AND liked_id = %s
        RETURNING liker_id
        """,
        (liker_id, liked_id),
        returning=True,
    )
    if not deleted:
        return False, False

    if was_connected:
        suppress_notifications_from(liker_id, liked_id)

    return True, was_connected


def get_likers(user_id):
    """Return visible users who have liked the account."""
    return query_all(
        """
        SELECT u.*, l.created_at AS liked_at
        FROM users u
        JOIN user_likes l ON l.liker_id = u.id
        WHERE l.liked_id = %s
          AND NOT EXISTS (
              SELECT 1 FROM user_blocks b
              WHERE (b.blocker_id = %s AND b.blocked_id = u.id)
                 OR (b.blocker_id = u.id AND b.blocked_id = %s)
          )
        ORDER BY l.created_at DESC
        """,
        (user_id, user_id, user_id),
    )


def get_outgoing_pending_likes(user_id):
    """Return outgoing likes that have not been reciprocated."""
    return query_all(
        """
        SELECT u.*, mine.created_at AS liked_at
        FROM user_likes mine
        JOIN users u ON u.id = mine.liked_id
        WHERE mine.liker_id = %s
          AND NOT EXISTS (
              SELECT 1
              FROM user_likes reverse_like
              WHERE reverse_like.liker_id = mine.liked_id
                AND reverse_like.liked_id = mine.liker_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM user_blocks b
              WHERE (b.blocker_id = %s AND b.blocked_id = u.id)
                 OR (b.blocker_id = u.id AND b.blocked_id = %s)
          )
        ORDER BY mine.created_at DESC
        """,
        (user_id, user_id, user_id),
    )


def get_incoming_pending_likes(user_id):
    """Return incoming likes that the user has not reciprocated."""
    return query_all(
        """
        SELECT u.*, incoming.created_at AS liked_at
        FROM user_likes incoming
        JOIN users u ON u.id = incoming.liker_id
        WHERE incoming.liked_id = %s
          AND NOT EXISTS (
              SELECT 1
              FROM user_likes my_like
              WHERE my_like.liker_id = incoming.liked_id
                AND my_like.liked_id = incoming.liker_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM user_blocks b
              WHERE (b.blocker_id = %s AND b.blocked_id = u.id)
                 OR (b.blocker_id = u.id AND b.blocked_id = %s)
          )
        ORDER BY incoming.created_at DESC
        """,
        (user_id, user_id, user_id),
    )


def get_matches(user_id):
    """Return visible users with reciprocal likes."""
    return query_all(
        """
        SELECT
            u.*,
            GREATEST(my_like.created_at, their_like.created_at) AS matched_at
        FROM user_likes my_like
        JOIN user_likes their_like
          ON their_like.liker_id = my_like.liked_id
         AND their_like.liked_id = my_like.liker_id
        JOIN users u ON u.id = my_like.liked_id
        WHERE my_like.liker_id = %s
          AND NOT EXISTS (
              SELECT 1 FROM user_blocks b
              WHERE (b.blocker_id = %s AND b.blocked_id = u.id)
                 OR (b.blocker_id = u.id AND b.blocked_id = %s)
          )
        ORDER BY matched_at DESC
        """,
        (user_id, user_id, user_id),
    )


def set_user_online(user_id, is_online):
    """
    Called from app.sockets on the true first-connect / last-disconnect for
    a user (not per-tab). Going offline also stamps last_activity so the
    "last seen" timestamp is accurate.
    """
    if is_online:
        execute("UPDATE users SET is_online = true WHERE id = %s", (user_id,))
    else:
        execute(
            "UPDATE users SET is_online = false, last_activity = now() WHERE id = %s",
            (user_id,),
        )


def reset_online_users():
    """Clear stale online flags left by a previous backend process."""
    execute(
        """
        UPDATE users
        SET is_online = false,
            last_activity = now()
        WHERE is_online = true
        """
    )


def is_blocked_either_way(user_a_id, user_b_id):
    """Return whether blocked either way is true."""
    return query_one(
        """
        SELECT 1 FROM user_blocks
        WHERE (blocker_id = %s AND blocked_id = %s)
           OR (blocker_id = %s AND blocked_id = %s)
        """,
        (user_a_id, user_b_id, user_b_id, user_a_id),
    ) is not None


def block_user(blocker_id, blocked_id):
    """
    Create the block and remove both directed likes in one transaction.

    Likes are current relationship state, not immutable history. Removing both
    rows guarantees that blocking always disconnects the users and that an
    unblock starts from an unrelated state.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                INSERT INTO user_blocks (blocker_id, blocked_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                RETURNING blocker_id
                """,
                (blocker_id, blocked_id),
            )
            created = cursor.fetchone() is not None

            cursor.execute(
                """
                DELETE FROM user_likes
                WHERE (liker_id = %s AND liked_id = %s)
                   OR (liker_id = %s AND liked_id = %s)
                RETURNING liker_id, liked_id
                """,
                (blocker_id, blocked_id, blocked_id, blocker_id),
            )
            removed_likes = [dict(row) for row in cursor.fetchall()]

    return {
        'created': created,
        'removed_likes': removed_likes,
        'was_connected': len(removed_likes) == 2,
    }


def unblock_user(blocker_id, blocked_id):
    """Delete one directional block owned by the current user."""
    return execute(
        """
        DELETE FROM user_blocks
        WHERE blocker_id = %s AND blocked_id = %s
        RETURNING blocker_id
        """,
        (blocker_id, blocked_id),
        returning=True,
    ) is not None


def get_blocked_users(blocker_id):
    """Return profiles blocked by the current user."""
    return query_all(
        """
        SELECT u.*, b.created_at AS blocked_at
        FROM users u
        JOIN user_blocks b ON b.blocked_id = u.id
        WHERE b.blocker_id = %s
        ORDER BY b.created_at DESC
        """,
        (blocker_id,),
    )


def suppress_notifications_from(user_id, suppressed_user_id):
    """Suppress future notifications from a disconnected user."""
    execute(
        """
        INSERT INTO notification_suppressions (user_id, suppressed_user_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        (user_id, suppressed_user_id),
    )


def clear_notification_suppression(user_id, suppressed_user_id):
    """Remove or invalidate notification suppression safely."""
    execute(
        """
        DELETE FROM notification_suppressions
        WHERE user_id = %s AND suppressed_user_id = %s
        """,
        (user_id, suppressed_user_id),
    )


def notifications_are_suppressed(user_id, from_user_id):
    """Return whether notifications from one user are currently suppressed."""
    if from_user_id is None:
        return False

    return query_one(
        """
        SELECT 1
        FROM notification_suppressions
        WHERE user_id = %s AND suppressed_user_id = %s
        """,
        (user_id, from_user_id),
    ) is not None


def record_view(viewer_id, viewed_id, visit_id):
    """Insert one logical profile visit and ignore a repeated idempotency key."""
    return execute(
        """
        INSERT INTO user_views (viewer_id, viewed_id, visit_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (viewer_id, visit_id) DO NOTHING
        RETURNING *
        """,
        (viewer_id, viewed_id, visit_id),
        returning=True,
    )


def get_viewers(user_id):
    """Return profile visit history visible to the account owner."""
    return query_all(
        """
        SELECT u.*, v.id AS view_id, v.viewed_at
        FROM users u
        JOIN user_views v ON v.viewer_id = u.id
        WHERE v.viewed_id = %s
          AND NOT EXISTS (
              SELECT 1 FROM user_blocks b
              WHERE (b.blocker_id = %s AND b.blocked_id = u.id)
                 OR (b.blocker_id = u.id AND b.blocked_id = %s)
          )
        ORDER BY v.viewed_at DESC, v.id DESC
        """,
        (user_id, user_id, user_id),
    )

# -------------------------------------------------------- fame rating / etc.

def calculate_age(birth_date):
    """Calculate a current age from a database date value."""
    if not birth_date:
        return None

    today = date.today()
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def missing_profile_fields(user, tags, photos):
    """Return every mandatory field still preventing profile completion."""
    missing = []

    if not str(user.get('first_name') or '').strip():
        missing.append('firstName')
    if not str(user.get('last_name') or '').strip():
        missing.append('lastName')
    if not str(user.get('email') or '').strip():
        missing.append('email')
    age = calculate_age(user.get('birth_date'))
    if age is None or age < MIN_PROFILE_AGE or age > MAX_PROFILE_AGE:
        missing.append('birthDate')
    if not user.get('gender'):
        missing.append('gender')
    if not user.get('sexual_preferences'):
        missing.append('sexualPreferences')
    if not str(user.get('biography') or '').strip():
        missing.append('biography')
    if not tags:
        missing.append('tags')
    if not any(photo['is_primary'] for photo in photos):
        missing.append('profilePicture')
    if (
        not str(user.get('location_name') or '').strip()
        or user.get('latitude') is None
        or user.get('longitude') is None
    ):
        missing.append('location')

    return missing


def is_profile_complete(user, tags, photos):
    """Return whether all mandatory profile fields are present."""
    return len(missing_profile_fields(user, tags, photos)) == 0


def is_user_profile_complete(user_id):
    """Load profile data and evaluate completion for one user."""
    user = get_user_by_id(user_id)
    if not user:
        return False

    return is_profile_complete(
        user,
        get_tags_for_user(user_id),
        get_photos_for_user(user_id),
    )


def profile_completion_points(user, tags, photos_count):
    """Calculate the documented profile-completion component of fame rating."""
    points = 0
    if user['birth_date']:
        points += 1
    if user['gender']:
        points += 1
    if user['sexual_preferences']:
        points += 1
    if user['biography']:
        points += 2
    if tags:
        points += 1
    if photos_count > 0:
        points += 2
    if user['latitude'] is not None and user['longitude'] is not None:
        points += 2
    return points


def calculate_fame_rating(user_id):
    """Calculate the documented, bounded fame score from likes, views, and completion."""
    likes = query_one(
        "SELECT COUNT(*) AS c FROM user_likes WHERE liked_id = %s",
        (user_id,),
    )['c']
    views = query_one(
        "SELECT COUNT(*) AS c FROM user_views WHERE viewed_id = %s",
        (user_id,),
    )['c']

    user = get_user_by_id(user_id)
    tags = get_tags_for_user(user_id)
    photos_count = count_photos(user_id)
    completion = profile_completion_points(user, tags, photos_count)

    raw_rating = (likes * 3) + (views * 0.5) + completion
    return min(MAX_FAME_RATING, max(0, round(raw_rating, 2)))


def update_fame_rating(user_id):
    """Recalculate and persist the bounded fame rating."""
    rating = calculate_fame_rating(user_id)
    execute("UPDATE users SET fame_rating = %s WHERE id = %s", (rating, user_id))
    return rating


# --------------------------------------------------------------- discovery

def discover_users(current_user_id, filters):
    """Execute the compatibility, privacy, filter, ranking, and pagination SQL."""
    order_by = {
        'recommended': (
            'same_area DESC, distance_km ASC, '
            'common_tag_count DESC, fame_rating DESC, id ASC'
        ),
        'age': f"age {filters['order'].upper()}, id ASC",
        'distance': f"distance_km {filters['order'].upper()}, id ASC",
        'fame': f"fame_rating {filters['order'].upper()}, id ASC",
        'commonTags': (
            f"common_tag_count {filters['order'].upper()}, id ASC"
        ),
    }[filters['sort']]

    base_sql = """
        WITH current_profile AS (
            SELECT
                id,
                gender,
                sexual_preferences,
                latitude,
                longitude,
                location_name
            FROM users
            WHERE id = %s
        ),
        candidate_profiles AS (
            SELECT
                u.*,
                primary_photo.filename AS primary_filename,
                DATE_PART('year', AGE(CURRENT_DATE, u.birth_date))::INTEGER AS age,
                (
                    SELECT COUNT(*)::INTEGER
                    FROM user_tags current_tags
                    JOIN user_tags candidate_tags
                      ON candidate_tags.tag_id = current_tags.tag_id
                    WHERE current_tags.user_id = %s
                      AND candidate_tags.user_id = u.id
                ) AS common_tag_count,
                (
                    LOWER(BTRIM(
                        CASE
                            WHEN POSITION(',' IN u.location_name) > 0
                            THEN SPLIT_PART(u.location_name, ',', 2)
                            ELSE u.location_name
                        END
                    )) = LOWER(BTRIM(
                        CASE
                            WHEN POSITION(',' IN current_profile.location_name) > 0
                            THEN SPLIT_PART(current_profile.location_name, ',', 2)
                            ELSE current_profile.location_name
                        END
                    ))
                ) AS same_area,
                6371.0 * 2 * ASIN(
                    SQRT(
                        LEAST(
                            1.0,
                            GREATEST(
                                0.0,
                                POWER(
                                    SIN(
                                        RADIANS(
                                            u.latitude - current_profile.latitude
                                        ) / 2
                                    ),
                                    2
                                )
                                + COS(RADIANS(current_profile.latitude))
                                * COS(RADIANS(u.latitude))
                                * POWER(
                                    SIN(
                                        RADIANS(
                                            u.longitude - current_profile.longitude
                                        ) / 2
                                    ),
                                    2
                                )
                            )
                        )
                    )
                ) AS distance_km
            FROM users u
            CROSS JOIN current_profile
            JOIN photos primary_photo
              ON primary_photo.user_id = u.id
             AND primary_photo.is_primary = true
            WHERE u.id <> current_profile.id
              AND u.is_verified = true
              AND u.birth_date IS NOT NULL
              AND u.gender IS NOT NULL
              AND CARDINALITY(u.sexual_preferences) BETWEEN 1 AND 3
              AND LENGTH(BTRIM(COALESCE(u.biography, ''))) > 0
              AND LENGTH(BTRIM(COALESCE(u.location_name, ''))) > 0
              AND u.latitude IS NOT NULL
              AND u.longitude IS NOT NULL
              AND u.gender = ANY(current_profile.sexual_preferences)
              AND current_profile.gender = ANY(u.sexual_preferences)
              AND EXISTS (
                  SELECT 1
                  FROM user_tags required_tag
                  WHERE required_tag.user_id = u.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_blocks blocked
                  WHERE (
                      blocked.blocker_id = current_profile.id
                      AND blocked.blocked_id = u.id
                  ) OR (
                      blocked.blocker_id = u.id
                      AND blocked.blocked_id = current_profile.id
                  )
              )
        )
    """

    filter_clauses = [
        'age BETWEEN %s AND %s',
        'fame_rating BETWEEN %s AND %s',
    ]
    parameters = [
        current_user_id,
        current_user_id,
        filters['min_age'],
        filters['max_age'],
        filters['min_fame'],
        filters['max_fame'],
    ]

    if filters['location']:
        filter_clauses.append('location_name ILIKE %s')
        parameters.append(f"%{filters['location']}%")

    if filters['tag_ids']:
        filter_clauses.append(
            """
            (
                SELECT COUNT(DISTINCT selected_tag.tag_id)
                FROM user_tags selected_tag
                WHERE selected_tag.user_id = candidate_profiles.id
                  AND selected_tag.tag_id = ANY(%s::INTEGER[])
            ) = %s
            """
        )
        parameters.extend([
            filters['tag_ids'],
            len(filters['tag_ids']),
        ])

    where_sql = ' AND '.join(filter_clauses)

    count_row = query_one(
        base_sql
        + f"""
        SELECT COUNT(*) AS total
        FROM candidate_profiles
        WHERE {where_sql}
        """,
        tuple(parameters),
    )
    total = count_row['total'] if count_row else 0

    offset = (filters['page'] - 1) * filters['page_size']
    profiles = query_all(
        base_sql
        + f"""
        SELECT
            candidate_profiles.*,
            ARRAY(
                SELECT tag.name
                FROM tags tag
                JOIN user_tags profile_tag
                  ON profile_tag.tag_id = tag.id
                WHERE profile_tag.user_id = candidate_profiles.id
                ORDER BY tag.name
            ) AS tag_names
        FROM candidate_profiles
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        tuple(parameters + [filters['page_size'], offset]),
    )

    total_pages = (
        (total + filters['page_size'] - 1) // filters['page_size']
        if total
        else 0
    )

    return {
        'profiles': profiles,
        'total': total,
        'total_pages': total_pages,
    }


def discovery_user_to_dict(user):
    """Serialize discovery user for the API response."""
    return {
        'id': user['id'],
        'username': user['username'],
        'firstName': user['first_name'],
        'lastName': user['last_name'],
        'age': user['age'],
        'gender': user['gender'],
        'profilePicture': (
            f"/uploads/{user['primary_filename']}"
            if user.get('primary_filename')
            else None
        ),
        'fameRating': min(
            MAX_FAME_RATING,
            max(0, round(float(user['fame_rating'] or 0), 2)),
        ),
        'tags': list(user.get('tag_names') or []),
        'isOnline': user['is_online'],
        'lastActivity': to_iso_utc(user['last_activity']),
        'location': {
            'name': user['location_name'],
        },
        'distanceKm': round(float(user['distance_km']), 1),
        'commonTagCount': int(user['common_tag_count']),
    }


def approximate_coordinate(value):
    """Round a coordinate before exposing it on the public map."""
    return round(float(value), 2)


def approximate_map_location(user):
    """Serialize a privacy-rounded public map location."""
    return {
        'name': user['location_name'],
        'latitude': approximate_coordinate(user['latitude']),
        'longitude': approximate_coordinate(user['longitude']),
    }


def map_user_to_dict(user):
    """Serialize map user for the API response."""
    data = discovery_user_to_dict(user)
    data['location'] = {
        'name': user['location_name'],
        'latitude': approximate_coordinate(user['latitude']),
        'longitude': approximate_coordinate(user['longitude']),
    }
    return data


# --------------------------------------------------------------- serializers

def photo_to_dict(photo):
    """Serialize photo for the API response."""
    return {
        'id': photo['id'],
        'url': f"/uploads/{photo['filename']}",
        'isPrimary': photo['is_primary'],
        'position': photo['position'],
    }


def user_to_dict(user, include_private=False):
    """Serialize a user while exposing private fields only to the account owner."""
    tags = get_tags_for_user(user['id'])
    photos = get_photos_for_user(user['id'])
    primary = get_primary_photo(user['id'])

    location = {'name': user['location_name']} if user['location_name'] else None
    if include_private and (
        user['location_name']
        or user['latitude'] is not None
        or user['longitude'] is not None
    ):
        location = {
            'name': user['location_name'],
            'latitude': user['latitude'],
            'longitude': user['longitude'],
        }

    data = {
        'id': user['id'],
        'username': user['username'],
        'firstName': user['first_name'],
        'lastName': user['last_name'],
        'age': calculate_age(user['birth_date']),
        'gender': user['gender'],
        'sexualPreferences': list(user['sexual_preferences'] or []),
        'biography': user['biography'],
        'profilePicture': f"/uploads/{primary['filename']}" if primary else None,
        'photos': [photo_to_dict(p) for p in photos],
        'fameRating': min(
            MAX_FAME_RATING,
            max(0, round(float(user['fame_rating'] or 0), 2)),
        ),
        'tags': [t['name'] for t in tags],
        'isOnline': user['is_online'],
        'lastActivity': to_iso_utc(user['last_activity']),
        'location': location,
        'isProfileComplete': is_profile_complete(user, tags, photos),
        'missingProfileFields': missing_profile_fields(user, tags, photos),
    }

    if include_private:
        data['email'] = user['email']
        data['birthDate'] = user['birth_date'].isoformat() if user['birth_date'] else None
        data['isVerified'] = user['is_verified']
        data['gpsConsent'] = user['gps_consent']

    return data


def view_to_dict(view):
    """Serialize view for the API response."""
    return {
        'id': view['view_id'],
        'viewedAt': to_iso_utc(view['viewed_at']),
        'viewer': user_to_dict(view),
    }


def like_to_dict(liker):
    """Serialize like for the API response."""
    return {
        'likedAt': to_iso_utc(liker['liked_at']),
        'user': user_to_dict(liker),
    }


def match_to_dict(match):
    """Serialize match for the API response."""
    return {
        'matchedAt': to_iso_utc(match['matched_at']),
        'user': user_to_dict(match),
    }


def blocked_user_to_dict(blocked_user):
    """Serialize blocked user for the API response."""
    return {
        'blockedAt': to_iso_utc(blocked_user['blocked_at']),
        'user': user_to_dict(blocked_user),
    }


# ------------------------------------------------------------------ messages

def create_message(sender_id, receiver_id, content):
    """Persist one message between authorized participants."""
    return execute(
        """
        INSERT INTO messages (sender_id, receiver_id, content)
        VALUES (%s, %s, %s)
        RETURNING *
        """,
        (sender_id, receiver_id, content),
        returning=True,
    )


def has_conversation_history(user_a_id, user_b_id):
    """Return whether conversation history is true."""
    return query_one(
        """
        SELECT 1
        FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        LIMIT 1
        """,
        (user_a_id, user_b_id, user_b_id, user_a_id),
    ) is not None


def get_chat_contacts(user_id):
    """Return matches and historical conversations with unread state."""
    return query_all(
        """
        WITH viewer_profile AS (
            SELECT %s::INTEGER AS id
        )
        SELECT
            u.*,
            primary_photo.filename AS primary_filename,
            (
                EXISTS (
                    SELECT 1
                    FROM user_likes mine
                    WHERE mine.liker_id = viewer_profile.id
                      AND mine.liked_id = u.id
                )
                AND EXISTS (
                    SELECT 1
                    FROM user_likes theirs
                    WHERE theirs.liker_id = u.id
                      AND theirs.liked_id = viewer_profile.id
                )
            ) AS can_message,
            last_message.id AS last_message_id,
            last_message.sender_id AS last_message_sender_id,
            last_message.receiver_id AS last_message_receiver_id,
            last_message.content AS last_message_content,
            last_message.is_read AS last_message_is_read,
            last_message.created_at AS last_message_created_at,
            (
                SELECT COUNT(*)::INTEGER
                FROM messages unread_message
                WHERE unread_message.sender_id = u.id
                  AND unread_message.receiver_id = viewer_profile.id
                  AND unread_message.is_read = false
            ) AS unread_count
        FROM users u
        CROSS JOIN viewer_profile
        JOIN photos primary_photo
          ON primary_photo.user_id = u.id
         AND primary_photo.is_primary = true
        LEFT JOIN LATERAL (
            SELECT message.*
            FROM messages message
            WHERE (
                message.sender_id = viewer_profile.id
                AND message.receiver_id = u.id
            ) OR (
                message.sender_id = u.id
                AND message.receiver_id = viewer_profile.id
            )
            ORDER BY message.created_at DESC, message.id DESC
            LIMIT 1
        ) AS last_message ON true
        WHERE u.id <> viewer_profile.id
          AND u.is_verified = true
          AND u.birth_date IS NOT NULL
          AND u.gender IS NOT NULL
          AND CARDINALITY(u.sexual_preferences) BETWEEN 1 AND 3
          AND LENGTH(BTRIM(COALESCE(u.biography, ''))) > 0
          AND LENGTH(BTRIM(COALESCE(u.location_name, ''))) > 0
          AND u.latitude IS NOT NULL
          AND u.longitude IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM user_tags profile_tag
              WHERE profile_tag.user_id = u.id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM user_blocks blocked
              WHERE (
                  blocked.blocker_id = viewer_profile.id
                  AND blocked.blocked_id = u.id
              ) OR (
                  blocked.blocker_id = u.id
                  AND blocked.blocked_id = viewer_profile.id
              )
          )
          AND (
              last_message.id IS NOT NULL
              OR (
                  EXISTS (
                      SELECT 1
                      FROM user_likes mine
                      WHERE mine.liker_id = viewer_profile.id
                        AND mine.liked_id = u.id
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM user_likes theirs
                      WHERE theirs.liker_id = u.id
                        AND theirs.liked_id = viewer_profile.id
                  )
              )
          )
        ORDER BY
            last_message.created_at DESC NULLS LAST,
            u.username ASC
        """,
        (user_id,),
    )


def get_conversation(user_a_id, user_b_id, page=1, page_size=50):
    """Return one authorized conversation in chronological pages."""
    count_row = query_one(
        """
        SELECT COUNT(*) AS total
        FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        """,
        (user_a_id, user_b_id, user_b_id, user_a_id),
    )
    total = count_row['total'] if count_row else 0
    offset = (page - 1) * page_size

    messages = query_all(
        """
        SELECT *
        FROM (
            SELECT *
            FROM messages
            WHERE (sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s)
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
        ) recent_messages
        ORDER BY created_at ASC, id ASC
        """,
        (
            user_a_id,
            user_b_id,
            user_b_id,
            user_a_id,
            page_size,
            offset,
        ),
    )

    total_pages = (
        (total + page_size - 1) // page_size
        if total
        else 0
    )

    return {
        'messages': messages,
        'total': total,
        'total_pages': total_pages,
    }


def mark_conversation_read(user_id, other_user_id):
    """Mark incoming messages as read and emit delivery receipts."""
    updated_messages = query_all(
        """
        UPDATE messages
        SET is_read = true
        WHERE receiver_id = %s
          AND sender_id = %s
          AND is_read = false
        RETURNING id
        """,
        (user_id, other_user_id),
    )

    return [message['id'] for message in updated_messages]


def count_unread_messages(user_id):
    """Return the current unread messages count."""
    row = query_one(
        """
        SELECT COUNT(*) AS total
        FROM messages message
        WHERE message.receiver_id = %s
          AND message.is_read = false
          AND NOT EXISTS (
              SELECT 1
              FROM user_blocks blocked
              WHERE (
                  blocked.blocker_id = %s
                  AND blocked.blocked_id = message.sender_id
              ) OR (
                  blocked.blocker_id = message.sender_id
                  AND blocked.blocked_id = %s
              )
          )
        """,
        (user_id, user_id, user_id),
    )
    return row['total'] if row else 0


def chat_user_to_dict(user):
    """Serialize chat user for the API response."""
    filename = user.get('primary_filename')
    if filename is None:
        primary = get_primary_photo(user['id'])
        filename = primary['filename'] if primary else None

    return {
        'id': user['id'],
        'username': user['username'],
        'firstName': user['first_name'],
        'lastName': user['last_name'],
        'profilePicture': f"/uploads/{filename}" if filename else None,
        'isOnline': user['is_online'],
        'lastActivity': to_iso_utc(user['last_activity']),
    }


def chat_contact_to_dict(contact):
    """Serialize chat contact for the API response."""
    last_message = None
    if contact.get('last_message_id') is not None:
        last_message = {
            'id': contact['last_message_id'],
            'senderId': contact['last_message_sender_id'],
            'receiverId': contact['last_message_receiver_id'],
            'content': contact['last_message_content'],
            'isRead': contact['last_message_is_read'],
            'createdAt': to_iso_utc(contact['last_message_created_at']),
        }

    return {
        'user': chat_user_to_dict(contact),
        'canMessage': bool(contact['can_message']),
        'unreadCount': int(contact.get('unread_count') or 0),
        'lastMessage': last_message,
    }


def message_to_dict(message):
    """Serialize message for the API response."""
    return {
        'id': message['id'],
        'senderId': message['sender_id'],
        'receiverId': message['receiver_id'],
        'content': message['content'],
        'isRead': message['is_read'],
        'createdAt': to_iso_utc(message['created_at']),
    }


# -------------------------------------------------------------------- reports

def create_report(reporter_id, reported_user_id, reason='fake_account'):
    """Insert one idempotent fake-account report for a user pair."""
    return execute(
        """
        INSERT INTO reports (reporter_id, reported_user_id, reason)
        VALUES (%s, %s, %s)
        ON CONFLICT (reporter_id, reported_user_id) DO NOTHING
        RETURNING *
        """,
        (reporter_id, reported_user_id, reason),
        returning=True,
    )


def has_reported(reporter_id, reported_user_id):
    """Return whether reported is true."""
    return query_one(
        "SELECT 1 FROM reports WHERE reporter_id = %s AND reported_user_id = %s",
        (reporter_id, reported_user_id),
    ) is not None


# --------------------------------------------------------------- notifications

def create_notification(user_id, type_, from_user_id=None, content=None):
    """Persist and emit an allowed notification after block and suppression checks."""
    if not is_user_profile_complete(user_id):
        return None

    if from_user_id is not None:
        if not is_user_profile_complete(from_user_id):
            return None
        if is_blocked_either_way(user_id, from_user_id):
            return None
        if notifications_are_suppressed(user_id, from_user_id):
            return None

    notif = execute(
        """
        INSERT INTO notifications (user_id, type, from_user_id, content)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (user_id, type_, from_user_id, content),
        returning=True,
    )
    from app.sockets import socketio
    socketio.emit('notification', notification_to_dict(notif), room=f'user:{user_id}')
    return notif


def notification_to_dict(notif):
    """Serialize notification for the API response."""
    from_user = get_user_by_id(notif['from_user_id']) if notif['from_user_id'] else None
    return {
        'id': notif['id'],
        'type': notif['type'],
        'content': notif['content'],
        'isRead': notif['is_read'],
        'createdAt': to_iso_utc(notif['created_at']),
        'fromUser': user_to_dict(from_user) if from_user else None,
    }


def get_notifications_for_user(user_id, limit=50):
    """Return recent notifications in newest-first order."""
    return query_all(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
        (user_id, limit),
    )


def count_unread_notifications(user_id):
    """Return the current unread notifications count."""
    row = query_one(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = %s AND is_read = false",
        (user_id,),
    )
    return row['c'] if row else 0


def mark_notification_read(notification_id, user_id):
    """Mark one notification as read only for its owner."""
    execute(
        "UPDATE notifications SET is_read = true WHERE id = %s AND user_id = %s",
        (notification_id, user_id),
    )


def mark_all_notifications_read(user_id):
    """Mark every notification for one user as read."""
    execute(
        "UPDATE notifications SET is_read = true WHERE user_id = %s AND is_read = false",
        (user_id,),
    )


# ---------------------------------------------------------------- date events

def create_date_event(proposer_id, recipient_id, scheduled_for, location, note=None):
    """Persist a date proposal and return its database row."""
    return execute(
        """
        INSERT INTO date_events (
            proposer_id,
            recipient_id,
            scheduled_for,
            location,
            note
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            proposer_id,
            recipient_id,
            scheduled_for,
            location,
            note,
        ),
        returning=True,
    )


def get_date_event(event_id):
    """Return one date proposal by identifier."""
    return query_one(
        "SELECT * FROM date_events WHERE id = %s",
        (event_id,),
    )


def get_date_events_for_user(user_id):
    """Return visible date proposals involving one user."""
    return query_all(
        """
        SELECT *
        FROM date_events event
        WHERE (event.proposer_id = %s OR event.recipient_id = %s)
          AND NOT EXISTS (
              SELECT 1
              FROM user_blocks blocked
              WHERE (
                  blocked.blocker_id = event.proposer_id
                  AND blocked.blocked_id = event.recipient_id
              ) OR (
                  blocked.blocker_id = event.recipient_id
                  AND blocked.blocked_id = event.proposer_id
              )
          )
        ORDER BY event.scheduled_for ASC, event.id ASC
        """,
        (user_id, user_id),
    )


def respond_to_date_event(event_id, recipient_id, status):
    """Accept or decline a pending proposal as its recipient."""
    return execute(
        """
        UPDATE date_events
        SET status = %s,
            updated_at = now()
        WHERE id = %s
          AND recipient_id = %s
          AND status = 'pending'
          AND scheduled_for > now()
        RETURNING *
        """,
        (status, event_id, recipient_id),
        returning=True,
    )


def cancel_date_event(event_id, user_id):
    """Cancel a pending or accepted future proposal as a participant."""
    return execute(
        """
        UPDATE date_events
        SET status = 'cancelled',
            updated_at = now()
        WHERE id = %s
          AND (proposer_id = %s OR recipient_id = %s)
          AND status IN ('pending', 'accepted')
          AND scheduled_for > now()
        RETURNING *
        """,
        (event_id, user_id, user_id),
        returning=True,
    )


def date_event_user_to_dict(user):
    """Serialize date event user for the API response."""
    if not user:
        return None

    photo = get_primary_photo(user['id'])
    return {
        'id': user['id'],
        'username': user['username'],
        'firstName': user['first_name'],
        'lastName': user['last_name'],
        'profilePicture': (
            f"/uploads/{photo['filename']}"
            if photo
            else None
        ),
    }


def date_event_to_dict(event):
    """Serialize a date proposal with participant-relative action permissions."""
    proposer = get_user_by_id(event['proposer_id'])
    recipient = get_user_by_id(event['recipient_id'])
    return {
        'id': event['id'],
        'proposer': date_event_user_to_dict(proposer),
        'recipient': date_event_user_to_dict(recipient),
        'scheduledFor': to_iso_utc(event['scheduled_for']),
        'location': event['location'],
        'note': event['note'],
        'status': event['status'],
        'createdAt': to_iso_utc(event['created_at']),
        'updatedAt': to_iso_utc(event['updated_at']),
    }

# --------------------------------------------------------------- authentication 42 google

def get_user_by_oauth(provider, oauth_id):
    """Return the local user linked to one provider identity."""
    return query_one(
        """
        SELECT users.*
        FROM oauth_identities identity
        JOIN users ON users.id = identity.user_id
        WHERE identity.provider = %s
          AND identity.provider_user_id = %s
        """,
        (provider, oauth_id),
    )


def create_oauth_user(username, email, first_name, last_name, provider, oauth_id):
    """Create a verified OAuth user and provider identity atomically."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                INSERT INTO users (
                    username,
                    email,
                    first_name,
                    last_name,
                    is_verified
                )
                VALUES (%s, %s, %s, %s, true)
                RETURNING *
                """,
                (username, email, first_name, last_name),
            )
            user = dict(cursor.fetchone())

            cursor.execute(
                """
                INSERT INTO oauth_identities (
                    user_id,
                    provider,
                    provider_user_id,
                    provider_email
                )
                VALUES (%s, %s, %s, %s)
                """,
                (user['id'], provider, oauth_id, email),
            )
            return user


def link_oauth_to_user(user_id, provider, oauth_id, provider_email):
    """Link a provider identity while preventing cross-account identity conflicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT user_id
                FROM oauth_identities
                WHERE provider = %s
                  AND provider_user_id = %s
                """,
                (provider, oauth_id),
            )
            provider_identity = cursor.fetchone()
            if provider_identity and provider_identity['user_id'] != user_id:
                raise OAuthIdentityConflictError(
                    'This provider identity is already linked to another account'
                )

            cursor.execute(
                """
                SELECT provider_user_id
                FROM oauth_identities
                WHERE user_id = %s
                  AND provider = %s
                """,
                (user_id, provider),
            )
            existing_identity = cursor.fetchone()
            if (
                existing_identity
                and existing_identity['provider_user_id'] != oauth_id
            ):
                raise OAuthIdentityConflictError(
                    f'This account already has a different {provider} identity'
                )

            cursor.execute(
                """
                INSERT INTO oauth_identities (
                    user_id,
                    provider,
                    provider_user_id,
                    provider_email
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (provider, provider_user_id)
                DO UPDATE SET provider_email = EXCLUDED.provider_email
                """,
                (user_id, provider, oauth_id, provider_email),
            )
            cursor.execute(
                """
                UPDATE users
                SET is_verified = true,
                    updated_at = now()
                WHERE id = %s
                """,
                (user_id,),
            )



def generate_unique_username(base):
    """Create a normalized available username for an OAuth account."""
    normalized = re.sub(r'[^a-z0-9_]+', '_', base.lower())
    normalized = re.sub(r'_+', '_', normalized).strip('_')
    base = normalized[:40] or 'user'
    candidate = base
    n = 0
    while get_user_by_username(candidate):
        n += 1
        candidate = f"{base[:50 - len(str(n))]}{n}"
    return candidate
