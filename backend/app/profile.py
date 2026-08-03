"""Private profile editing, tags, photos, location, and activity routes."""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from app import models
from app.request_helpers import get_authenticated_user, json_object
from app.profile_access import complete_profile_required
from app.utils import (
    LocationServiceError,
    delete_saved_image,
    reverse_geocode_location,
    search_locations,
    save_image,
    send_verification_email,
)
from app.validation import (
    normalize_email,
    validate_biography,
    validate_birth_date,
    validate_coordinate,
    validate_gender,
    validate_location_name,
    validate_name,
    validate_sexual_preferences,
)

profile_bp = Blueprint('profile', __name__, url_prefix='/api/profile')


def private_user_response(user_id):
    """Return a private profile response with provider-link metadata."""
    user = models.get_user_by_id(user_id)
    return models.user_to_dict(user, include_private=True)


@profile_bp.route('', methods=['GET'])
@jwt_required()
def get_profile():
    """Return the authenticated user’s private editable profile."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'user': models.user_to_dict(user, include_private=True)}), 200


@profile_bp.route('', methods=['PUT'])
@jwt_required()
def update_profile():
    """Validate and update editable identity and profile fields."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = json_object()
    if data is None:
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    updates = {}
    email_changed = False

    if 'firstName' in data:
        first_name, error = validate_name(data['firstName'], 'First name')
        if error:
            return jsonify({'message': error}), 400
        updates['first_name'] = first_name

    if 'lastName' in data:
        last_name, error = validate_name(data['lastName'], 'Last name')
        if error:
            return jsonify({'message': error}), 400
        updates['last_name'] = last_name

    if 'email' in data:
        new_email, error = normalize_email(data['email'])
        if error:
            return jsonify({'message': error}), 400
        existing = models.get_user_by_email(new_email)
        if existing and existing['id'] != user['id']:
            return jsonify({'message': 'Email already in use'}), 409
        if new_email != user['email']:
            updates['email'] = new_email
            updates['is_verified'] = False
            email_changed = True

    if 'birthDate' in data:
        birth_date, error = validate_birth_date(data['birthDate'], required=True)
        if error:
            return jsonify({'message': error}), 400
        updates['birth_date'] = birth_date

    if 'gender' in data:
        gender, error = validate_gender(data['gender'], required=True)
        if error:
            return jsonify({'message': error}), 400
        updates['gender'] = gender

    if 'sexualPreferences' in data:
        preferences, error = validate_sexual_preferences(data['sexualPreferences'])
        if error:
            return jsonify({'message': error}), 400
        updates['sexual_preferences'] = preferences

    if 'biography' in data:
        biography, error = validate_biography(data['biography'], required=True)
        if error:
            return jsonify({'message': error}), 400
        updates['biography'] = biography

    if email_changed:
        verification_user = dict(user)
        verification_user.update(updates)
        try:
            send_verification_email(verification_user)
        except Exception:
            current_app.logger.exception('Failed to send email-change verification email')
            return jsonify({
                'message': 'Email could not be changed because the verification email failed'
            }), 503

    if updates:
        models.update_user_fields(user['id'], updates)

    fame_fields = {
        'birth_date',
        'gender',
        'sexual_preferences',
        'biography',
    }
    if fame_fields.intersection(updates):
        models.update_fame_rating(user['id'])

    return jsonify({
        'message': 'Profile updated',
        'user': private_user_response(user['id']),
        'emailChanged': email_changed,
    }), 200


@profile_bp.route('/tags', methods=['GET'])
@jwt_required()
def list_tags():
    """Return the fixed reusable interest catalogue."""
    tags = models.get_all_tags()
    return jsonify({'tags': [{'id': tag['id'], 'name': tag['name']} for tag in tags]}), 200


