import os
import pickle
import uuid
import sentry_sdk
from datetime import datetime as dt
from datetime import timedelta

from flask import Flask, render_template, request, flash, redirect, url_for
from flask_debugtoolbar import DebugToolbarExtension
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from sentry_sdk.integrations.flask import FlaskIntegration

from .blueprints.admin import admin_bp as admin_blueprint
from .blueprints.api import api as api_blueprint
from .extensions import cache, socketio
from .blueprints.auth import auth_bp as auth_blueprint
from .blueprints.auth import hcaptcha
from .decorators import fully_authenticated
from .models import db, User, SystemSetting, Faction, Application, get_site_theme, get_applications_open
from .blueprints.ticket import ticket_bp as ticket_blueprint
from .blueprints.user import user_bp as user_blueprint

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0,
    environment=os.getenv("FLASK_ENV", ""),
)

development_env = os.getenv("FLASK_ENV", "development") == "development"


app = Flask(__name__)
app.debug = os.environ.get('FLASK_ENV') == 'development'
csp = {
    'default-src': '\'self\'',
    'img-src': '*',
    'style-src': [
        '\'self\'',
        'https://fonts.googleapis.com',
        'bootswatch.com',
        'cdnjs.cloudflare.com',
        'cdn.datatables.net',
        '\'unsafe-inline\''
    ],
    'script-src': [
        '\'self\'',
        'code.jquery.com',
        'cdnjs.cloudflare.com',
        'cdn.datatables.net',
        'cdn.jsdelivr.net',
        '\'unsafe-inline\''
    ],
    'font-src': [
        '\'self\'',
        'cdnjs.cloudflare.com',
        'fonts.gstatic.com',
        'fonts.googleapis.com'
    ]
}

# Login manager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = "danger"
login_manager.init_app(app)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.secret_key = os.getenv("SECRET_KEY", "secret")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "secret")

# hCaptcha settings
app.config["HCAPTCHA_SITE_KEY"] = os.getenv("HCAPTCHA_SITE_KEY", "")
app.config["HCAPTCHA_SECRET_KEY"] = os.getenv("HCAPTCHA_SECRET_KEY", "")
app.config["HCAPTCHA_ENABLED"] = bool(os.getenv("HCAPTCHA_ENABLED", "False"))

# Debug toolbar
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False

# Cache
app.config["CACHE_TYPE"] = os.getenv("CACHE_TYPE", "SimpleCache")
app.config["CACHE_REDIS_HOST"] = os.getenv("CACHE_REDIS_HOST", "localhost")
app.config["CACHE_REDIS_PORT"] = int(os.getenv("CACHE_REDIS_PORT", "6379"))
app.config["CACHE_REDIS_DB"] = int(os.getenv("CACHE_REDIS_DB", "0"))
app.config["CACHE_REDIS_URL"] = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")
app.config["CACHE_DEFAULT_TIMEOUT"] = int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300"))

# Scheme settings
if not os.getenv('FLASK_ENV') == 'development':
    app.config["PREFERRED_URL_SCHEME"] = "https"

db.init_app(app)
migrate = Migrate(app, db)
hcaptcha.init_app(app)
toolbar = DebugToolbarExtension(app)
cache.init_app(app)
socketio.init_app(app)

# Import our socketio file
from .blueprints import socket

# Blueprints
app.register_blueprint(auth_blueprint, url_prefix="/auth")
app.register_blueprint(api_blueprint, url_prefix="/api")
app.register_blueprint(user_blueprint, url_prefix="/user")
app.register_blueprint(admin_blueprint, url_prefix="/admin")
app.register_blueprint(ticket_blueprint, url_prefix="/tickets")


def is_valid_uuid(uuid_to_test, version=4):
    try:
        uuid_obj = uuid.UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test


@login_manager.user_loader
def load_user(user_id):
    # Check if user_id is a UUID
    if is_valid_uuid(user_id):
        # We wanna do some caching here to avoid hitting the database every time
        unique_cache_key = "user_" + user_id
        # This is pickling from our redis cache, this is safe to do since we're the ones handling it
        # skipcq: BAN-B301
        user_obj = pickle.loads(cache.get(unique_cache_key)) if cache.get(unique_cache_key) else None
        if user_obj is None:
            query = User.query.filter_by(session_id=str(user_id)).first()
            user_obj = pickle.dumps(query)
            cache.set(unique_cache_key, user_obj, timeout=3600)
            return query
        return user_obj
    return None


@app.context_processor
def inject_site_settings():
    return_dict = {
        "default_theme": get_site_theme(),
        "applications_open": get_applications_open(),
    }
    return dict(return_dict)


@app.route("/")
def index():
    return render_template("index.html")


if development_env:
    @app.route('/sentry_debug')
    def sentry_debug():
        divide_by_zero = 1 / 0
        return "You should never see this"


    @app.route('/notification_test/<string:user_id>')
    def notification_test(user_id):
        socket.broadcast_notification_to_user(user_id, "I hope you stub your toe you fucking loser", notif_title='lol u suck ass', notif_type='success')
        return "Notification sent"


@app.route("/apply", methods=["GET", "POST"])
@fully_authenticated
def apply():
    settings = SystemSetting.query.first()
    if settings.applications_open:
        if request.method == "POST":
            # Get the form
            form_data = request.form
            character_name = form_data.get("characterName")
            character_faction = form_data.get("characterFaction")
            character_class = form_data.get("characterClass")
            character_race = form_data.get("characterRace")
            character_backstory = form_data.get("characterBackstory")
            character_description = form_data.get("characterDescription")
            rule_agreement = form_data.get("ruleAgreement") == "on"

            # Check if the user has already applied
            app_check = Application.query.filter_by(user_id=current_user.id).all()
            if app_check:
                # Loop through all the applications and look for any that are still pending
                for l_app in app_check:
                    if not l_app.is_accepted and not l_app.is_rejected:
                        # Means they're still pending
                        flash("You already have an application pending.", "danger")
                        return redirect(url_for("user.profile"))
                    else:
                        # Check if the application is older than 7 days
                        if dt.utcnow() - l_app.updated_at < timedelta(days=7):
                            # Means it's still within 7 days
                            flash("You can only apply once every 7 days.", "danger")
                            return redirect(url_for("user.profile"))

            if not rule_agreement:
                flash("You must agree to the rules!", "danger")
                return redirect(url_for("apply"))
            # Are we in development
            if os.getenv("FLASK_ENV") != "development":
                # Check if backstory and description are over 500 characters
                if len(character_backstory) < 500 or len(character_description) < 500:
                    flash("Your backstory and description must be over 500 characters!", "danger")
                    return redirect(url_for("apply"))

                # Check if they're over 1500 characters
                if len(character_backstory) > 750 or len(character_description) > 750:
                    flash("Your backstory and description must be under 750 characters!", "danger")
                    return redirect(url_for("apply"))
            else:
                print("Skipping checks in development")

            # Create the application
            application = Application(
                user=current_user,
                character_name=character_name,
                character_faction=character_faction,
                character_class=character_class,
                character_race=character_race,
                backstory=character_backstory,
                description=character_description
            )
            # Save
            db.session.add(application)
            db.session.commit()
            flash("Your application has been submitted!", "success")
            return redirect(url_for("user.profile"))
        else:
            if current_user.is_whitelisted:
                flash("You're already whitelisted!", "success")
                return redirect(url_for("user.profile"))
            factions = Faction.query.all()
            return render_template("apply.html", factions=factions)
    else:
        flash("Applications are currently closed.", "danger")
        return redirect(url_for("index"))


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
