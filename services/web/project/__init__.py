import os
import pickle
import uuid
import requests
from datetime import datetime as dt
from datetime import timedelta
from threading import Thread

import sentry_sdk
from flask import render_template, request, flash, redirect, url_for, send_from_directory
from flask_debugtoolbar import DebugToolbarExtension
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from sentry_sdk import last_event_id
from sentry_sdk.integrations.flask import FlaskIntegration

from .blueprints.admin import admin_bp as admin_blueprint
from .blueprints.api import api as api_blueprint
from .blueprints.auth import auth_bp as auth_blueprint
from .blueprints.ticket import ticket_bp as ticket_blueprint
from .blueprints.user import user_bp as user_blueprint
from .decorators import fully_authenticated
from .extensions import cache, app
from .models import db, User, Faction, Application, Class, Race
from .settings_helper import get_site_settings
from .webhooks import new_application

development_env = os.getenv("ENVIRONMENT", "development") == "development"

if not development_env:
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN", ""),
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0,
        environment=os.getenv("ENVIRONMENT", "development"),
        send_default_pii=True,
        debug=False
    )

app.debug = os.environ.get('ENVIRONMENT') == 'development'
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
if not os.getenv('ENVIRONMENT') == 'development':
    app.config["PREFERRED_URL_SCHEME"] = "https"
else:
    app.config["PREFERRED_URL_SCHEME"] = "http"

db.init_app(app)
migrate = Migrate(app, db)
toolbar = DebugToolbarExtension(app)
cache.init_app(app)


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
    settings = get_site_settings()
    return_dict = {
        "default_theme": settings["site_theme"],
        "applications_open": settings["application_settings"]["applications_open"],
        "can_register": settings["registration_settings"]["can_register"],
    }
    return dict(return_dict)


@app.before_request
def correct_ip_for_cloudflare():
    # Check if CF-Connecting-IP is in the headers
    if "CF-Connecting-IP" in request.headers:
        real_ip = request.headers.get("CF-Connecting-IP")
        # Set remote_addr to the CF-Connecting-IP
        setattr(request, "remote_addr", real_ip)


@app.errorhandler(500)
def internal_server_error(_):
    return render_template("errors/500.html", sentry_event_id=last_event_id(), dsn=os.getenv("SENTRY_DSN")), 500


@app.errorhandler(404)
def page_not_found(_):
    return render_template("errors/404.html")


@app.route("/")
def index():
    caro_images = os.listdir(os.path.join(app.static_folder, "caro-pics"))
    # Ignore any files that start with ._ since MacOS is a piece of shit
    caro_images = [x for x in caro_images if not x.startswith("._")]
    # The images are in the format of pic[0-9].png
    # Sort them by their number
    caro_images.sort(key=lambda x: int(x.split(".")[0][3:]))
    return render_template("index.html", caro_images=caro_images)


@app.route("/robots.txt")
def robots():
    return send_from_directory("static", "robots.txt")


# Serves all of our static launcher files
@app.route("/launcher/<path:path>")
def launcher(path):
    return send_from_directory("static/launcher", path)


if development_env:
    @app.route('/sentry_debug')
    def sentry_debug():
        _divide_by_zero = 1 / 0
        return "You should never see this"


