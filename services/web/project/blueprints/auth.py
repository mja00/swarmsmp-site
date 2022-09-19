import hashlib
import os
from datetime import datetime as dt

import jwt
import requests
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_hcaptcha import hCaptcha
from flask_login import login_required, current_user, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash

from ..decorators import minecraft_authenticated
from ..extensions import cache
from ..logger import log_login
from ..models import User, db, EmailConfirmation, MinecraftAuthentication
from ..settings_helper import get_site_settings
from ..webhooks import new_user, email_confirmed_hook, discord_linked_hook, minecraft_linked_hook

auth_bp = Blueprint('auth', __name__)

MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
hcaptcha = hCaptcha()

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')


def send_registration_email(user, confirmation_token):
    # Get the user's email address
    email = user.email

    # Create a new confirmation object
    try:
        confirmation = EmailConfirmation(user=user, token=confirmation_token, email=email)
        db.session.add(confirmation)
        db.session.commit()
    except SQLAlchemyError:
        return False

    # Check if we're currently in development mode
    if os.environ.get('ENVIRONMENT') == 'development':
        # We'll just simulate the email sending and print out the confirmation link
        print('Confirmation link: ' + url_for('auth.confirm_email', token=confirmation_token, _external=True))
        return True
    else:
        response = requests.post(
            "https://api.mailgun.net/v3/ssmp.theairplan.com/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": "SwarmSMP <noreply@ssmp.theairplan.com>",
                "subject": "Welcome to SwarmSMP!",
                "to": email,
                "template": "confirm-email",
                "h:X-Mailgun-Variables": f'{{"confirmation": "{url_for("auth.confirm_email", token=confirmation_token, _external=True)}"}}'
            }
        )
        return response.status_code == 200


def send_password_reset_email(email, user):
    token = user.get_password_reset_token()
    if os.environ.get('ENVIRONMENT') == 'development':
        print('Password reset link: ' + url_for('auth.reset_password', token=token, _external=True))
        return True
    else:
        response = requests.post(
            "https://api.mailgun.net/v3/ssmp.theairplan.com/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": "SwarmSMP <noreply@ssmp.theairplan.com>",
                "subject": "Reset your password",
                "to": email,
                "template": "reset-password",
                "h:X-Mailgun-Variables": f'{{"reset_password_url": "{url_for("auth.reset_password", token=token, _external=True, _scheme="https")}"}}'
            }
        )
        return response.status_code == 200


def verify_reset_token(token):
    try:
        username = jwt.decode(token, os.environ.get('SECRET_KEY'), algorithms=["HS256"])['reset_password']
    except jwt.exceptions.DecodeError as e:
        print(e)
        return
    return User.query.filter_by(username=username).first()


def generate_confirmation_token(email):
    # Hash the current time and email address
    string = email + str(dt.now())
    # Convert the string to a sha256 hash
    return hashlib.sha256(string.encode('utf-8')).hexdigest()


def get_discord_authorization_url():
    base_url = "https://discord.com/api/v10/oauth2/authorize"
    client_id = os.environ.get('DISCORD_CLIENT_ID')
    scheme = "http" if os.environ.get('ENVIRONMENT') == 'development' else "https"
    redirect_uri = url_for('auth.discord_callback', _external=True, _scheme=scheme)
    scope = "identify guilds.join"
    return_url = f"{base_url}?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"
    return return_url


def convert_discord_code_to_token(code):
    base_url = "https://discord.com/api/v10/oauth2/token"
    client_id = os.environ.get('DISCORD_CLIENT_ID')
    client_secret = os.environ.get('DISCORD_CLIENT_SECRET')
    scheme = "http" if os.environ.get('ENVIRONMENT') == 'development' else "https"
    redirect_uri = url_for('auth.discord_callback', _external=True, _scheme=scheme)
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code
    }
    response = requests.post(base_url, data=data)
    return response.json()


def get_discord_info_for_token(token):
    base_url = "https://discord.com/api/v10/users/@me"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(base_url, headers=headers)
    return response.json()


