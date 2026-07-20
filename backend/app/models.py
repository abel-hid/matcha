from datetime import datetime
from flask_jwt_extended import create_access_token, create_refresh_token
import bcrypt
from app.extensions import db

MAX_PHOTOS_PER_USER = 5

# Association table for many-to-many relationships
user_tags = db.Table('user_tags',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

user_likes = db.Table('user_likes',
    db.Column('liker_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('liked_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

user_blocks = db.Table('user_blocks',
    db.Column('blocker_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('blocked_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

user_views = db.Table('user_views',
    db.Column('viewer_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('viewed_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('viewed_at', db.DateTime, default=datetime.utcnow)
)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)

    # Profile fields
    gender = db.Column(db.String(20))
    sexual_preferences = db.Column(db.String(20))
    biography = db.Column(db.Text)
    profile_picture = db.Column(db.String(255))  # denormalized: kept in sync with the primary Photo's filename
    fame_rating = db.Column(db.Float, default=0)

    # Location
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    location_name = db.Column(db.String(100))
    location_updated_at = db.Column(db.DateTime)
    # True once the user has explicitly agreed to GPS-based location tracking.
    # If False, location must come from manual entry (location_name / geocoded lat-lng).
    gps_consent = db.Column(db.Boolean, default=False, nullable=False)

    # Status
    is_verified = db.Column(db.Boolean, default=False)
    is_online = db.Column(db.Boolean, default=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    token_version = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    tags = db.relationship('Tag', secondary=user_tags, lazy='subquery',
                          backref=db.backref('users', lazy=True))

    photos = db.relationship('Photo', backref='user', lazy='dynamic',
                             cascade='all, delete-orphan',
                             order_by='Photo.position')

    # Self-referential relationships
    liked_by = db.relationship('User', secondary=user_likes,
                               primaryjoin=(user_likes.c.liked_id == id),
                               secondaryjoin=(user_likes.c.liker_id == id),
                               lazy='dynamic')

    liked_users = db.relationship('User', secondary=user_likes,
                                  primaryjoin=(user_likes.c.liker_id == id),
                                  secondaryjoin=(user_likes.c.liked_id == id),
                                  lazy='dynamic')

    blocked_by = db.relationship('User', secondary=user_blocks,
                                 primaryjoin=(user_blocks.c.blocked_id == id),
                                 secondaryjoin=(user_blocks.c.blocker_id == id),
                                 lazy='dynamic')

    blocked_users = db.relationship('User', secondary=user_blocks,
                                    primaryjoin=(user_blocks.c.blocker_id == id),
                                    secondaryjoin=(user_blocks.c.blocked_id == id),
                                    lazy='dynamic')

    viewed_by = db.relationship('User', secondary=user_views,
                                primaryjoin=(user_views.c.viewed_id == id),
                                secondaryjoin=(user_views.c.viewer_id == id),
                                lazy='dynamic')

    viewed_users = db.relationship('User', secondary=user_views,
                                   primaryjoin=(user_views.c.viewer_id == id),
                                   secondaryjoin=(user_views.c.viewed_id == id),
                                   lazy='dynamic')

    # Messages
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id',
                                   backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id',
                                       backref='receiver', lazy='dynamic')

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        """Verify password"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def get_access_token(self):
        """Generate JWT access token"""
        return create_access_token(identity=str(self.id))

    def get_refresh_token(self):
        """Generate JWT refresh token"""
        return create_refresh_token(identity=str(self.id))

    def update_fame_rating(self):
        """Calculate and update fame rating based on activity.

        Definition used here: fame_rating = (likes * 3) + (views * 1) + (profile_completeness_bonus)
        - Likes count more than views because they signal active interest, not passive browsing.
        - A small flat bonus rewards having a complete profile (photos, bio, tags), since an
          empty profile shouldn't out-rank an engaged one just from raw traffic.
        Rounded to 2 decimals for display; consistent across the app.
        """
        likes_count = self.liked_by.count()
        views_count = self.viewed_by.count()

        completeness_bonus = 0
        if self.biography:
            completeness_bonus += 2
        if self.gender and self.sexual_preferences:
            completeness_bonus += 2
        if self.photos.count() > 0:
            completeness_bonus += 3
        if self.tags:
            completeness_bonus += 1

        rating = (likes_count * 3) + (views_count * 0.5) + completeness_bonus
        self.fame_rating = round(rating, 2)
        db.session.commit()

    def is_profile_complete(self):
        """True once all Web Matcha-required profile fields are filled in."""
        return bool(
            self.gender
            and self.sexual_preferences
            and self.biography
            and self.tags
            and self.photos.count() > 0
            and (self.latitude is not None and self.longitude is not None or self.location_name)
        )

    def primary_photo(self):
        return self.photos.filter_by(is_primary=True).first()

    def to_dict(self, include_private=False):
        """Convert user to dictionary"""
        primary = self.primary_photo()
        data = {
            'id': self.id,
            'username': self.username,
            'firstName': self.first_name,
            'lastName': self.last_name,
            'gender': self.gender,
            'sexualPreferences': self.sexual_preferences,
            'biography': self.biography,
            'profilePicture': primary.to_dict()['url'] if primary else None,
            'photos': [p.to_dict() for p in self.photos],
            'fameRating': self.fame_rating,
            'tags': [tag.name for tag in self.tags],
            'isOnline': self.is_online,
            'lastActivity': self.last_activity.isoformat() if self.last_activity else None,
            'location': {
                'name': self.location_name,
                'latitude': self.latitude,
                'longitude': self.longitude
            } if self.latitude and self.longitude else (
                {'name': self.location_name, 'latitude': None, 'longitude': None}
                if self.location_name else None
            ),
            'isProfileComplete': self.is_profile_complete(),
        }

        if include_private:
            data['email'] = self.email
            data['isVerified'] = self.is_verified
            data['gpsConsent'] = self.gps_consent

        return data

    def __repr__(self):
        return f'<User {self.username}>'


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'name': self.name}

    def __repr__(self):
        return f'<Tag {self.name}>'


class Photo(db.Model):
    __tablename__ = 'photos'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            # Served by the static upload route registered in app/__init__.py
            'url': f"/uploads/{self.filename}",
            'isPrimary': self.is_primary,
            'position': self.position,
        }

    def __repr__(self):
        return f'<Photo {self.id} user={self.user_id}>'


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'senderId': self.sender_id,
            'receiverId': self.receiver_id,
            'content': self.content,
            'isRead': self.is_read,
            'createdAt': self.created_at.isoformat()
        }

    def __repr__(self):
        return f'<Message {self.id}>'


class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.String(50), default='fake_account', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reporter = db.relationship('User', foreign_keys=[reporter_id])
    reported_user = db.relationship('User', foreign_keys=[reported_user_id])

    __table_args__ = (
        db.UniqueConstraint('reporter_id', 'reported_user_id', name='uq_reporter_reported'),
    )

    def __repr__(self):
        return f'<Report {self.reporter_id} -> {self.reported_user_id}>'


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # like, view, message, match, unlike
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    content = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='notifications')
    from_user = db.relationship('User', foreign_keys=[from_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'content': self.content,
            'isRead': self.is_read,
            'createdAt': self.created_at.isoformat(),
            'fromUser': self.from_user.to_dict() if self.from_user else None
        }

    def __repr__(self):
        return f'<Notification {self.id}>'