@cache.cached(timeout=3600)
@app.route('/s1-thanks')
def s1_thanks():
    s1_players = ['0zdon', '1leggedroflcoptr', '77Gameboy', '99fredd', '_MANT1S_', '_moth___', '_Reta', 'Adorara',
                  'Akann', 'Akukami', 'AL_ManOfEnd', 'AlphaIncline', 'ANIME_LORD_SKYE', 'Aran_Cheezy', 'Arrendt',
                  'AtticusWhitemire', 'Avis34', 'AxelGirl30', 'Azure_Grimm', 'BandAid91', 'Bashboy128',
                  'blacknightte', 'BlueyPanther', 'Bormeus', 'BoundlessScar', 'BurningToasts', 'Cagbert', 'Cat_Batman',
                  'CharaGlitchWitch', 'ChronoGear', 'Cibaly', 'Comrade_Socks', 'Conflee', 'Corowna',
                  'CrystalGarden', 'd1amond_dra90n5', 'Dalca', 'DarkAngel25', 'DarryBot', 'DatzGhostie', 'daverboy',
                  'DawnMystique', 'deadsha13', 'Dekustar714', 'Devious_Angel', 'DianaVTuber', 'Dillonator3',
                  'DocPayne_', 'Dr_Hasashimi', 'Ender_kitty1', 'Everki_8', 'Falcon4562', 'Fastpoker', 'FeelsChevreuil',
                  'Firelord1129', 'Flamewolf120', 'FluffyNeberu', 'FyreLord', 'gaibtris', 'GalaxyDamakun',
                  'GriseousAnim22', 'HatKidTTV', 'hmat09', 'huntman0697', 'ICON_maegeri', 'Imaginemod', 'ImParzival',
                  'iTzNikkitty', 'JADemiser', 'Jakk9891', 'jharry01', 'jjstarlord', 'Jormunzumr', 'jowlbowl',
                  'K3ntlageris', 'KalistaChan', 'katekyo61394', 'Kazuki286', 'Kevrex97', 'KingDepresso',
                  'kingdragon1j8', 'Korodachii', 'KOyster', 'Kraylek', 'KTKrysi', 'Kyithfantasy', 'KyriaKrysos',
                  'Lady_azure3', 'LaurenDarkmore', 'LbpZero', 'LeekWhibble', 'LesbianToast', 'LichbaneCa',
                  'lilsweeper1998', 'linxXsilver', 'lolchow00', 'LolHamsters', 'Lothrumaege', 'lotteje13',
                  'Madmanartist', 'MapleSpyru', 'Mathrador', 'Megamorphton', 'megarock1018', 'MercurialWilting',
                  'MisterMusashi', 'Misty_Lotus', 'Mitra123', 'mja00', 'moddkre', 'MorpheusTM', 'MrRespawn',
                  'MsOblivious', 'Mulmil', 'mutatedfox', 'Narbae', 'NarvonAZ', 'Nekokikai', 'nevakari', 'NicBerry10',
                  'NigelTrillnaire', 'NightclubRush', 'NoahAl', 'Noob04ever', 'OliviaKaori', 'OminousII', 'Omnijoel',
                  'Orion_Skykaller', 'OverratedHype', 'Paijichor', 'Peterisms', 'phantomdust149', 'PhantomKatz_',
                  'PhantomLord1180', 'PhoenixCraft2', 'Piilon', 'Professor_Alpaca', 'PsiRenn71', 'R0MAZI', 'RandomHill',
                  'RandomsCreations', 'Ranger_Savage', 'redempaladin', 'RenagadeJay', 'rennnnnnnnnnnnnn',
                  'RibbonyHeart', 'RockZero3', 'RPGPhysicist', 'Saiura', 'Satchi', 'Scionzenos', 'ScorpionShans13',
                  'SelinBroz', 'ShaoUnaware', 'shawneemorrisart', 'ShinyRay', 'ShockandMaw', 'Shokeliz', 'silentknight',
                  'SilverDusks', 'SilversShadow', 'Simulation_rk', 'sirclaw44', 'Skarra_365', 'Skulblaka1987',
                  'Skullamancer', 'SmallsMerre', 'Smoli_uvu', 'StarPuddles', 'StaticKiller1', 'Stormrphosis', 'Strazis',
                  'SugarcoatedWitch', 'Super5erious', 'T61Deadaim00', 'the_flyingangel', 'The_Kazz', 'TheChosenJuan007',
                  'TheDudeBro21', 'TheInnerWolf', 'Tossorn', 'Trishy1232', 'Twismyer', 'twistingmtd',
                  'TysontheCanadian', 'ValinCastor', 'Vecron', 'Ventiar0021', 'Versterven',
                  'VevinaCiseris', 'VillianShiroe', 'VRC_Ruby_Rose', 'Warden_Kesmas', 'Windown4Window',
                  'Wolfbrother13le', 'WolFierz', 'XerPSTV', 'YMGKevin', 'ZAMSPEAR', 'Zandwheet93', 'ZankioVR',
                  'Zechibi', 'Zevaak', 'ZRFrost']
    return render_template('thanks.html', players=s1_players)


