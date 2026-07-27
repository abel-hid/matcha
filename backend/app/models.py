
from datetime import datetime, timedelta, timezone
import bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token

from app.db import query_one, query_all, execute

MAX_PHOTOS_PER_USER = 5


# ---------------------------------------------------------------- passwords

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def get_tokens_for_user(user_id):
    identity = str(user_id)
    return create_access_token(identity=identity), create_refresh_token(identity=identity)


def to_iso_utc(dt):
    """
    Postgres TIMESTAMP columns are naive -- dt.isoformat() alone produces
    something like '2026-07-23T14:00:00' with no timezone marker. JS's
    `new Date(...)` then parses that as *local* time, not UTC, silently
    shifting every timestamp by the browser's UTC offset (e.g. exactly 1h
    off for a GMT+1 user). Stamping it explicitly as UTC here fixes that at
    the source instead of needing every frontend consumer to know to adjust.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


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
    'first_name', 'last_name', 'email', 'is_verified', 'gender',
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


def get_or_create_tag(name):
    tag = query_one("SELECT * FROM tags WHERE name = %s", (name,))
    if tag:
        return tag
    return execute("INSERT INTO tags (name) VALUES (%s) RETURNING *", (name,), returning=True)


def set_user_tags(user_id, tag_names):
    execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))
    tags = []
    for name in tag_names:
        tag = get_or_create_tag(name)
        execute(
            "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, tag['id']),
        )
        tags.append(tag)
    return tags


# -------------------------------------------------------------------- photos

def get_photos_for_user(user_id):
    return query_all("SELECT * FROM photos WHERE user_id = %s ORDER BY position", (user_id,))


def count_photos(user_id):
    row = query_one("SELECT COUNT(*) AS c FROM photos WHERE user_id = %s", (user_id,))
    return row['c'] if row else 0


def get_primary_photo(user_id):
    return query_one("SELECT * FROM photos WHERE user_id = %s AND is_primary = true", (user_id,))


def add_photo(user_id, filename):
    current_count = count_photos(user_id)
    return execute(
        """
        INSERT INTO photos (user_id, filename, is_primary, position)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (user_id, filename, current_count == 0, current_count),
        returning=True,
    )


def get_photo(photo_id, user_id):
    return query_one("SELECT * FROM photos WHERE id = %s AND user_id = %s", (photo_id, user_id))


def delete_photo(photo_id, user_id):
    execute("DELETE FROM photos WHERE id = %s AND user_id = %s", (photo_id, user_id))


def set_primary_photo(photo_id, user_id):
    execute("UPDATE photos SET is_primary = false WHERE user_id = %s", (user_id,))
    execute("UPDATE photos SET is_primary = true WHERE id = %s AND user_id = %s", (photo_id, user_id))


def promote_next_photo_to_primary(user_id):
    next_photo = query_one(
        "SELECT * FROM photos WHERE user_id = %s ORDER BY position LIMIT 1", (user_id,)
    )
    if next_photo:
        execute("UPDATE photos SET is_primary = true WHERE id = %s", (next_photo['id'],))


# ---------------------------------------------------------- likes/views/blocks

def has_liked(liker_id, liked_id):
    return query_one(
        "SELECT 1 FROM user_likes WHERE liker_id = %s AND liked_id = %s", (liker_id, liked_id)
    ) is not None


def like_user(liker_id, liked_id):
    execute(
        "INSERT INTO user_likes (liker_id, liked_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (liker_id, liked_id),
    )


def unlike_user(liker_id, liked_id):
    execute("DELETE FROM user_likes WHERE liker_id = %s AND liked_id = %s", (liker_id, liked_id))


def get_likers(user_id):
    return query_all("""
        SELECT u.* FROM users u
        JOIN user_likes l ON l.liker_id = u.id
        WHERE l.liked_id = %s
          AND NOT EXISTS (
              SELECT 1 FROM user_blocks b
              WHERE (b.blocker_id = %s AND b.blocked_id = u.id)
                 OR (b.blocker_id = u.id AND b.blocked_id = %s)
          )
        ORDER BY l.created_at DESC
    """, (user_id, user_id, user_id))


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


