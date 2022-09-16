from models import SystemSetting, db
from .extensions import cache


@cache.cached(timeout=0, key_prefix='site_theme')
def get_site_theme():
    return SystemSetting.query.first().site_theme


@cache.cached(timeout=0, key_prefix='applications_open')
def get_applications_open() -> bool:
    return SystemSetting.query.first().applications_open


@cache.cached(timeout=0, key_prefix='can_register')
def get_can_register():
    return SystemSetting.query.first().can_register


@cache.cached(timeout=0, key_prefix='panel_settings')
def get_panel_settings():
    settings = SystemSetting.query.first()
    return {
        'panel_api_key': settings.panel_api_key,
        'panel_api_url': settings.panel_api_url,
    }


@cache.cached(timeout=0, key_prefix='server_settings')
def get_server_settings():
    settings = SystemSetting.query.first()
    return {
        'live_server_uuid': {
            "name": "Live Server",
            "uuid": settings.live_server_uuid,
        },
        'staging_server_uuid': {
            "name": "Staging Server",
            "uuid": settings.staging_server_uuid,
        },
        'fallback_server_uuid': {
            "name": "Fallback Server",
            "uuid": settings.fallback_server_uuid,
        }
    }


@cache.cached(timeout=0, key_prefix='application_settings')
def get_application_settings():
    settings = SystemSetting.query.first()
    return {
        "minimum_length": int(settings.minimum_length),
        "maximum_length": int(settings.maximum_length),
    }


@cache.cached(timeout=0, key_prefix='discord_settings')
def get_join_discord():
    return SystemSetting.query.first().join_discord_on_register


def set_applications_status(status: bool):
    setting = SystemSetting.query.first()
    setting.applications_open = status
    db.session.commit()
    cache.delete('applications_open')


def set_can_register(status: bool):
    setting = SystemSetting.query.first()
    setting.can_register = status
    db.session.commit()
    cache.delete('can_register')


def set_join_discord(status: bool):
    setting = SystemSetting.query.first()
    setting.join_discord_on_register = status
    db.session.commit()
    cache.delete('discord_settings')


def set_site_theme(theme: str):
    setting = SystemSetting.query.first()
    setting.site_theme = theme
    db.session.commit()
    cache.delete('site_theme')


def set_panel_settings(panel_api_key: str, panel_api_url: str):
    setting = SystemSetting.query.first()
    setting.panel_api_key = panel_api_key
    setting.panel_api_url = panel_api_url
    db.session.commit()
    cache.delete('panel_settings')


def set_server_settings(live_server_uuid: str, staging_server_uuid: str, fallback_server_uuid: str):
    setting = SystemSetting.query.first()
    setting.live_server_uuid = live_server_uuid
    setting.staging_server_uuid = staging_server_uuid
    setting.fallback_server_uuid = fallback_server_uuid
    db.session.commit()
    cache.delete('server_settings')


def set_application_settings(minimum_length: int, maximum_length: int):
    setting = SystemSetting.query.first()
    setting.minimum_length = minimum_length
    setting.maximum_length = maximum_length
    db.session.commit()
    cache.delete('application_settings')