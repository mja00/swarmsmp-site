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

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(UUID(as_uuid=True), unique=True, nullable=False)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    discord_uuid = db.Column(db.String(255), nullable=True)
    minecraft_username = db.Column(db.String(255), nullable=True)
    minecraft_uuid = db.Column(db.String(255), nullable=True)
    characters = db.relationship('Character', backref='user', lazy=True)
    tickets = db.relationship('Ticket', backref='owner', lazy=True)
    ticketreplies = db.relationship('TicketReply', backref='author', lazy=True)
    application = db.relationship('Application', backref='user', lazy=True)

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
        return '<User %r>' % self.username

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
        return self.minecraft_uuid.replace('-', '')

    def has_character(self):
        characters = Character.query.filter_by(user_id=self.id, is_permad=False).all()
        return len(characters) > 0

    def get_avatar_link(self, size=150, type='helm'):
        if self.minecraft_uuid is not None:
            if type == 'helm':
                return f"https://minotar.net/helm/{self.minecraft_uuid_as_plain()}/{size}"
            elif type == 'bust':
                return f"https://minotar.net/bust/{self.minecraft_uuid_as_plain()}/{size}"
            elif type == 'body':
                return f"https://minotar.net/body/{self.minecraft_uuid_as_plain()}/{size}"
            elif type == 'cube':
                return f"https://minotar.net/cube/{self.minecraft_uuid_as_plain()}/{size}"
            else:
                return f"https://minotar.net/avatar/{self.minecraft_uuid_as_plain()}/{size}"
        else:
            return "https://minotar.net/helm/MHF_Steve/150"

    def is_elevated(self):
        return self.is_admin or self.is_staff

    def get_most_recent_character(self):
        return Character.query.filter_by(user_id=self.id, is_permad=False).order_by(Character.id.desc()).first()

    def get_id(self):
        return str(self.session_id)


class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    character_name = db.Column(db.String(255), nullable=False)
    character_faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=False)
    character_race = db.Column(db.String(255), nullable=False)
    character_class = db.Column(db.String(255), nullable=False)
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

    def __init__(self, user, character_name, character_faction, character_race, character_class, backstory, description):
        self.user_id = user.id
        self.character_name = character_name
        self.character_faction_id = character_faction
        self.character_race = character_race
        self.character_class = character_class
        self.backstory = backstory
        self.description = description

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
    subrace = db.Column(db.String(255), nullable=False)
    clazz = db.Column(db.String(255), nullable=False)
    backstory = db.Column(db.Text(), nullable=False)
    description = db.Column(db.Text(), nullable=False)

    # JSON data for starting power
    starting_power = db.Column(db.JSON, nullable=False)

    # Boolean
    is_permad = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, user_id, name, faction, subrace, clazz, backstory, description, starting_power, is_permad):
        self.user_id = user_id
        self.name = name
        self.faction_id = faction.id
        self.subrace = subrace
        self.clazz = clazz
        self.backstory = backstory
        self.description = description
        self.starting_power = starting_power
        self.is_permad = is_permad

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

    def __init__(self, auth_code, uuid, username):
        self.auth_code = auth_code
        self.uuid = uuid
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

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Faction %r>' % self.id

    def total(self):
        return len(self.characters)

    def online(self):
        return 0

    def offline(self):
        return 0