def is_blocked_either_way(user_a_id, user_b_id):
    return query_one(
        """
        SELECT 1 FROM user_blocks
        WHERE (blocker_id = %s AND blocked_id = %s)
           OR (blocker_id = %s AND blocked_id = %s)
        """,
        (user_a_id, user_b_id, user_b_id, user_a_id),
    ) is not None


def block_user(blocker_id, blocked_id):
    execute(
        "INSERT INTO user_blocks (blocker_id, blocked_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (blocker_id, blocked_id),
    )


def unblock_user(blocker_id, blocked_id):
    execute("DELETE FROM user_blocks WHERE blocker_id = %s AND blocked_id = %s", (blocker_id, blocked_id))


VIEW_RENOTIFY_COOLDOWN = timedelta(seconds=10)  #set to 10 seconds for testing


def record_view(viewer_id, viewed_id):
    """
    Insert or refresh a view timestamp.
    Returns True if a 'view' notification should fire for this visit — i.e.
    this is the first-ever view, or the last one was more than
    VIEW_RENOTIFY_COOLDOWN ago. Repeated views within the cooldown (e.g. the
    viewer refreshing the page a few times) update viewed_at but don't
    re-trigger the notification.
    """
    existing = query_one(
        "SELECT viewed_at FROM user_views WHERE viewer_id = %s AND viewed_id = %s",
        (viewer_id, viewed_id),
    )

    if existing is None:
        execute("INSERT INTO user_views (viewer_id, viewed_id) VALUES (%s, %s)", (viewer_id, viewed_id))
        return True

    execute(
        "UPDATE user_views SET viewed_at = now() WHERE viewer_id = %s AND viewed_id = %s",
        (viewer_id, viewed_id),
    )
    return (datetime.utcnow() - existing['viewed_at']) > VIEW_RENOTIFY_COOLDOWN


def get_viewers(user_id):
    return query_all("""
        SELECT u.* FROM users u
        JOIN user_views v ON v.viewer_id = u.id
        WHERE v.viewed_id = %s
          AND NOT EXISTS (
              SELECT 1 FROM user_blocks b
              WHERE (b.blocker_id = %s AND b.blocked_id = u.id)
                 OR (b.blocker_id = u.id AND b.blocked_id = %s)
          )
        ORDER BY v.viewed_at DESC
    """, (user_id, user_id, user_id))

# -------------------------------------------------------- fame rating / etc.

def update_fame_rating(user_id):
    likes = query_one("SELECT COUNT(*) AS c FROM user_likes WHERE liked_id = %s", (user_id,))['c']
    views = query_one("SELECT COUNT(*) AS c FROM user_views WHERE viewed_id = %s", (user_id,))['c']

    user = get_user_by_id(user_id)
    tags = get_tags_for_user(user_id)
    photos_count = count_photos(user_id)

    bonus = 0
    if user['biography']:
        bonus += 2
    if user['gender'] and user['sexual_preferences']:
        bonus += 2
    if photos_count > 0:
        bonus += 3
    if tags:
        bonus += 1

    rating = round((likes * 3) + (views * 0.5) + bonus, 2)
    execute("UPDATE users SET fame_rating = %s WHERE id = %s", (rating, user_id))
    return rating


def is_profile_complete(user, tags, photos_count):
    return bool(
        user['gender']
        and user['sexual_preferences']
        and user['biography']
        and tags
        and photos_count > 0
        and ((user['latitude'] is not None and user['longitude'] is not None) or user['location_name'])
    )


# --------------------------------------------------------------- serializers

def photo_to_dict(photo):
    return {
        'id': photo['id'],
        'url': f"/uploads/{photo['filename']}",
        'isPrimary': photo['is_primary'],
        'position': photo['position'],
    }


