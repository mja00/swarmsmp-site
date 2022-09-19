from .models import SystemSetting, db
from .extensions import cache


# This is a new function that just gets all the settings and returns them as a dict
@cache.cached(timeout=0, key_prefix='site_settings')
def get_site_settings():
    settings = SystemSetting.query.first()
    return_dict = {
        "application_settings": {
            "minimum_length": settings.minimum_length,
            "maximum_length": settings.maximum_length,
            "applications_open": settings.applications_open
        },
        "panel_settings": {
            "panel_api_key": settings.panel_api_key,
            "panel_api_url": settings.panel_api_url,
            "live_server_uuid": settings.live_server_uuid,
            "staging_server_uuid": settings.staging_server_uuid,
            "fallback_server_uuid": settings.fallback_server_uuid
        },
        "webhook_settings": {
            "ticket_webhook": settings.ticket_webhook,
            "application_webhook": settings.application_webhook,
            "general_webhook": settings.general_webhook,
            "dev_webhook": settings.dev_webhook
        },
        "registration_settings": {
            "can_register": settings.can_register,
            "join_discord_on_register": settings.join_discord_on_register
        },
        "server_settings": {
            "maintenance_mode": settings.maintenance_mode
        },
        "site_theme": settings.site_theme
    }
    return return_dict


def clear_site_settings_cache():
    cache.delete('site_settings')


@cache.cached(timeout=0, key_prefix='server_settings')
def get_server_settings():
    settings = get_site_settings()
    return {
        'live_server_uuid': {
            "name": "Live Server",
            "uuid": settings['panel_settings']['live_server_uuid'],
        },
        'staging_server_uuid': {
            "name": "Staging Server",
            "uuid": settings['panel_settings']['staging_server_uuid'],
        },
        'fallback_server_uuid': {
            "name": "Fallback Server",
            "uuid": settings['panel_settings']['fallback_server_uuid'],
        }
    }


def set_applications_status(status: bool):
    setting = SystemSetting.query.first()
    setting.applications_open = status
    db.session.commit()
    clear_site_settings_cache()


def set_can_register(status: bool):
    setting = SystemSetting.query.first()
    setting.can_register = status
    db.session.commit()
    clear_site_settings_cache()


def set_join_discord(status: bool):
    setting = SystemSetting.query.first()
    setting.join_discord_on_register = status
    db.session.commit()
    clear_site_settings_cache()


def set_site_theme(theme: str):
    setting = SystemSetting.query.first()
    setting.site_theme = theme
    db.session.commit()
    clear_site_settings_cache()


def set_panel_settings(panel_api_key: str, panel_api_url: str):
    setting = SystemSetting.query.first()
    setting.panel_api_key = panel_api_key
    setting.panel_api_url = panel_api_url
    db.session.commit()
    clear_site_settings_cache()


def set_server_settings(live_server_uuid: str, staging_server_uuid: str, fallback_server_uuid: str):
    setting = SystemSetting.query.first()
    setting.live_server_uuid = live_server_uuid
    setting.staging_server_uuid = staging_server_uuid
    setting.fallback_server_uuid = fallback_server_uuid
    db.session.commit()
    clear_site_settings_cache()


def set_application_settings(minimum_length: int, maximum_length: int):
    setting = SystemSetting.query.first()
    setting.minimum_length = minimum_length
    setting.maximum_length = maximum_length
    db.session.commit()
    clear_site_settings_cache()


def set_webhook_settings(ticket, application, general, dev):
    setting = SystemSetting.query.first()
    setting.ticket_webhook = ticket
    setting.application_webhook = application
    setting.general_webhook = general
    setting.dev_webhook = dev
    db.session.commit()
    clear_site_settings_cache()