@profile_bp.route('/tags', methods=['PUT'])
@jwt_required()
def set_my_tags():
    """Replace the authenticated user's selected interests."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = json_object()
    if data is None:
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    tag_ids = data.get('tagIds')
    if not isinstance(tag_ids, list):
        return jsonify({'message': 'tagIds must be a list of integers'}), 400
    if len(tag_ids) == 0:
        return jsonify({'message': 'Select at least one interest'}), 400
    if len(tag_ids) > 20:
        return jsonify({'message': 'A maximum of 20 tags is allowed'}), 400
    if any(isinstance(tag_id, bool) or not isinstance(tag_id, int) for tag_id in tag_ids):
        return jsonify({'message': 'tagIds must be a list of integers'}), 400

    try:
        tags = models.set_user_tags(user['id'], tag_ids)
    except models.InvalidTagIdsError as error:
        return jsonify({'message': str(error)}), 400

    models.update_fame_rating(user['id'])
    return jsonify({
        'tags': [tag['name'] for tag in tags],
        'user': private_user_response(user['id']),
    }), 200


@profile_bp.route('/photos', methods=['POST'])
@jwt_required()
def upload_photo():
    """Validate, re-encode, save, and register a new profile image."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if 'photo' not in request.files:
        return jsonify({'message': 'No photo file provided'}), 400

    file = request.files['photo']
    if not file or file.filename == '':
        return jsonify({'message': 'No photo file provided'}), 400

    filename = save_image(file)
    if not filename:
        return jsonify({'message': 'Upload a valid PNG or JPEG image'}), 400

    try:
        photo = models.add_photo(user['id'], filename)
    except models.PhotoLimitError as error:
        delete_saved_image(filename)
        return jsonify({'message': str(error)}), 400
    except Exception:
        delete_saved_image(filename)
        raise

    models.update_fame_rating(user['id'])
    updated_user = private_user_response(user['id'])

    return jsonify({
        'photo': models.photo_to_dict(photo),
        'photos': updated_user['photos'],
        'user': updated_user,
    }), 201


@profile_bp.route('/photos/<int:photo_id>', methods=['PUT'])
@jwt_required()
def replace_photo(photo_id):
    """Validate and replace an owned profile image without changing its identity."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if 'photo' not in request.files:
        return jsonify({'message': 'No photo file provided'}), 400

    file = request.files['photo']
    if not file or file.filename == '':
        return jsonify({'message': 'No photo file provided'}), 400

    filename = save_image(file)
    if not filename:
        return jsonify({'message': 'Upload a valid PNG or JPEG image'}), 400

    try:
        photo = models.replace_photo_filename(user['id'], photo_id, filename)
    except Exception:
        delete_saved_image(filename)
        raise

    if not photo:
        delete_saved_image(filename)
        return jsonify({'message': 'Photo not found'}), 404

    previous_filename = photo.pop('previous_filename', None)
    if previous_filename and not delete_saved_image(previous_filename):
        current_app.logger.error(
            'Failed to delete replaced upload file %s',
            previous_filename,
        )

    models.update_fame_rating(user['id'])
    updated_user = private_user_response(user['id'])
    return jsonify({
        'photo': models.photo_to_dict(photo),
        'photos': updated_user['photos'],
        'user': updated_user,
    }), 200


@profile_bp.route('/photos/<int:photo_id>', methods=['DELETE'])
@jwt_required()
def delete_photo(photo_id):
    """Delete an owned photo while preserving mandatory profile requirements."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    try:
        photo = models.delete_photo_and_promote(user['id'], photo_id)
    except models.LastPhotoError as error:
        return jsonify({'message': str(error)}), 400
    if not photo:
        return jsonify({'message': 'Photo not found'}), 404

    if not delete_saved_image(photo['filename']):
        current_app.logger.error('Failed to delete upload file %s', photo['filename'])

    models.update_fame_rating(user['id'])
    updated_user = private_user_response(user['id'])

    return jsonify({
        'photos': updated_user['photos'],
        'user': updated_user,
    }), 200


