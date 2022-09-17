import json
import os

import requests
import hashlib

from flask import url_for
from discord_webhook import DiscordWebhook, DiscordEmbed

from .models import User, Ticket, Application
from .settings_helper import get_panel_settings, get_server_settings, get_webhook_settings
from .extensions import app

MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')


class Error(Exception):
    """Base class for other exceptions"""
    pass


class UserNotFoundError(Error):
    """Raised when a user is not found"""
    pass


class MojangAPIError(Error):
    """Raised when an error occurs in the Mojang API"""
    pass


def get_username_from_uuid(uuid, pull_from_db=True) -> str:
    """
    Get username from uuid
    :parameter uuid: UUID to get the username from
    :parameter pull_from_db: If True, pull from the database, if False, pull from the Mojang API

    :return: Username
    """
    if not pull_from_db:
        url = f'https://api.mojang.com/user/profiles/{uuid}/names'
        r = requests.get(url)
        if r.status_code == 200:
            # Get the last element
            return r.json()[-1]['name']
        else:
            raise MojangAPIError("Error in Mojang API")
    else:
        user = User.query.filter_by(minecraft_uuid=uuid).first()
        if user:
            return user.minecraft_username
        else:
            raise UserNotFoundError(f"User not found with uuid {uuid}")


def send_template_to_email(email: str, template: str, subject: str, force: bool = False,
                           variables: dict = None) -> bool:
    """
    Send a template to an email
    :param subject: Subject of the email
    :param force: If True, forces email sending even in development mode
    :parameter email: Email to send the template to
    :parameter template: Template to send

    :return: True if the email was sent, False if not
    """
    if os.environ.get("ENVIRONMENT") == "development" and not force:
        print(
            "\n\nWe've caught you from accidentally sending an email in development mode.\nWe'll return True to not affect any functions.\n\n")
        return True
    else:
        data = {
            "from": "SwarmSMP <noreply@ssmp.theairplan.com>",
            "subject": subject,
            "to": email,
            "template": template,
        }
        if variables:
            data["h:X-Mailgun-Variables"] = json.dumps(variables)
        response = requests.post(
            "https://api.mailgun.net/v3/ssmp.theairplan.com/messages",
            auth=("api", MAILGUN_API_KEY),
            data=data
        )
        if response.status_code == 200:
            return True
        else:
            print(response.text)
            return False


def is_server_online(server_uuid: str) -> bool:
    panel_settings = get_panel_settings()
    headers = {
        "Authorization": f"Bearer {panel_settings['panel_api_key']}",
    }

    # We need to do a get request to the panel to get the server status
    url = f"{panel_settings['panel_api_url']}servers/{server_uuid}/resources"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        # Get the JSON response
        try:
            response = r.json()
        except json.decoder.JSONDecodeError:
            return False
        # Get the status
        status = response['status']
        # If the status is 1 it's online, if not, it's offline
        return status == 1
    else:
        return False


def send_command_to_server(server_name: str, command: str) -> bool:
    print(f"Sending command {command} to server {server_name}")
    panel_settings = get_panel_settings()
    server_settings = get_server_settings()
    server_uuid = server_settings[server_name]['uuid']
    headers = {
        "Authorization": f"Bearer {panel_settings['panel_api_key']}",
        "Content-Type": "application/json",
    }

    # We need to do a post request to the panel to send a command
    url = f"{panel_settings['panel_api_url']}servers/{server_uuid}/command"
    r = requests.post(url, headers=headers, json={'command': command})
    return r.status_code == 204