def user_to_dict(user, include_private=False):
    tags = get_tags_for_user(user['id'])
    photos = get_photos_for_user(user['id'])
    primary = get_primary_photo(user['id'])

    data = {
        'id': user['id'],
        'username': user['username'],
        'firstName': user['first_name'],
        'lastName': user['last_name'],
        'gender': user['gender'],
        'sexualPreferences': user['sexual_preferences'],
        'biography': user['biography'],
        'profilePicture': f"/uploads/{primary['filename']}" if primary else None,
        'photos': [photo_to_dict(p) for p in photos],
        'fameRating': user['fame_rating'],
        'tags': [t['name'] for t in tags],
        'isOnline': user['is_online'],
        'lastActivity': to_iso_utc(user['last_activity']),
        'location': (
            {'name': user['location_name'], 'latitude': user['latitude'], 'longitude': user['longitude']}
            if user['latitude'] and user['longitude']
            else ({'name': user['location_name'], 'latitude': None, 'longitude': None}
                  if user['location_name'] else None)
        ),
        'isProfileComplete': is_profile_complete(user, tags, len(photos)),
    }

    if include_private:
        data['email'] = user['email']
        data['isVerified'] = user['is_verified']
        data['gpsConsent'] = user['gps_consent']

    return data


# ------------------------------------------------------------------ messages

def create_message(sender_id, receiver_id, content):
    return execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s) RETURNING *",
        (sender_id, receiver_id, content),
        returning=True,
    )


def get_conversation(user_a_id, user_b_id):
    return query_all(
        """
        SELECT * FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY created_at
        """,
        (user_a_id, user_b_id, user_b_id, user_a_id),
    )


def message_to_dict(message):
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
    return execute(
        """
        INSERT INTO reports (reporter_id, reported_user_id, reason)
        VALUES (%s, %s, %s)
        RETURNING *
        """,
        (reporter_id, reported_user_id, reason),
        returning=True,
    )


def has_reported(reporter_id, reported_user_id):
    return query_one(
        "SELECT 1 FROM reports WHERE reporter_id = %s AND reported_user_id = %s",
        (reporter_id, reported_user_id),
    ) is not None


# --------------------------------------------------------------- notifications

def create_notification(user_id, type_, from_user_id=None, content=None):
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
    return query_all(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
        (user_id, limit),
    )


def count_unread_notifications(user_id):
    row = query_one(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = %s AND is_read = false",
        (user_id,),
    )
    return row['c'] if row else 0


def mark_notification_read(notification_id, user_id):
    execute(
        "UPDATE notifications SET is_read = true WHERE id = %s AND user_id = %s",
        (notification_id, user_id),
    )


def mark_all_notifications_read(user_id):
    execute(
        "UPDATE notifications SET is_read = true WHERE user_id = %s AND is_read = false",
        (user_id,),
    )
    
# --------------------------------------------------------------- authentication 42 google

def get_user_by_oauth(provider, oauth_id):
    return query_one(
        "SELECT * FROM users WHERE oauth_provider = %s AND oauth_id = %s",
        (provider, oauth_id),
    )


def create_oauth_user(username, email, first_name, last_name, provider, oauth_id):
    return execute(
        """
        INSERT INTO users (username, email, first_name, last_name,
                            oauth_provider, oauth_id, is_verified)
        VALUES (%s, %s, %s, %s, %s, %s, true)
        RETURNING *
        """,
        (username, email, first_name, last_name, provider, oauth_id),
        returning=True,
    )


def link_oauth_to_user(user_id, provider, oauth_id):
    execute(
        "UPDATE users SET oauth_provider = %s, oauth_id = %s, is_verified = true WHERE id = %s",
        (provider, oauth_id, user_id),
    )


def generate_unique_username(base):
    base = base.lower().replace(' ', '_')[:20] or 'user'
    candidate = base
    n = 0
    while get_user_by_username(candidate):
        n += 1
        candidate = f"{base}{n}"
    return candidate