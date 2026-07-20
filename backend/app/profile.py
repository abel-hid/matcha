from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from app.models import User, Tag, Photo, MAX_PHOTOS_PER_USER
from app.extensions import db
from app.utils import validate_email, save_image, geocode_location

profile_bp = Blueprint('profile', __name__, url_prefix='/api/profile')


def get_current_user_or_404():
    """Helper: resolve the JWT identity (always a string) back to a User row."""
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return User.query.get(int(user_id))



@profile_bp.route('', methods=['GET'])
@jwt_required()
def get_profile():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'user': user.to_dict(include_private=True)}), 200


@profile_bp.route('', methods=['PUT'])
@jwt_required()
def update_profile():
    """
    Update gender, sexual preferences, biography, first/last name, and email.
    Tags, photos, and location each have their own dedicated endpoints below —
    they involve different validation (uniqueness, file handling, geocoding)
    and keeping them separate avoids one giant do-everything route.
    """
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json() or {}

    if 'firstName' in data:
        if not data['firstName']:
            return jsonify({'message': 'First name cannot be empty'}), 400
        user.first_name = data['firstName']

    if 'lastName' in data:
        if not data['lastName']:
            return jsonify({'message': 'Last name cannot be empty'}), 400
        user.last_name = data['lastName']

    if 'email' in data:
        new_email = data['email']
        if not validate_email(new_email):
            return jsonify({'message': 'Invalid email address'}), 400
        existing = User.query.filter_by(email=new_email).first()
        if existing and existing.id != user.id:
            return jsonify({'message': 'Email already in use'}), 400
        if new_email != user.email:
            user.email = new_email
            user.is_verified = False
    if 'gender' in data:
        user.gender = data['gender']

    if 'sexualPreferences' in data:
        user.sexual_preferences = data['sexualPreferences']

    if 'biography' in data:
        user.biography = data['biography']

    db.session.commit()

    return jsonify({'message': 'Profile updated', 'user': user.to_dict(include_private=True)}), 200


@profile_bp.route('/tags', methods=['GET'])
@jwt_required()
def list_tags():
    """All tags in the system, for autocomplete when a user is adding interests."""
    tags = Tag.query.order_by(Tag.name).all()
    return jsonify({'tags': [t.to_dict() for t in tags]}), 200


@profile_bp.route('/tags', methods=['PUT'])
@jwt_required()
def set_my_tags():
    """
    Replace the current user's tag list. Accepts {"tags": ["vegan", "geek", ...]}.
    Tag names are normalized (lowercased, trimmed, leading '#' stripped) so
    "#Vegan" and "vegan" resolve to the same reusable Tag row instead of
    silently creating duplicates.
    """
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

    tag_objects = []
    for name in normalized:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()  # get an id without a full commit yet
        tag_objects.append(tag)

    user.tags = tag_objects
    db.session.commit()

    return jsonify({'tags': [t.name for t in user.tags]}), 200



@profile_bp.route('/photos', methods=['POST'])
@jwt_required()
def upload_photo():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if user.photos.count() >= MAX_PHOTOS_PER_USER:
        return jsonify({'message': f'You can have at most {MAX_PHOTOS_PER_USER} photos'}), 400

    if 'photo' not in request.files:
        return jsonify({'message': 'No photo file provided'}), 400

    file = request.files['photo']
    if not file or file.filename == '':
        return jsonify({'message': 'No photo file provided'}), 400

    filepath = save_image(file)
    if not filepath:
        return jsonify({'message': 'Invalid or unsupported image file'}), 400

    filename = filepath.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]  # basename, OS-agnostic
    is_first_photo = user.photos.count() == 0

    photo = Photo(
        user_id=user.id,
        filename=filename,
        is_primary=is_first_photo,  # first photo you ever upload becomes primary automatically
        position=user.photos.count()
    )
    db.session.add(photo)
    db.session.commit()

    return jsonify({'photo': photo.to_dict(), 'photos': [p.to_dict() for p in user.photos]}), 201


@profile_bp.route('/photos/<int:photo_id>', methods=['DELETE'])
@jwt_required()
def delete_photo(photo_id):
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    photo = Photo.query.filter_by(id=photo_id, user_id=user.id).first()
    if not photo:
        return jsonify({'message': 'Photo not found'}), 404

    was_primary = photo.is_primary
    db.session.delete(photo)
    db.session.flush()
    if was_primary:
        next_photo = user.photos.order_by(Photo.position).first()
        if next_photo:
            next_photo.is_primary = True

    db.session.commit()

    return jsonify({'photos': [p.to_dict() for p in user.photos]}), 200


@profile_bp.route('/photos/<int:photo_id>/primary', methods=['PUT'])
@jwt_required()
def set_primary_photo(photo_id):
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    photo = Photo.query.filter_by(id=photo_id, user_id=user.id).first()
    if not photo:
        return jsonify({'message': 'Photo not found'}), 404

    for p in user.photos:
        p.is_primary = (p.id == photo.id)

    db.session.commit()

    return jsonify({'photos': [p.to_dict() for p in user.photos]}), 200



@profile_bp.route('/location', methods=['PUT'])
@jwt_required()
def update_location():
    """
    Two modes, both requiring an explicit choice from the client:
      - GPS:    {"gpsConsent": true, "latitude": ..., "longitude": ...}
      - Manual: {"gpsConsent": false, "locationName": "Casablanca, Morocco"}
    gpsConsent is stored so the app can honor "opted out" on future visits
    instead of re-prompting or silently falling back.
    """
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json() or {}
    gps_consent = data.get('gpsConsent')

    if gps_consent is None:
        return jsonify({'message': 'gpsConsent is required (true or false)'}), 400

    user.gps_consent = bool(gps_consent)

    if user.gps_consent:
        lat, lon = data.get('latitude'), data.get('longitude')
        if lat is None or lon is None:
            return jsonify({'message': 'latitude and longitude are required when gpsConsent is true'}), 400
        user.latitude = float(lat)
        user.longitude = float(lon)
        if data.get('locationName'):
            user.location_name = data['locationName']
    else:
        location_name = data.get('locationName')
        if not location_name:
            return jsonify({'message': 'locationName is required when gpsConsent is false'}), 400
        lat, lon = geocode_location(location_name)
        user.location_name = location_name
        user.latitude = lat
        user.longitude = lon

    user.location_updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'location': {
            'name': user.location_name,
            'latitude': user.latitude,
            'longitude': user.longitude,
        },
        'gpsConsent': user.gps_consent,
    }), 200


@profile_bp.route('/viewers', methods=['GET'])
@jwt_required()
def get_viewers():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    viewers = user.viewed_by.order_by(User.username).all()
    return jsonify({'viewers': [v.to_dict() for v in viewers]}), 200


@profile_bp.route('/likes', methods=['GET'])
@jwt_required()
def get_likes():
    user = get_current_user_or_404()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    likers = user.liked_by.order_by(User.username).all()
    return jsonify({'likes': [l.to_dict() for l in likers]}), 200