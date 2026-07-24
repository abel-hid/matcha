from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from app import models
from app.utils import validate_email, save_image, geocode_location, send_verification_email

profile_bp = Blueprint('profile', __name__, url_prefix='/api/profile')


def get_current_user_or_404():
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return models.get_user_by_id(int(user_id))


@profile_bp.route('', methods=['GET'])
@jwt_required()
def get_profile():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'user': models.user_to_dict(user, include_private=True)}), 200


@profile_bp.route('', methods=['PUT'])
@jwt_required()
def update_profile():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json() or {}
    updates = {}
    email_changed = False

    if 'firstName' in data:
        if not data['firstName']:
            return jsonify({'message': 'First name cannot be empty'}), 400
        updates['first_name'] = data['firstName']

    if 'lastName' in data:
        if not data['lastName']:
            return jsonify({'message': 'Last name cannot be empty'}), 400
        updates['last_name'] = data['lastName']

    if 'email' in data:
        new_email = data['email']
        if not validate_email(new_email):
            return jsonify({'message': 'Invalid email address'}), 400
        existing = models.get_user_by_email(new_email)
        if existing and existing['id'] != user['id']:
            return jsonify({'message': 'Email already in use'}), 400
        if new_email != user['email']:
            updates['email'] = new_email
            updates['is_verified'] = False
            email_changed = True

    if 'gender' in data:
        updates['gender'] = data['gender']

    if 'sexualPreferences' in data:
        updates['sexual_preferences'] = data['sexualPreferences']

    if 'biography' in data:
        updates['biography'] = data['biography']

    if updates:
        models.update_user_fields(user['id'], updates)

    updated_user = models.get_user_by_id(user['id'])

    if email_changed:
        try:
            send_verification_email(updated_user)
        except Exception as e:
            print(f"[update_profile] failed to send verification email: {e}")

    return jsonify({
        'message': 'Profile updated',
        'user': models.user_to_dict(updated_user, include_private=True),
        'emailChanged': email_changed,
    }), 200


@profile_bp.route('/tags', methods=['GET'])
@jwt_required()
def list_tags():
    tags = models.get_all_tags()
    return jsonify({'tags': [{'id': t['id'], 'name': t['name']} for t in tags]}), 200


@profile_bp.route('/tags', methods=['PUT'])
@jwt_required()
def set_my_tags():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json() or {}
    raw_names = data.get('tags')
    if raw_names is None or not isinstance(raw_names, list):
        return jsonify({'message': 'tags must be a list of strings'}), 400

    normalized = []
    for name in raw_names:
        if not isinstance(name, str):
            continue
        clean = name.strip().lstrip('#').lower()
        if clean and clean not in normalized:
            normalized.append(clean)

    if len(normalized) > 20:
        return jsonify({'message': 'A maximum of 20 tags is allowed'}), 400

    tags = models.set_user_tags(user['id'], normalized)
    return jsonify({'tags': [t['name'] for t in tags]}), 200


@profile_bp.route('/photos', methods=['POST'])
@jwt_required()
def upload_photo():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if models.count_photos(user['id']) >= models.MAX_PHOTOS_PER_USER:
        return jsonify({'message': f'You can have at most {models.MAX_PHOTOS_PER_USER} photos'}), 400

    if 'photo' not in request.files:
        return jsonify({'message': 'No photo file provided'}), 400

    file = request.files['photo']
    if not file or file.filename == '':
        return jsonify({'message': 'No photo file provided'}), 400

    filepath = save_image(file)
    if not filepath:
        return jsonify({'message': 'Invalid or unsupported image file'}), 400

    filename = filepath.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    photo = models.add_photo(user['id'], filename)
    photos = models.get_photos_for_user(user['id'])

    return jsonify({
        'photo': models.photo_to_dict(photo),
        'photos': [models.photo_to_dict(p) for p in photos],
    }), 201


@profile_bp.route('/photos/<int:photo_id>', methods=['DELETE'])
@jwt_required()
def delete_photo(photo_id):
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    photo = models.get_photo(photo_id, user['id'])
    if not photo:
        return jsonify({'message': 'Photo not found'}), 404

    was_primary = photo['is_primary']
    models.delete_photo(photo_id, user['id'])
    if was_primary:
        models.promote_next_photo_to_primary(user['id'])

    photos = models.get_photos_for_user(user['id'])
    return jsonify({'photos': [models.photo_to_dict(p) for p in photos]}), 200


@profile_bp.route('/photos/<int:photo_id>/primary', methods=['PUT'])
@jwt_required()
def set_primary_photo(photo_id):
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    photo = models.get_photo(photo_id, user['id'])
    if not photo:
        return jsonify({'message': 'Photo not found'}), 404

    models.set_primary_photo(photo_id, user['id'])
    photos = models.get_photos_for_user(user['id'])
    return jsonify({'photos': [models.photo_to_dict(p) for p in photos]}), 200


@profile_bp.route('/location', methods=['PUT'])
@jwt_required()
def update_location():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json() or {}
    gps_consent = data.get('gpsConsent')

    if gps_consent is None:
        return jsonify({'message': 'gpsConsent is required (true or false)'}), 400

    updates = {
        'gps_consent': bool(gps_consent),
        'location_updated_at': datetime.utcnow(),
    }

    if updates['gps_consent']:
        lat, lon = data.get('latitude'), data.get('longitude')
        if lat is None or lon is None:
            return jsonify({'message': 'latitude and longitude are required when gpsConsent is true'}), 400
        try:
            updates['latitude'] = float(lat)
            updates['longitude'] = float(lon)
        except (TypeError, ValueError):
            return jsonify({'message': 'latitude and longitude must be numbers'}), 400
        if data.get('locationName'):
            updates['location_name'] = data['locationName']
    else:
        location_name = data.get('locationName')
        if not location_name:
            return jsonify({'message': 'locationName is required when gpsConsent is false'}), 400
        lat, lon = geocode_location(location_name)
        updates['location_name'] = location_name
        updates['latitude'] = lat
        updates['longitude'] = lon

    models.update_user_fields(user['id'], updates)
    updated = models.get_user_by_id(user['id'])

    return jsonify({
        'location': {
            'name': updated['location_name'],
            'latitude': updated['latitude'],
            'longitude': updated['longitude'],
        },
        'gpsConsent': updated['gps_consent'],
    }), 200


@profile_bp.route('/viewers', methods=['GET'])
@jwt_required()
def get_viewers():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    viewers = models.get_viewers(user['id'])
    return jsonify({'viewers': [models.user_to_dict(v) for v in viewers]}), 200


@profile_bp.route('/likes', methods=['GET'])
@jwt_required()
def get_likes():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    likers = models.get_likers(user['id'])
    return jsonify({'likes': [models.user_to_dict(l) for l in likers]}), 200