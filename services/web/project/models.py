import datetime
import os
import uuid
from datetime import datetime as dt
from datetime import timedelta

import humanize
import jwt
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID

from .extensions import cache

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    discord_uuid = db.Column(db.String(255), nullable=True)
    minecraft_username = db.Column(db.String(255), nullable=True)
    minecraft_uuid = db.Column(db.String(255), nullable=True)
    characters = db.relationship('Character', backref='user', lazy=True)
    application = db.relationship('Application', backref='user', lazy=True)
    ban_reason = db.Column(db.Text(), nullable=True)
    staff_notes = db.Column(db.Text(), nullable=True)
    staff_title = db.Column(db.String(255), nullable=True)

    # Tickets
    tickets = db.relationship('Ticket', backref='owner', lazy=True)
    ticketreplies = db.relationship('TicketReply', backref='author', lazy=True)

    # User Settings
    site_theme = db.Column(db.String(255), nullable=True)

    # Boolean states
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_staff = db.Column(db.Boolean, nullable=False, default=False)
    is_banned = db.Column(db.Boolean, nullable=False, default=False)
    is_whitelisted = db.Column(db.Boolean, nullable=False, default=False)
    email_confirmed = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, username, password, email, discord_uuid=None, minecraft_username=None, minecraft_uuid=None):
        self.username = username
        self.password = password
        self.email = email
        self.discord_uuid = discord_uuid
        self.minecraft_username = minecraft_username
        self.minecraft_uuid = minecraft_uuid

    def __repr__(self):
        return '<User %s %s>' % (self.username, self.id)

    def get_password_reset_token(self, expires_in=600):
        return jwt.encode({
            'reset_password': self.username,
            'exp': dt.utcnow() + timedelta(seconds=expires_in)},
            key=os.getenv('SECRET_KEY'),
            algorithm="HS256"
        )

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'discord_uuid': self.discord_uuid,
            'minecraft_username': self.minecraft_username,
            'minecraft_uuid': self.minecraft_uuid,
            'minecraft_uuid_plain': self.minecraft_uuid_as_plain(),
            'is_admin': self.is_admin,
            'is_staff': self.is_staff,
            'is_banned': self.is_banned,
            'is_whitelisted': self.is_whitelisted,
            'email_confirmed': self.email_confirmed,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    def minecraft_uuid_as_plain(self):
        if self.minecraft_uuid is None:
            # Return a null UUID
            return '00000000000000000000000000000000'
        return self.minecraft_uuid.replace('-', '')

    @cache.memoize(timeout=3600)
    def has_character(self):
        characters = Character.query.filter_by(user_id=self.id, is_permad=False).all()
        return len(characters) > 0

    def get_avatar_link(self, size=150, skin_type='helm'):
        if self.minecraft_uuid is not None:
            return f"https://minotar.net/{skin_type}/{self.minecraft_uuid_as_plain()}/{size}"
        else:
            return "https://minotar.net/helm/MHF_Steve/150"

    def is_elevated(self):
        return self.is_admin or self.is_staff

    # @cache.memoize(timeout=3600)
    def get_most_recent_character(self):
        return db.session.query(Character).filter_by(user_id=self.id, is_permad=False).order_by(Character.created_at.desc()).options(db.joinedload('faction')).first()

    def delete_character_caches(self):
        cache.delete_memoized(self.has_character)
        cache.delete_memoized(self.get_most_recent_character)

    def get_id(self):
        return str(self.session_id)

    def delete_cache_for_user(self):
        cache.delete(f"user_{self.session_id}")

    def commit_and_invalidate_cache(self):
        db.session.commit()
        self.delete_cache_for_user()

    def refresh_session_id(self):
        self.session_id = str(uuid.uuid4())
        self.commit_and_invalidate_cache()

    # Setters
    def set_password(self, password):
        self.password = password
        self.commit_and_invalidate_cache()

    def set_is_whitelisted(self, value):
        self.is_whitelisted = value
        self.commit_and_invalidate_cache()

    def set_is_banned(self, value):
        self.is_banned = value
        self.commit_and_invalidate_cache()

    def set_minecraft_username(self, username):
        self.minecraft_username = username
        self.commit_and_invalidate_cache()

    def set_minecraft_uuid(self, given_uuid):
        self.minecraft_uuid = given_uuid
        self.commit_and_invalidate_cache()

    def set_discord_uuid(self, given_uuid):
        self.discord_uuid = given_uuid
        self.commit_and_invalidate_cache()

    def set_email(self, email):
        self.email = email
        self.commit_and_invalidate_cache()

    def set_email_confirmed(self, value):
        self.email_confirmed = value
        self.commit_and_invalidate_cache()

    def set_session_id(self, session_id):
        self.session_id = session_id
        self.commit_and_invalidate_cache()

    def add_command(self, command):
        command_obj = CommandQueue(self.id, command)
        db.session.add(command_obj)
        db.session.commit()
        self.delete_cache_for_user()

    def set_username(self, username):
        self.username = username
        self.commit_and_invalidate_cache()


