from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from app import models


def complete_profile_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        user_id = get_jwt_identity()
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({'message': 'User not found'}), 404

        user = models.get_user_by_id(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404

        tags = models.get_tags_for_user(user_id)
        photos = models.get_photos_for_user(user_id)
        missing_fields = models.missing_profile_fields(user, tags, photos)
        if missing_fields:
            return jsonify({
                'message': 'Complete your profile before using Matcha',
                'code': 'PROFILE_INCOMPLETE',
                'missingFields': missing_fields,
            }), 403

        return function(*args, **kwargs)

    return wrapped
