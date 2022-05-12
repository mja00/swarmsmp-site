import os
from functools import wraps

from flask import request, redirect, url_for, flash, jsonify
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_elevated():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def whitelist_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_whitelisted:
            flash('You must be whitelisted to visit this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def minecraft_authenticated(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.minecraft_uuid:
            flash('You\'ll need to auth yourself on Minecraft first.', 'danger')
            return redirect(url_for('auth.minecraft_authentication'))
        return f(*args, **kwargs)

    return decorated_function


def discord_authenticated(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.discord_uuid:
            flash('You\'ll need to auth yourself on Discord first.', 'danger')
            return redirect(url_for('auth.discord_authentication'))
        return f(*args, **kwargs)

    return decorated_function


def whitelisted_and_minecraft_authenticated(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_whitelisted:
            flash('You must be whitelisted to visit this page.', 'danger')
            return redirect(url_for('index'))
        if not current_user.minecraft_uuid:
            flash('You\'ll need to auth yourself on Minecraft first.', 'danger')
            return redirect(url_for('auth.minecraft_authentication'))
        return f(*args, **kwargs)

    return decorated_function


def whitelisted_and_fully_authenticated(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You need to be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_whitelisted:
            flash('You must be whitelisted to visit this page.', 'danger')
            return redirect(url_for('index'))
        if not current_user.minecraft_uuid:
            flash('You\'ll need to auth yourself on Minecraft first.', 'danger')
            return redirect(url_for('auth.minecraft_authentication'))
        if not current_user.discord_uuid:
            flash('You\'ll need to auth yourself on Discord first.', 'danger')
            return redirect(url_for('auth.discord_authentication'))
        return f(*args, **kwargs)

    return decorated_function


def fully_authenticated(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You must be logged in to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.minecraft_uuid:
            flash('You\'ll need to auth yourself on Minecraft first.', 'danger')
            return redirect(url_for('auth.minecraft_authentication'))
        if not current_user.discord_uuid:
            flash('You\'ll need to auth yourself on Discord first.', 'danger')
            return redirect(url_for('auth.discord_authentication'))
        return f(*args, **kwargs)

    return decorated_function


def auth_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the Authorization header from the request
        auth_header = request.headers.get('Authorization')
        if current_user.is_authenticated and current_user.is_admin:
            return f(*args, **kwargs)
        if not auth_header:
            return jsonify({'message': 'Authorization header is missing.'}), 401
        if not os.getenv('AUTH_KEY'):
            return jsonify({'message': 'AUTH_KEY is not set.'}), 401
        auth_key = os.getenv('AUTH_KEY')
        if auth_key != auth_header:
            return jsonify({'message': 'Invalid authorization key.'}), 401
        return f(*args, **kwargs)

    return decorated_function