@profile_bp.route('/photos/<int:photo_id>/primary', methods=['PUT'])
@jwt_required()
def set_primary_photo(photo_id):
    """Set an owned image as the single primary profile photo."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if not models.set_primary_photo(photo_id, user['id']):
        return jsonify({'message': 'Photo not found'}), 404

    updated_user = private_user_response(user['id'])
    return jsonify({
        'photos': updated_user['photos'],
        'user': updated_user,
    }), 200


@profile_bp.route('/location/search', methods=['GET'])
@jwt_required()
def search_location():
    """Search the configured geocoder for manual location choices."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    location_name, error = validate_location_name(request.args.get('q'), required=True)
    if error:
        return jsonify({'message': error}), 400

    try:
        results = search_locations(location_name)
    except LocationServiceError:
        return jsonify({
            'message': 'Location search is temporarily unavailable. Try again shortly.'
        }), 503

    return jsonify({'results': results}), 200


@profile_bp.route('/location', methods=['PUT'])
@jwt_required()
def update_location():
    """Save GPS or manual location with explicit consent and coordinate validation."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = json_object()
    if data is None:
        return jsonify({'message': 'Request body must be a JSON object'}), 400

    gps_consent = data.get('gpsConsent')
    if not isinstance(gps_consent, bool):
        return jsonify({'message': 'gpsConsent must be true or false'}), 400

    updates = {
        'gps_consent': gps_consent,
        'location_updated_at': datetime.utcnow(),
    }

    latitude, error = validate_coordinate(data.get('latitude'), 'latitude', -90, 90)
    if error:
        return jsonify({'message': error}), 400
    longitude, error = validate_coordinate(data.get('longitude'), 'longitude', -180, 180)
    if error:
        return jsonify({'message': error}), 400

    if gps_consent:
        try:
            location_name = reverse_geocode_location(latitude, longitude)
        except LocationServiceError:
            location_name = None

        updates['location_name'] = location_name or 'Approximate GPS location'
    else:
        location_name, error = validate_location_name(data.get('locationName'), required=True)
        if error:
            return jsonify({'message': error}), 400
        updates['location_name'] = location_name

    updates['latitude'] = latitude
    updates['longitude'] = longitude

    models.update_user_fields(user['id'], updates)
    models.update_fame_rating(user['id'])
    updated_user = private_user_response(user['id'])

    return jsonify({
        'location': updated_user['location'],
        'gpsConsent': updated_user['gpsConsent'],
        'user': updated_user,
    }), 200


@profile_bp.route('/viewers', methods=['GET'])
@jwt_required()
@complete_profile_required
def get_viewers():
    """Return profile visit history visible to the account owner."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    viewers = models.get_viewers(user['id'])
    return jsonify({
        'viewers': [models.view_to_dict(viewer) for viewer in viewers]
    }), 200


@profile_bp.route('/likes', methods=['GET'])
@jwt_required()
@complete_profile_required
def get_likes():
    """Return incoming, outgoing, and mutual-like activity."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    likers = models.get_likers(user['id'])
    return jsonify({
        'likes': [models.like_to_dict(liker) for liker in likers]
    }), 200


@profile_bp.route('/activity', methods=['GET'])
@jwt_required()
@complete_profile_required
def get_activity():
    """Return categorized views, likes, and matches for the activity page."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    visits = models.get_viewers(user['id'])
    liked_by_me = models.get_outgoing_pending_likes(user['id'])
    liked_me = models.get_incoming_pending_likes(user['id'])
    matches = models.get_matches(user['id'])

    return jsonify({
        'visits': [models.view_to_dict(visit) for visit in visits],
        'likedByMe': [models.like_to_dict(like) for like in liked_by_me],
        'likedMe': [models.like_to_dict(like) for like in liked_me],
        'matches': [models.match_to_dict(match) for match in matches],
    }), 200