class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    character_name = db.Column(db.String(255), nullable=False)
    character_faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=False)
    character_race = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    character_class = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    character_scale = db.Column(db.String(255), nullable=False)
    backstory = db.Column(db.Text(), nullable=False)
    description = db.Column(db.Text(), nullable=False)
    rejection_reason = db.Column(db.Text(), nullable=True)
    cooldown = db.Column(db.DateTime, nullable=True)

    # Boolean states
    is_accepted = db.Column(db.Boolean, default=False, nullable=False)
    is_rejected = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, user, character_name, character_faction, character_race, character_class, backstory, description, scale):
        self.user_id = user.id
        self.character_name = character_name
        self.character_faction_id = character_faction
        self.character_race = character_race
        self.character_class = character_class
        self.backstory = backstory
        self.description = description
        self.character_scale = scale

    def __repr__(self):
        return '<Application %r>' % self.id

    def get_humanized_created_at(self):
        return humanize.naturaltime(datetime.datetime.now() - self.created_at)


class Character(db.Model):
    __tablename__ = 'characters'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=False)
    subrace = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=False)
    clazz = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    scale = db.Column(db.String(255), nullable=False)
    backstory = db.Column(db.Text(), nullable=False)
    original_backstory = db.Column(db.Text(), nullable=False)
    description = db.Column(db.Text(), nullable=False)

    # JSON data for starting power
    starting_power = db.Column(db.JSON, nullable=False)

    # Boolean
    is_permad = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, user_id, name, faction, subrace, clazz, backstory, description, starting_power, is_permad, scale):
        self.user_id = user_id
        self.name = name
        self.faction_id = faction.id
        self.subrace = subrace
        self.clazz = clazz
        self.backstory = backstory
        self.original_backstory = backstory
        self.description = description
        self.starting_power = starting_power
        self.is_permad = is_permad
        self.scale = scale

    def __repr__(self):
        return '<Character %r>' % self.id


class MinecraftAuthentication(db.Model):
    __tablename__ = 'minecraft_authentications'

    id = db.Column(db.Integer, primary_key=True)
    auth_code = db.Column(db.Integer, nullable=False)
    uuid = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(255), nullable=False)
    is_used = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, auth_code, given_uuid, username):
        self.auth_code = auth_code
        self.uuid = given_uuid
        self.username = username

    def __repr__(self):
        return '<MinecraftAuthentication %r>' % self.id


class DiscordAuthentication(db.Model):
    __tablename__ = 'discord_authentications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    auth_hash = db.Column(db.String(255), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, user, auth_hash):
        self.user_id = user.id
        self.auth_hash = auth_hash

    def __repr__(self):
        return '<DiscordAuthentication %r>' % self.id


class EmailConfirmation(db.Model):
    __tablename__ = 'email_confirmations'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(255), nullable=False)
    is_used = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, user, email, token):
        self.user = user.id
        self.email = email
        self.token = token

    def __repr__(self):
        return '<EmailConfirmation %r>' % self.id


class TicketDepartment(db.Model):
    __tablename__ = 'ticket_departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text(), nullable=False)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)
    is_disabled = db.Column(db.Boolean, nullable=False, default=False)
    tickets = db.relationship('Ticket', backref='department', lazy=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, name, description, is_hidden=False, is_disabled=False):
        self.name = name
        self.description = description
        self.is_hidden = is_hidden
        self.is_disabled = is_disabled

    def __repr__(self):
        return '<TicketDepartment %r>' % self.id

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_hidden': self.is_hidden,
            'is_disabled': self.is_disabled
        }


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('ticket_departments.id'), nullable=False)
    status = db.Column(db.String(255), nullable=False, default='open')
    replies = db.relationship('TicketReply', backref='ticket', lazy=True)
    last_replied_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, owner: User, subject: str, department: TicketDepartment):
        self.owner_id = owner.id
        self.subject = subject
        self.department_id = department.id

    def __repr__(self):
        return '<Ticket %r>' % self.id

    def get_short_id(self):
        return str(self.id).split('-')[0]

    def get_humanized_created_at(self):
        return humanize.naturaltime(datetime.datetime.now() - self.created_at)

    def get_humanized_updated_at(self):
        return humanize.naturaltime(datetime.datetime.now() - self.updated_at)

    def get_humanized_last_replied_at(self):
        return humanize.naturaltime(datetime.datetime.now() - self.last_replied_at)


