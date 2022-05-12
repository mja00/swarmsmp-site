import requests
import os
import time
import json

PANEL_API_URL = os.getenv('PANEL_API_URL', 'http://localhost:5000')
PANEL_API_KEY = os.getenv('PANEL_API_KEY', 'secret')
LIVE_SERVER_UUID = os.getenv('LIVE_SERVER_UUID', '123456789')
STAGING_SERVER_UUID = os.getenv('STAGING_SERVER_UUID', '123456789')
FALLBACK_SERVER_UUID = os.getenv('FALLBACK_SERVER_UUID', '123456789')
PORTAL_API_KEY = os.getenv('AUTH_KEY', 'secret')
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL", "http://localhost:8080")
UUIDS = [LIVE_SERVER_UUID, STAGING_SERVER_UUID, FALLBACK_SERVER_UUID]

headers = {
        'Authorization': f"{PORTAL_API_KEY}",
        'Content-Type': 'application/json'
    }


def get_status_for_server(server_uuid):
    url = f'{PANEL_API_URL}servers/{server_uuid}/resources'
    print(f"Getting status for server {server_uuid}")
    headers = {'Authorization': f'Bearer {PANEL_API_KEY}'}
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except requests.exceptions.ConnectionError:
        print(f"Error getting status for server {server_uuid}")
        return {'status': 0}


def is_server_online(status_json):
    try:
        if status_json['status'] == 1:
            return True
    except KeyError:
        return False
    return False


def get_query_for_server(status_json):
    return status_json['query']


def get_player_list(status_json):
    try:
        return get_query_for_server(status_json)['players']
    except KeyError:
        print("Failed to get player list")
        return []


def get_status_for_servers():
    output_json = {}
    for uuid in UUIDS:
        output_json[uuid] = {}
        status_json = get_status_for_server(uuid)
        if is_server_online(status_json):
            output_json[uuid]["online"] = True
            player_list = get_player_list(status_json)
            output_json[uuid]["player_list"] = player_list
        else:
            output_json[uuid]["online"] = False
            output_json[uuid]["player_list"] = []
    return output_json


def post_data_to_portal(data):
    url = f'{WEB_SERVER_URL}/api/update_server_status'
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        try:
            response_json = response.json()
            print(f"Error posting data to portal: {response_json['msg']}")
        except json.decoder.JSONDecodeError:
            print(f"Error posting data to portal")
    else:
        print("Successfully posted data to portal")


while True:
    output = get_status_for_servers()
    print(output)
    try:
        post_data_to_portal(output)
    except requests.exceptions.ConnectionError:
        print("Error posting data to portal")
    time.sleep(60)
