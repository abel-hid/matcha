"""Reusable authorization guard for features that require a complete profile."""

from functools import wraps

from flask import jsonify

from app import models
from app.request_helpers import get_authenticated_user


def complete_profile_required(function):
    """Protect a route until the authenticated profile is complete."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        """Reject incomplete profiles before invoking the protected route."""
        user = get_authenticated_user()
        if not user:
            return jsonify({'message': 'User not found'}), 404

        tags = models.get_tags_for_user(user['id'])
        photos = models.get_photos_for_user(user['id'])
        missing_fields = models.missing_profile_fields(user, tags, photos)
        if missing_fields:
            return jsonify({
                'message': 'Complete your profile before using Matcha',
                'code': 'PROFILE_INCOMPLETE',
                'missingFields': missing_fields,
            }), 403

        return function(*args, **kwargs)

    return wrapped
