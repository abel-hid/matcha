from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import models
from app.profile_access import complete_profile_required


discover_bp = Blueprint('discover', __name__, url_prefix='/api/discover')

SORT_VALUES = {
    'recommended',
    'age',
    'distance',
    'fame',
    'commonTags',
}
ORDER_VALUES = {'asc', 'desc'}
DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 24
MAP_PAGE_SIZE = 500


def parse_integer_argument(name, default, minimum, maximum):
    raw_value = request.args.get(name)
    if raw_value in (None, ''):
        return default, None

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, f'{name} must be an integer'

    if value < minimum or value > maximum:
        return None, f'{name} must be between {minimum} and {maximum}'

    return value, None


def parse_tag_ids():
    raw_value = request.args.get('tagIds', '').strip()
    if not raw_value:
        return [], None

    raw_ids = raw_value.split(',')
    if len(raw_ids) > 20:
        return None, 'A maximum of 20 tags can be selected'

    tag_ids = []
    for raw_id in raw_ids:
        try:
            tag_id = int(raw_id)
        except (TypeError, ValueError):
            return None, 'tagIds must be a comma-separated list of integers'

        if tag_id <= 0:
            return None, 'tagIds must contain positive integers'

        if tag_id not in tag_ids:
            tag_ids.append(tag_id)

    valid_ids = {tag['id'] for tag in models.get_all_tags()}
    if not set(tag_ids).issubset(valid_ids):
        return None, 'One or more selected tags are invalid'

    return tag_ids, None


def parse_discovery_filters(*, include_pagination):
    min_age, error = parse_integer_argument('minAge', 18, 18, 80)
    if error:
        return None, error

    max_age, error = parse_integer_argument('maxAge', 80, 18, 80)
    if error:
        return None, error
    if min_age > max_age:
        return None, 'minAge cannot be greater than maxAge'

    min_fame, error = parse_integer_argument('minFame', 0, 0, 100)
    if error:
        return None, error

    max_fame, error = parse_integer_argument('maxFame', 100, 0, 100)
    if error:
        return None, error
    if min_fame > max_fame:
        return None, 'minFame cannot be greater than maxFame'

    location = request.args.get('location', '').strip()
    if len(location) > 100:
        return None, 'location must be at most 100 characters long'

    tag_ids, error = parse_tag_ids()
    if error:
        return None, error

    sort = request.args.get('sort', 'recommended')
    if sort not in SORT_VALUES:
        return None, 'Invalid sort value'

    order = request.args.get('order', 'asc').lower()
    if order not in ORDER_VALUES:
        return None, 'order must be asc or desc'

    filters = {
        'min_age': min_age,
        'max_age': max_age,
        'min_fame': min_fame,
        'max_fame': max_fame,
        'location': location,
        'tag_ids': tag_ids,
        'sort': sort,
        'order': order,
    }

    if include_pagination:
        page, error = parse_integer_argument('page', 1, 1, 1000000)
        if error:
            return None, error

        page_size, error = parse_integer_argument(
            'pageSize',
            DEFAULT_PAGE_SIZE,
            1,
            MAX_PAGE_SIZE,
        )
        if error:
            return None, error
        filters.update({'page': page, 'page_size': page_size})
    else:
        filters.update({'page': 1, 'page_size': MAP_PAGE_SIZE})

    return filters, None


def criteria_to_dict(filters):
    return {
        'minAge': filters['min_age'],
        'maxAge': filters['max_age'],
        'minFame': filters['min_fame'],
        'maxFame': filters['max_fame'],
        'location': filters['location'],
        'tagIds': filters['tag_ids'],
        'sort': filters['sort'],
        'order': filters['order'],
    }


@discover_bp.route('', methods=['GET'])
@jwt_required()
@complete_profile_required
def discover_profiles():
    current_user_id = int(get_jwt_identity())
    filters, error = parse_discovery_filters(include_pagination=True)
    if error:
        return jsonify({'message': error}), 400

    result = models.discover_users(current_user_id, filters)
    return jsonify({
        'profiles': [
            models.discovery_user_to_dict(profile)
            for profile in result['profiles']
        ],
        'pagination': {
            'page': filters['page'],
            'pageSize': filters['page_size'],
            'total': result['total'],
            'totalPages': result['total_pages'],
        },
        'criteria': criteria_to_dict(filters),
    }), 200


@discover_bp.route('/map', methods=['GET'])
@jwt_required()
@complete_profile_required
def discover_map():
    current_user_id = int(get_jwt_identity())
    filters, error = parse_discovery_filters(include_pagination=False)
    if error:
        return jsonify({'message': error}), 400

    current_user = models.get_user_by_id(current_user_id)
    if (
        not current_user
        or current_user.get('latitude') is None
        or current_user.get('longitude') is None
    ):
        return jsonify({'message': 'Set a usable location before opening the map'}), 400

    result = models.discover_users(current_user_id, filters)
    return jsonify({
        'currentUserLocation': models.approximate_map_location(current_user),
        'profiles': [
            models.map_user_to_dict(profile)
            for profile in result['profiles']
        ],
        'total': result['total'],
        'truncated': result['total'] > MAP_PAGE_SIZE,
        'criteria': criteria_to_dict(filters),
    }), 200