@app.route('/apply', methods=['POST'])
@fully_authenticated
def apply_post():
    app_settings = get_site_settings()['application_settings']
    minimum_length = int(app_settings["minimum_length"])
    maximum_length = int(app_settings["maximum_length"])
    if app_settings['applications_open']:
        # Get the form
        form_data = request.form
        character_name = form_data.get("characterName")
        character_faction = form_data.get("characterFaction")
        character_class = form_data.get("characterClass")
        character_race = form_data.get("characterRace")
        character_backstory = form_data.get("characterBackstory")
        character_description = form_data.get("characterDescription")
        character_scale = form_data.get("characterScale")
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
                elif not l_app.cooldown:
                    continue
                else:
                    # Check if they're still in the cooldown period
                    current_time = dt.utcnow()
                    if current_time < l_app.cooldown:
                        flash(f"You're still in the cooldown period. You can apply again in {l_app.get_humanized_cooldown()}.", "danger")
                        return redirect(url_for("user.profile"))

        if not rule_agreement:
            flash("You must agree to the rules!", "danger")
            return redirect(url_for("apply"))
        # Are we in development
        if os.getenv("ENVIRONMENT") == "development":
            # Check if backstory and description are under min characters
            if len(character_backstory) < minimum_length or len(character_description) < minimum_length:
                flash(f"Your backstory and description must be over {minimum_length} characters!", "danger")
                return redirect(url_for("apply"))

            # Check if they're over max characters
            if len(character_backstory) > maximum_length or len(character_description) > maximum_length:
                flash(f"Your backstory and description must be under {maximum_length} characters!", "danger")
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
            description=character_description,
            scale=character_scale
        )
        # Save
        db.session.add(application)
        db.session.commit()
        # Successful application submission, send a webhook
        Thread(target=new_application, args=(application,)).start()
        flash("Your application has been submitted!", "success")
        return redirect(url_for("user.profile"))
    else:
        flash("Applications are currently closed.", "danger")
        return redirect(url_for("index"))


@app.route("/apply", methods=["GET"])
@fully_authenticated
def apply():
    app_settings = get_site_settings()['application_settings']
    minimum_length = int(app_settings["minimum_length"])
    maximum_length = int(app_settings["maximum_length"])
    if app_settings['applications_open']:
        if current_user.is_whitelisted and not current_user.is_admin:
            flash("You're already whitelisted!", "success")
            return redirect(url_for("user.profile"))
        factions = Faction.query.all()
        classes = Class.query.filter_by(hidden=False).all()
        races = Race.query.filter_by(hidden=False).all()
        return render_template("apply.html", factions=factions, classes=classes, races=races, min=minimum_length, max=maximum_length)
    else:
        flash("Applications are currently closed.", "danger")
        return redirect(url_for("index"))


def find_asset_for_system(asset_list, system):
    for asset in asset_list:
        if "blockmap" in asset["name"]:
            continue
        if system in asset["name"]:
            return asset
    return None


@app.route("/download")
def download():
    # This'll be the download page, we need to get the artifacts from GitHub
    github_api = "https://api.github.com/repos/mja00/SwarmSMPLauncher/releases/latest"
    # Get the json from the API
    response = requests.get(github_api)
    if response.status_code == 200:
        json_data = response.json()
        assets = json_data["assets"]
        downloadable_assets = {
            "windows": find_asset_for_system(assets, ".exe"),
            "linux": find_asset_for_system(assets, ".AppImage"),
            "darwin-x64": find_asset_for_system(assets, "x64.dmg"),
            "darwin-arm64": find_asset_for_system(assets, "arm64.dmg"),
        }
        return render_template("download.html", downloadable_assets=downloadable_assets, latest_version=downloadable_assets['windows']['name'].split('-')[3].split('.exe')[0])


@app.route("/swarmsmp-mod")
def swarmsmp_mod():
    return render_template("swarmsmp-mod.html")
