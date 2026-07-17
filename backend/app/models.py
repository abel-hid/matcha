from datetime import datetime
from app.extensions import db
import bcrypt


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optional profile fields (you can expand later)
    gender = db.Column(db.String(20))
    sexual_preferences = db.Column(db.String(20))
    biography = db.Column(db.Text)
    profile_picture = db.Column(db.String(255))
    fame_rating = db.Column(db.Float, default=0)
    
    # reset password token version for invalidating old tokens
    token_version = db.Column(db.Integer, default=0, nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def to_dict(self, include_private=False):
        data = {
            'id': self.id,
            'username': self.username,
            'firstName': self.first_name,
            'lastName': self.last_name,
            'gender': self.gender,
            'sexualPreferences': self.sexual_preferences,
            'biography': self.biography,
            'profilePicture': self.profile_picture,
            'fameRating': self.fame_rating,
        }
        if include_private:
            data['email'] = self.email
            data['isVerified'] = self.is_verified
        return data