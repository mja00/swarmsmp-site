from .extensions import app
from .models import User, Ticket, Application
from .settings_helper import get_webhook_settings
from flask import url_for
from discord_webhook import DiscordWebhook, DiscordEmbed
import hashlib


def trim_ticket_id(ticket_id):
    return str(ticket_id)[0:7]


def new_ticket_webhook(ticket_id, first_message):
    with app.app_context():
        ticket = Ticket.query.filter_by(id=ticket_id).first()
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['ticket_webhook'],
            username=ticket.owner.username,
            avatar_url=ticket.owner.get_avatar_link()
        )
        embed = DiscordEmbed(title='New ticket created', color=0x00ff00)
        embed.set_timestamp()

        embed.add_embed_field(name='Ticket ID', value=str(trim_ticket_id(ticket.id)), inline=True)
        embed.add_embed_field(name='Department', value=ticket.department.name, inline=True)
        embed.add_embed_field(name='Subject', value=ticket.subject, inline=False)
        embed.add_embed_field(name='Content', value=first_message, inline=False)

        webhook.add_embed(embed)
        webhook.execute()


def new_ticket_reply(ticket, reply_content):
    with app.app_context():
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['ticket_webhook'],
            username=ticket.owner.username,
            avatar_url=ticket.owner.get_avatar_link()
        )
        embed = DiscordEmbed(title='New reply to ticket', color=0xf39c12)
        embed.set_timestamp()

        embed.add_embed_field(name='Ticket ID', value=str(trim_ticket_id(ticket.id)), inline=True)
        embed.add_embed_field(name='Department', value=ticket.department.name, inline=True)
        embed.add_embed_field(name='Reply', value=reply_content, inline=False)

        webhook.add_embed(embed)
        webhook.execute()


def new_application(application):
    with app.app_context():
        current_application = Application.query.filter_by(id=application.id).first()
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['application_webhook'],
            username=current_application.user.username,
            avatar_url=current_application.user.get_avatar_link()
        )
        embed = DiscordEmbed(title='New application', color=0xf39c12)
        embed.set_timestamp()

        embed.add_embed_field(name='Name', value=current_application.character_name, inline=True)
        embed.add_embed_field(name='Faction', value=current_application.faction.name, inline=True)
        embed.add_embed_field(name='Race', value=current_application.race.name, inline=True)
        embed.add_embed_field(name='Class', value=current_application.clazz.name, inline=True)

        webhook.add_embed(embed)
        webhook.execute()


def hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()


def new_user(username, email, request_ip):
    with app.app_context():
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['general_webhook'],
            username=username
        )
        embed = DiscordEmbed(title='New user', color=0x00ff00)
        embed.set_timestamp()

        embed.add_embed_field(name='Username', value=username, inline=True)
        embed.add_embed_field(name='Email', value=email, inline=True)
        embed.add_embed_field(name='IP Hash', value=hash_ip(request_ip), inline=False)

        webhook.add_embed(embed)
        webhook.execute()


def email_confirmed_hook(user):
    with app.app_context():
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['general_webhook'],
            username=user.username
        )
        embed = DiscordEmbed(title='Email confirmed', color=0x00ff00)
        embed.set_timestamp()

        embed.add_embed_field(name='Username', value=user.username, inline=True)
        embed.add_embed_field(name='Email', value=user.email, inline=True)

        webhook.add_embed(embed)
        webhook.execute()


def discord_linked_hook(user: User):
    with app.app_context():
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['general_webhook'],
            username=user.username
        )
        embed = DiscordEmbed(title='Discord linked', color=0x00ff00)
        embed.set_timestamp()

        embed.add_embed_field(name='Discord', value=f"<@{user.discord_uuid}>", inline=True)

        webhook.add_embed(embed)
        webhook.execute()


def minecraft_linked_hook(user: User):
    with app.app_context():
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['general_webhook'],
            username=user.username,
            avatar_url=user.get_avatar_link()
        )
        embed = DiscordEmbed(title='Minecraft linked', color=0x00ff00)
        embed.set_timestamp()

        embed.add_embed_field(name='Minecraft Username', value=user.minecraft_username, inline=True)
        embed.add_embed_field(name='Minecraft UUID', value=user.minecraft_uuid, inline=True)

        webhook.add_embed(embed)
        webhook.execute()


def user_edited_by_admin(user, admin):
    with app.app_context():
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['dev_webhook'],
            username=admin.username,
            avatar_url=admin.get_avatar_link()
        )
        embed = DiscordEmbed(title=f'User edited by {admin.username}', color=0xff0000)
        embed.set_timestamp()

        embed.add_embed_field(name='Username', value=user.username, inline=True)
        embed.add_embed_field(name='Email', value=user.email, inline=True)
        embed.add_embed_field(name='Discord', value=f"<@{user.discord_uuid}>", inline=True)
        embed.add_embed_field(name='Minecraft Username', value=user.minecraft_username, inline=True)
        embed.add_embed_field(name='Minecraft UUID', value=user.minecraft_uuid, inline=True)

        webhook.add_embed(embed)
        webhook.execute()


def site_settings_hook(admin):
    with app.app_context():
        webhook_settings = get_webhook_settings()
        webhook = DiscordWebhook(
            url=webhook_settings['dev_webhook'],
            username=admin.username,
            avatar_url=admin.get_avatar_link(),
            content="I just messed with the site's settings!"
        )
        webhook.execute()
