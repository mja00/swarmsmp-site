from datetime import datetime
from datetime import timedelta

import humanize
import uuid as uuid_lib
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import current_user

from ..decorators import minecraft_authenticated
from ..models import User, Application
from ..extensions import cache

user_bp = Blueprint('user', __name__)


# The order of searching here is:
# 1. The user's Minecraft UUID
# 2. The user's Minecraft username
# 3. The user's portal username
@user_bp.route('/<uuid>')
def get_user(uuid):
    if uuid == "null":
        flash('This user has not linked a Minecraft account.', 'warning')
        return redirect(url_for('index'))

    # Check if the uuid is a valid UUID
    try:
        uuid_lib.UUID(uuid)
        user = User.query.filter_by(minecraft_uuid=uuid).first()
    except ValueError:
        # Wasn't a valid UUID check by minecraft username
        user = User.query.filter_by(minecraft_username=uuid).first()
        if user is None:
            # Not a valid minecraft username, check by portal username
            user = User.query.filter_by(username=uuid).first()

    if user is None:
        flash('User not found. It must be a valid UUID, Minecraft username, or portal username.', 'danger')
        return redirect(url_for('index'))
    # Get their most recent application
    application = Application.query.filter_by(user_id=user.id).order_by(Application.id.desc()).first()
    if application:
        now = datetime.utcnow()
        # TODO: Make the timedelta configurable
        time_till_next_application = humanize.naturaltime(now - (application.created_at + timedelta(days=7)))
    else:
        time_till_next_application = None
    if user.has_character():
        latest_character = user.get_most_recent_character()
    else:
        latest_character = None
    return render_template(
        'user_pages/view_user.html',
        user=user,
        latest_application=application,
        time_till=time_till_next_application,
        latest_character=latest_character
    )


@user_bp.route('/whitelisted')
@cache.cached(timeout=600)
def whitelisted_users():
    users = User.query.filter_by(is_whitelisted=True).all()
    return render_template('user_pages/whitelisted_users.html', users=users)


@user_bp.route('/profile')
@minecraft_authenticated
def profile():
    uuid = current_user.minecraft_uuid
    return redirect(url_for('user.get_user', uuid=uuid))
