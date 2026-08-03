CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL CHECK (length(btrim(username)) > 0),
    email VARCHAR(100) UNIQUE NOT NULL CHECK (length(btrim(email)) > 0),
    password_hash VARCHAR(255),
    first_name VARCHAR(50) NOT NULL CHECK (length(btrim(first_name)) > 0),
    last_name VARCHAR(50) NOT NULL CHECK (length(btrim(last_name)) > 0),

    birth_date DATE CHECK (birth_date IS NULL OR birth_date >= DATE '1900-01-01'),
    gender VARCHAR(20) CHECK (gender IS NULL OR gender IN ('male', 'female', 'non-binary')),
    sexual_preferences TEXT[] NOT NULL DEFAULT ARRAY['male', 'female', 'non-binary']::TEXT[]
        CHECK (
            cardinality(sexual_preferences) BETWEEN 1 AND 3
            AND sexual_preferences <@ ARRAY['male', 'female', 'non-binary']::TEXT[]
        ),
    biography VARCHAR(500),
    fame_rating DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (fame_rating BETWEEN 0 AND 100),

    latitude DOUBLE PRECISION CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    location_name VARCHAR(100) CHECK (
        location_name IS NULL OR length(btrim(location_name)) > 0
    ),
    location_updated_at TIMESTAMP,
    gps_consent BOOLEAN NOT NULL DEFAULT FALSE,

    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_online BOOLEAN NOT NULL DEFAULT FALSE,
    last_activity TIMESTAMP NOT NULL DEFAULT now(),

    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),

    token_version INTEGER NOT NULL DEFAULT 0 CHECK (token_version >= 0),

    CHECK ((latitude IS NULL) = (longitude IS NULL))
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    last_used_at TIMESTAMP NOT NULL DEFAULT now(),
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    CHECK (expires_at > created_at),
    CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);


CREATE TABLE IF NOT EXISTS oauth_identities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL CHECK (provider IN ('42', 'google')),
    provider_user_id VARCHAR(255) NOT NULL
        CHECK (length(btrim(provider_user_id)) > 0),
    provider_email VARCHAR(100) NOT NULL
        CHECK (length(btrim(provider_email)) > 0),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_user_id),
    UNIQUE (user_id, provider)
);

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL CHECK (length(btrim(name)) > 0),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO tags (name)
VALUES
    ('music'),
    ('movies'),
    ('gaming'),
    ('books'),
    ('travel'),
    ('fitness'),
    ('cooking'),
    ('photography'),
    ('art'),
    ('technology'),
    ('nature'),
    ('hiking'),
    ('pets'),
    ('sports'),
    ('dancing'),
    ('fashion'),
    ('coffee'),
    ('vegan'),
    ('anime'),
    ('volunteering')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS user_tags (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, tag_id)
);

CREATE TABLE IF NOT EXISTS photos (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL CHECK (length(btrim(filename)) > 0),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    position INTEGER NOT NULL DEFAULT 0 CHECK (position BETWEEN 0 AND 4),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_likes (
    liker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    liked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (liker_id, liked_id),
    CHECK (liker_id <> liked_id)
);

CREATE TABLE IF NOT EXISTS user_blocks (
    blocker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id <> blocked_id)
);

CREATE TABLE IF NOT EXISTS user_views (
    id SERIAL PRIMARY KEY,
    viewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewed_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    visit_id UUID NOT NULL,
    viewed_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (viewer_id, visit_id),
    CHECK (viewer_id <> viewed_id)
);

CREATE TABLE IF NOT EXISTS notification_suppressions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    suppressed_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, suppressed_user_id),
    CHECK (user_id <> suppressed_user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL CHECK (length(btrim(content)) > 0),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    CHECK (sender_id <> receiver_id)
);

CREATE TABLE IF NOT EXISTS date_events (
    id SERIAL PRIMARY KEY,
    proposer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scheduled_for TIMESTAMPTZ NOT NULL,
    location VARCHAR(150) NOT NULL CHECK (length(btrim(location)) > 0),
    note VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (proposer_id <> recipient_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(50) NOT NULL DEFAULT 'fake_account' CHECK (reason = 'fake_account'),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (reporter_id, reported_user_id),
    CHECK (reporter_id <> reported_user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('like', 'view', 'message', 'match', 'unlike', 'date')),
    from_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content VARCHAR(255),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
    ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_active
    ON auth_sessions(user_id, expires_at)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_oauth_identities_user_id
    ON oauth_identities(user_id);
CREATE INDEX IF NOT EXISTS idx_users_birth_date ON users(birth_date);
CREATE INDEX IF NOT EXISTS idx_users_gender ON users(gender);
CREATE INDEX IF NOT EXISTS idx_users_location ON users(latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_user_tags_tag_id ON user_tags(tag_id);

CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id);
CREATE INDEX IF NOT EXISTS idx_photos_user_position ON photos(user_id, position);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_one_primary_per_user
    ON photos(user_id)
    WHERE is_primary = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_likes_liked_id ON user_likes(liked_id);
CREATE INDEX IF NOT EXISTS idx_user_blocks_blocked_id ON user_blocks(blocked_id);
CREATE INDEX IF NOT EXISTS idx_user_views_viewed_at ON user_views(viewed_id, viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_views_viewer_id ON user_views(viewer_id);
CREATE INDEX IF NOT EXISTS idx_notification_suppressions_suppressed
    ON notification_suppressions(suppressed_user_id);

CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(sender_id, receiver_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_unread_receiver
    ON messages(receiver_id, created_at)
    WHERE is_read = FALSE;

CREATE INDEX IF NOT EXISTS idx_date_events_proposer
    ON date_events(proposer_id, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_date_events_recipient
    ON date_events(recipient_id, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_reports_reported_user ON reports(reported_user_id);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_created
    ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON notifications(user_id, created_at DESC)
    WHERE is_read = FALSE;

ALTER TABLE notifications
    DROP CONSTRAINT IF EXISTS notifications_type_check;
ALTER TABLE notifications
    ADD CONSTRAINT notifications_type_check
    CHECK (type IN ('like', 'view', 'message', 'match', 'unlike', 'date'));