def make_user_join_discord_guild(token, guild_id, user_id, access_token):
    base_url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    data = {"access_token": access_token}
    response = requests.put(base_url, headers=headers, json=data)
    if response.status_code == 204:
        return True
    elif response.status_code == 201:
        return True
    else:
        print(response.text)
        return False


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the form contents
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        # Look for the user
        user = User.query.filter(func.lower(User.username) == func.lower(username)).first()
        if user:
            # Check if password is correct
            if check_password_hash(user.password, password):
                login_user(user, remember=remember)
                flash('Logged in', "success")
                log_login(user)
                if not user.minecraft_uuid:
                    return redirect(url_for('auth.minecraft_authentication'))
                if not user.discord_uuid:
                    return redirect(url_for('auth.discord_authentication'))
                return redirect(url_for('index'))
            else:
                flash('Either username or password incorrect', "danger")
                return redirect(url_for('auth.login'))
        else:
            flash('Either username or password incorrect', "danger")
            return redirect(url_for('auth.login'))
    else:
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        else:
            return render_template('auth_pages/login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    # Remove user from cache
    cache_key = f"user_{current_user.session_id}"
    cache.delete(cache_key)
    logout_user()
    flash('Logged out', "success")
    return redirect(url_for('index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        if not get_site_settings()['registration_settings']['can_register']:
            flash("Registration is currently disabled", "danger")
            return redirect(url_for('index'))

        if not hcaptcha.verify():
            flash('Captcha failed', "danger")
            return redirect(url_for('auth.register'))
        # Get the form contents
        username = request.form.get('username')
        password = request.form.get('password')
        password_confirm = request.form.get('confirm')
        email = request.form.get('email')

        # Check for errors
        if password != password_confirm:
            flash('Passwords do not match', "danger")
            return redirect(url_for('auth.register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters long', "danger")
            return redirect(url_for('auth.register'))
        if len(username) < 3:
            flash('Username must be at least 3 characters long', "danger")
            return redirect(url_for('auth.register'))

        # Check if username is taken
        user = User.query.filter(func.lower(User.username) == func.lower(username)).first()
        if user:
            flash('Username already taken', "danger")
            return redirect(url_for('auth.register'))

        # Create the user
        password = generate_password_hash(password)
        user = User(username=username, password=password, email=email)

        try:
            db.session.add(user)
            db.session.commit()

            # Generate a confirmation token
            confirmation_token = generate_confirmation_token(email)
            # Send the confirmation email
            success = send_registration_email(user, confirmation_token)
            if success:
                new_user(username, email, request.remote_addr)
                flash('Successfully registered.', "success")
                return redirect(url_for('auth.login'))
            else:
                flash('Failed to send confirmation email.', "danger")
                return redirect(url_for('auth.register'))
        except SQLAlchemyError:
            flash('Something went wrong', "danger")
            return redirect(url_for('auth.register'))
    else:
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        else:
            return render_template('auth_pages/register.html')


@auth_bp.route('/minecraft/authentication', methods=['GET', 'POST'])
@login_required
def minecraft_authentication():
    if request.method == 'POST':
        # Get the form data
        auth_code = request.form.get('authCode', None)
        print(auth_code)
        if not auth_code:
            flash('No auth code provided', "danger")
            return redirect(url_for('auth.minecraft_authentication'))

        # Look up the auth code entered
        auth_code_object = MinecraftAuthentication.query.filter_by(auth_code=auth_code, is_used=False).first()
        if not auth_code_object:
            flash('Invalid auth code', "danger")
            return redirect(url_for('auth.minecraft_authentication'))

        # Check to see if the UUID is already in the database
        user_uuid = auth_code_object.uuid
        test_user = User.query.filter_by(minecraft_uuid=user_uuid).first()
        if test_user:
            flash('This Minecraft account has already been linked.', "danger")
            return redirect(url_for('auth.minecraft_authentication'))

        # Our auth code is valid, so we can now update the user's minecraft uuid
        # Get the user
        try:

            user = User.query.filter_by(id=current_user.id).first()
            user.set_minecraft_username(auth_code_object.username)
            user.set_minecraft_uuid(auth_code_object.uuid)
            # Delete the auth code object
            db.session.delete(auth_code_object)

            db.session.commit()
            flash('Successfully authenticated', "success")
            minecraft_linked_hook(user)
            return redirect(url_for('auth.discord_authentication'))
        except SQLAlchemyError:
            flash('Something went wrong', "danger")
            return redirect(url_for('auth.minecraft_authentication'))
    else:
        if not current_user.minecraft_uuid:
            return render_template('auth_pages/minecraft_authentication.html')
        else:
            flash('Already authenticated', "danger")
            return redirect(url_for('index'))


@auth_bp.route('/discord/authentication', methods=['GET', 'POST'])
@login_required
@minecraft_authenticated
def discord_authentication():
    discord_url = get_discord_authorization_url()
    return render_template("auth_pages/discord_authentication.html", discord_redirect=discord_url)


@auth_bp.route('/confirm_email/<token>', methods=['GET'])
def confirm_email(token):
    # Look up the confirmation token
    confirmation_token = EmailConfirmation.query.filter_by(token=token).one()
    if confirmation_token:
        # Look up the user
        user = User.query.filter_by(email=confirmation_token.email).first()
        if user:
            # Confirm the user
            user.set_email_confirmed(True)
            # Delete the token
            db.session.delete(confirmation_token)
            db.session.commit()
            flash('Email confirmed', "success")
            # Fire webhook
            email_confirmed_hook(user)
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid confirmation token', "danger")
            return redirect(url_for('index'))
    else:
        flash('Invalid confirmation token', "danger")
        return redirect(url_for('index'))


@auth_bp.route('/fully_authenticated', methods=['GET'])
@login_required
def fully_authenticated():
    flash('You are now fully authenticated', "success")
    return redirect(url_for('index'))


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # Get the email from the form
        email = request.form.get('email', None)
        if email is None:
            flash('Please enter an email', "danger")
            return redirect(url_for('auth.forgot_password'))
        # Lookup the user
        user = User.query.filter_by(email=email).first()
        if user:
            send_password_reset_email(user.email, user)
        flash("If an account exists with that email we'll send an email.", "success")
        return redirect(url_for('index'))

    else:
        return render_template('auth_pages/forgot_password.html')


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = verify_reset_token(token)
    if user is None:
        flash('Invalid or expired token', "danger")
        return redirect(url_for('auth.forgot_password'))
    else:
        if request.method == 'POST':
            # Get the form data
            data = request.form
            password1 = data.get('password', None)
            password2 = data.get('password2', None)
            if password1 is None or password2 is None:
                flash('Please enter a password', "danger")
                return redirect(url_for('auth.reset_password', token=token))
            if password1 != password2:
                flash('Passwords do not match', "danger")
                return redirect(url_for('auth.reset_password', token=token))

            password_hash = generate_password_hash(password1)
            # Check if the password is already set to that
            if user.password == password_hash:
                flash('You cannot use the same password.', "danger")
                return redirect(url_for('auth.reset_password', token=token))

            # Update the user
            try:
                user.set_password(password_hash)
                # Generate a new UUID for their session_id
                user.refresh_session_id()
                flash('Password updated', "success")
                return redirect(url_for('auth.login'))
            except SQLAlchemyError as e:
                print(e)
                flash('Error updating password', "danger")
                return redirect(url_for('auth.reset_password', token=token))
        else:
            return render_template('auth_pages/reset_password.html', token=token)


@auth_bp.route('/discord/callback', methods=['GET'])
@login_required
def discord_callback():
    # Get the code from the query string
    code = request.args.get('code', None)
    if code is None:
        flash('No code provided', "danger")
        return redirect(url_for('index'))

    # Get the discord auth token

    token_info = convert_discord_code_to_token(code)
    try:
        access_token = token_info['access_token']
        user_info = get_discord_info_for_token(access_token)
        user = User.query.filter_by(id=current_user.id).first()
        if get_site_settings()['registration_settings']['join_discord_on_register']:
            success = make_user_join_discord_guild(DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, user_info['id'], access_token)
            if not success:
                flash('Error joining Discord guild', "danger")
                return redirect(url_for('index'))
    except KeyError as e:
        print(e)
        print(f"Error: {token_info['error']}\nError Description: {token_info['error_description']}")
        flash('Error getting discord info. The error has been logged and will be investigated.', "danger")
        return redirect(url_for('index'))

    # Update the user
    try:
        user.set_discord_uuid(user_info['id'])
        flash('Discord account linked', "success")
        discord_linked_hook(user)
        return redirect(url_for('index'))
    except SQLAlchemyError as e:
        print(e)
        flash('Error linking Discord account', "danger")
        return redirect(url_for('index'))
