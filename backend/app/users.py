from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from app.models import User, Notification, Report, user_views, user_likes, user_blocks
from app.extensions import db

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


def get_current_user_or_404():
    user_id = get_jwt_identity()
    if user_id is None:
        return None
    return User.query.get(int(user_id))


def is_blocked_either_way(user_a_id, user_b_id):
    """True if either user has blocked the other."""
    return db.session.query(user_blocks).filter(
        db.or_(
            db.and_(user_blocks.c.blocker_id == user_a_id, user_blocks.c.blocked_id == user_b_id),
            db.and_(user_blocks.c.blocker_id == user_b_id, user_blocks.c.blocked_id == user_a_id),
        )
    ).first() is not None


def has_liked(liker_id, liked_id):
    return db.session.query(user_likes).filter_by(liker_id=liker_id, liked_id=liked_id).first() is not None


def create_notification(user_id, type_, from_user_id=None, content=None):
    """
    Persists the notification row. NOTE: this does not push it to the client
    in real time — the spec requires notifications to appear within 10s, which
    means a websocket or short-polling layer on top of this. That's a separate
    piece of work; this just ensures the data exists to be pushed/polled.
    """
    notif = Notification(user_id=user_id, type=type_, from_user_id=from_user_id, content=content)
    db.session.add(notif)


@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_profile(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = User.query.get(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if is_blocked_either_way(current_user.id, target.id):
        return jsonify({'message': 'User not found'}), 404
    if current_user.id != target.id:
        existing_view = db.session.query(user_views).filter_by(
            viewer_id=current_user.id, viewed_id=target.id
        ).first()

        if existing_view:
            db.session.execute(
                user_views.update()
                .where(user_views.c.viewer_id == current_user.id)
                .where(user_views.c.viewed_id == target.id)
                .values(viewed_at=datetime.utcnow())
            )
        else:
            db.session.execute(
                user_views.insert().values(
                    viewer_id=current_user.id, viewed_id=target.id, viewed_at=datetime.utcnow()
                )
            )
            create_notification(target.id, 'view', from_user_id=current_user.id)

        target.update_fame_rating()
        db.session.commit()

    data = target.to_dict(include_private=False)
    data['hasLikedThem'] = has_liked(current_user.id, target.id)
    data['theyLikedMe'] = has_liked(target.id, current_user.id)
    data['isConnected'] = data['hasLikedThem'] and data['theyLikedMe']

    return jsonify({'user': data}), 200


@users_bp.route('/<int:user_id>/like', methods=['POST'])
@jwt_required()
def like_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user.id == user_id:
        return jsonify({'message': 'You cannot like yourself'}), 400

    target = User.query.get(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    if is_blocked_either_way(current_user.id, target.id):
        return jsonify({'message': 'User not found'}), 404

    if not current_user.primary_photo():
        return jsonify({'message': 'Add a profile picture before liking other users'}), 400

    if has_liked(current_user.id, target.id):
        return jsonify({'message': 'Already liked'}), 400

    db.session.execute(
        user_likes.insert().values(
            liker_id=current_user.id, liked_id=target.id, created_at=datetime.utcnow()
        )
    )

    mutual = has_liked(target.id, current_user.id)
    if mutual:
        create_notification(target.id, 'match', from_user_id=current_user.id)
        create_notification(current_user.id, 'match', from_user_id=target.id)
    else:
        create_notification(target.id, 'like', from_user_id=current_user.id)

    target.update_fame_rating()
    db.session.commit()

    return jsonify({'liked': True, 'isConnected': mutual}), 200


@users_bp.route('/<int:user_id>/like', methods=['DELETE'])
@jwt_required()
def unlike_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    target = User.query.get(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    was_connected = has_liked(current_user.id, target.id) and has_liked(target.id, current_user.id)

    db.session.execute(
        user_likes.delete().where(
            db.and_(user_likes.c.liker_id == current_user.id, user_likes.c.liked_id == target.id)
        )
    )

    if was_connected:
        create_notification(target.id, 'unlike', from_user_id=current_user.id)

    target.update_fame_rating()
    db.session.commit()

    return jsonify({'liked': False}), 200


@users_bp.route('/<int:user_id>/block', methods=['POST'])
@jwt_required()
def block_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user.id == user_id:
        return jsonify({'message': 'You cannot block yourself'}), 400

    target = User.query.get(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    already_blocked = db.session.query(user_blocks).filter_by(
        blocker_id=current_user.id, blocked_id=target.id
    ).first()

    if not already_blocked:
        db.session.execute(
            user_blocks.insert().values(
                blocker_id=current_user.id, blocked_id=target.id, created_at=datetime.utcnow()
            )
        )
        db.session.commit()

    return jsonify({'blocked': True}), 200


@users_bp.route('/<int:user_id>/block', methods=['DELETE'])
@jwt_required()
def unblock_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    db.session.execute(
        user_blocks.delete().where(
            db.and_(user_blocks.c.blocker_id == current_user.id, user_blocks.c.blocked_id == user_id)
        )
    )
    db.session.commit()

    return jsonify({'blocked': False}), 200


@users_bp.route('/<int:user_id>/report', methods=['POST'])
@jwt_required()
def report_user(user_id):
    current_user = get_current_user_or_404()
    if not current_user:
        return jsonify({'message': 'User not found'}), 404

    if current_user.id == user_id:
        return jsonify({'message': 'You cannot report yourself'}), 400

    target = User.query.get(user_id)
    if not target:
        return jsonify({'message': 'User not found'}), 404

    existing = Report.query.filter_by(reporter_id=current_user.id, reported_user_id=user_id).first()
    if existing:
        return jsonify({'message': 'You have already reported this user'}), 400

    report = Report(reporter_id=current_user.id, reported_user_id=user_id, reason='fake_account')
    db.session.add(report)
    db.session.commit()

    return jsonify({'message': 'Report submitted'}), 201