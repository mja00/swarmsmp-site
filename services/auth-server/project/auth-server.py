import os
import random

import requests
from quarry.net.server import ServerFactory, ServerProtocol
from twisted.internet import reactor

base_web_url = os.getenv("WEB_SERVER_URL", "http://localhost:8080")
new_user_url = f"{base_web_url}/api/auth/minecraft"
AUTH_KEY = os.getenv("AUTH_KEY", None)
if not AUTH_KEY:
    raise Exception("AUTH_KEY environment variable not set")

headers = {
    "Authorization": f"{AUTH_KEY}",
}


def generate_auth_code():
    # Generate random 6 digit number
    auth_code = random.randint(000000, 999999)
    # Make sure it's padded with zeros
    auth_code = str(auth_code).zfill(6)
    return auth_code


def send_auth_code(display_name, uuid, ip_address):
    generated_code = generate_auth_code()
    post_dict = {
        "uuid": str(uuid),
        "display_name": display_name,
        "ip_address": ip_address,
        "auth_code": generated_code
    }
    response = requests.post(new_user_url, json=post_dict, headers=headers)
    if response.status_code == 200:
        # Kick them with the auth code
        return generated_code
    elif response.status_code == 400:
        # Check what the return msg is
        if response.json()["msg"] == "Auth code already used":
            # We need to re-fire this request
            print(f"Auth code for {display_name} already used, re-sending")
            send_auth_code(display_name, uuid, ip_address)
        elif response.json()["msg"] == "UUID already exists":
            # User has already authed once but never used the code, send back the code we already have for them
            auth_code = response.json()["auth_code"]
            print(f"User {display_name} has already authed but never used the code, sending back code {auth_code}")
            return auth_code
    elif response.status_code == 401:
        print("Invalid AUTH_KEY")
        return None


class AuthProtocol(ServerProtocol):
    def player_joined(self):
        ServerProtocol.player_joined(self)

        display_name = self.display_name
        uuid = self.uuid
        ip_address = self.remote_addr.host

        generated_code = send_auth_code(display_name, uuid, ip_address)
        if generated_code:
            print(
                f"{display_name} ({uuid}) ({ip_address}) has joined the server. Generated auth code: {generated_code}")
            self.close(
                f"\u00A7bSuccessfully Authenticated!\nPlease enter the auth code: \u00A7a\u00A7l{generated_code} \u00A7r\u00A7bon the website.")
        else:
            print(f"{display_name} ({uuid}) ({ip_address}) has joined the server. Failed to generate auth code.")
            self.close("\u00A7bFailed to Authenticate!\nPlease try again later.")


class AuthFactory(ServerFactory):
    protocol = AuthProtocol
    motd = "SwarmSMP Auth Server"
    max_players = 1


def main():
    factory = AuthFactory()

    print("Listening on port 25565")

    # skipcq: BAN-B104
    factory.listen("0.0.0.0", 25565)
    reactor.run()


if __name__ == "__main__":
    print("Starting Auth Server...")
    main()