class TicketReply(db.Model):
    __tablename__ = 'ticket_replies'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text(), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, ticket: Ticket, user: User, content: str):
        self.ticket_id = ticket.id
        self.user_id = user.id
        self.content = content

    def __repr__(self):
        return '<TicketReply %r>' % self.id

    def get_humanized_created_at(self):
        return humanize.naturaltime(datetime.datetime.now() - self.created_at)

    def get_humanized_updated_at(self):
        return humanize.naturaltime(datetime.datetime.now() - self.updated_at)


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    applications_open = db.Column(db.Boolean, nullable=False, default=False)
    site_theme = db.Column(db.String(255), nullable=False, default='darkly')
    can_register = db.Column(db.Boolean, nullable=False, default=False)
    join_discord_on_register = db.Column(db.Boolean, nullable=False, default=False)

    # Application settings
    minimum_length = db.Column(db.Integer, nullable=False, default=20)
    maximum_length = db.Column(db.Integer, nullable=False, default=10000)

    # Panel related settings
    panel_api_key = db.Column(db.String(255), nullable=False, default='CHANGE_ME')
    panel_api_url = db.Column(db.String(255), nullable=False, default='http://localhost:5000/api/v1')
    live_server_uuid = db.Column(db.String(255), nullable=False, default='CHANGE_ME')
    staging_server_uuid = db.Column(db.String(255), nullable=False, default='CHANGE_ME')
    fallback_server_uuid = db.Column(db.String(255), nullable=False, default='CHANGE_ME')

    # Webhook settings
    ticket_webhook = db.Column(db.String(255), nullable=False, default='CHANGE_ME')
    application_webhook = db.Column(db.String(255), nullable=False, default='CHANGE_ME')
    general_webhook = db.Column(db.String(255), nullable=False, default='CHANGE_ME')
    dev_webhook = db.Column(db.String(255), nullable=False, default='CHANGE_ME')

    # Server settings
    maintenance_mode = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self):
        self.applications_open = False

    def __repr__(self):
        return '<SystemSetting %r>' % self.id


class Faction(db.Model):
    __tablename__ = 'factions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    characters = db.relationship('Character', backref='faction', lazy=True)
    applications = db.relationship('Application', backref='faction', lazy=True)
    classes = db.relationship('Class', backref='faction', lazy=True)
    races = db.relationship('Race', backref='faction', lazy=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Faction %r>' % self.id

    def total(self):
        # Get all characters that aren't perma'd
        characters = Character.query.filter_by(faction_id=self.id).filter_by(is_permad=False).filter_by(is_active=True).all()
        return len(characters)

    def online(self):
        # TODO: Make this pull from the DB
        _characters = self.characters
        return "N/A"

    def offline(self):
        # TODO: Make this pull from the DB
        _characters = self.characters
        return "N/A"


class Class(db.Model):
    __tablename__ = 'classes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    characters = db.relationship('Character', backref='class', lazy=True)
    applications = db.relationship('Application', backref='class', lazy=True)
    hidden = db.Column(db.Boolean, nullable=False, default=True)
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Class %r>' % self.id

    def total(self):
        characters = Character.query.filter_by(clazz=self.id).filter_by(is_permad=True).filter_by(is_active=True).all()
        return len(characters)

    def is_used(self):
        # Check if there is characters or applications using this class
        if len(self.characters) > 0 or len(self.applications) > 0:
            return True
        return False


class Race(db.Model):
    __tablename__ = 'races'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    characters = db.relationship('Character', backref='race', lazy=True)
    applications = db.relationship('Application', backref='race', lazy=True)
    hidden = db.Column(db.Boolean, nullable=False, default=True)
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, name, faction_id):
        self.name = name
        self.faction_id = faction_id

    def __repr__(self):
        return '<Race %r>' % self.id

    def total(self):
        characters = Character.query.filter_by(subrace=self.id).filter_by(is_permad=True).filter_by(is_active=True).all()
        return len(characters)

    def is_used(self):
        # Check if there is characters or applications using this class
        if len(self.characters) > 0 or len(self.applications) > 0:
            return True
        return False


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='audit_logs', lazy=True)
    action = db.Column(db.String(255), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    target_type = db.Column(db.String(255), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, user_id, action, target_id=0, target_type='N/A'):
        self.user_id = user_id
        self.action = action
        self.target_id = target_id
        self.target_type = target_type

    def __repr__(self):
        return '<AuditLog %r>' % self.id

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': self.user_id,
            'user': self.user.to_dict(),
            'action': self.action,
            'target_id': self.target_id,
            'target_type': self.target_type,
            'created_at': self.created_at,
            'created_at_human': self.get_humanized_created_at(),
            'updated_at': self.updated_at
        }

    def get_humanized_created_at(self):
        return humanize.naturaltime(datetime.datetime.now() - self.created_at)


class CommandQueue(db.Model):
    __tablename__ = 'command_queue'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='commands', lazy='subquery')
    command = db.Column(db.Text(), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, user_id, command):
        self.user_id = user_id
        self.command = command

    def __repr__(self):
        return '<CommandQueue %r>' % self.id


class ServerStatus(db.Model):
    __tablename__ = 'server_status'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status_json = db.Column(db.JSON, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, status_json):
        self.status_json = status_json

    def __repr__(self):
        return '<ServerStatus %r>' % self.id
