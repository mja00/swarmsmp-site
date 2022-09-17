import time
from datetime import datetime as dt
from threading import Thread

from flask import Blueprint, jsonify, request, flash, redirect, url_for, copy_current_request_context
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from .socket import broadcast_server_status, broadcast_notification_to_user
from ..decorators import staff_required, admin_required, auth_key_required
from ..extensions import cache
from ..helpers import get_username_from_uuid, MojangAPIError
from ..helpers import send_template_to_email, send_command_to_server
from ..logger import log_connect
from ..models import MinecraftAuthentication, db, DiscordAuthentication, User, \
    Ticket, TicketReply, TicketDepartment, Application, Character, CommandQueue, \
    ServerStatus, Faction
from ..webhooks import new_ticket_reply

api = Blueprint('api', __name__)


def application_accepted(application: Application):
    # Get the user
    user = application.user
    # Set their is_whitelisted to True
    user.set_is_whitelisted(True)
    # Create a new character for them, based on the application
    character = Character(
        user_id=user.id,
        name=application.character_name,
        faction=application.faction,
        subrace=application.character_race,
        clazz=application.character_class,
        backstory=application.backstory,
        description=application.description,
        scale=application.character_scale,
        starting_power={},
        is_permad=False
    )
    db.session.add(character)
    db.session.commit()
    print(f"Accepted application for user {user.username}")
    # TODO: Give the user the whitelist role on Discord
    # TODO: Give the user their faction role on Discord
    # Delete the caches for the user's character functions
    user.delete_character_caches()
    # Email the user
    return send_template_to_email(
        email=user.email,
        template="application_accepted",
        subject="Congratulations! Your application has been accepted!"
    )


@api.route('/auth/minecraft', methods=['POST'])
@auth_key_required
def auth_minecraft():
    """
    Ties a Minecraft account to a user.
    :return: Status message
    """
    # Ensure the body is json
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400

    # Get the body's data
    data = request.get_json()

    # Get the data from the body
    uuid = data.get('uuid', None)
    username = data.get('display_name', None)
    auth_code = data.get('auth_code', None)

    # Ensure all data is present
    if not uuid or not username or not auth_code:
        return jsonify({"msg": "Missing data in request"}), 400

    # Check if the uuid already exists
    uuid_search = MinecraftAuthentication.query.filter_by(uuid=uuid, is_used=False).first()
    if uuid_search:
        return jsonify({"msg": "UUID already exists", "auth_code": uuid_search.auth_code}), 400

    # Check if the auth code is already used
    search = MinecraftAuthentication.query.filter_by(auth_code=auth_code).first()
    if search:
        # Check if is_used is true
        if search.is_used:
            # Delete the auth code from the database
            db.session.delete(MinecraftAuthentication.query.filter_by(auth_code=auth_code).one())
            db.session.commit()
            return jsonify({"msg": "Auth code already used"}), 400
        else:
            # Return the auth code
            return jsonify({"msg": "Auth code already used"}), 400
    else:
        # We can add the auth code to the database
        auth = MinecraftAuthentication(given_uuid=uuid, username=username, auth_code=auth_code)
        db.session.add(auth)
        db.session.commit()
        return jsonify({"msg": "Auth code added"}), 200


@api.route('/auth/discord', methods=['POST'])
@auth_key_required
def auth_discord():
    """
        Ties a Discord account to a user.
        :return: Status message
        """
    # Ensure the body is json
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400

    # Get the body's data
    data = request.get_json()

    # Get the data from the body
    user_uuid = str(data.get('user_uuid', None))
    auth_code = data.get('auth_code', None)

    # Ensure all data is present
    if not user_uuid or not auth_code:
        return jsonify({"msg": "Missing data in request"}), 400

    # Check for the auth code
    search = DiscordAuthentication.query.filter_by(auth_hash=auth_code).one()
    if search:
        # Get the user
        user = User.query.filter_by(id=search.user_id).first()
        user.discord_uuid = user_uuid
        db.session.delete(search)
        db.session.commit()
        return jsonify({"msg": "Auth code added"}), 200
    else:
        return jsonify({"msg": "Auth code not found"}), 400


@api.route('/refresh/minecraft', methods=['POST'])
@login_required
def refresh_minecraft():
    # Get the user
    user = User.query.filter_by(id=current_user.id).first()
    try:
        new_username = get_username_from_uuid(user.minecraft_uuid, pull_from_db=False)
    except MojangAPIError:
        return jsonify({"msg": "Error getting username"}), 400

    # Update the username
    user.set_minecraft_username(new_username)
    return jsonify({"msg": "Username updated", "username": new_username}), 200


@api.route('/ticket/<string:ticket_id>/close', methods=['POST'])
@login_required
def close_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        return jsonify({"msg": "Ticket not found"}), 400

    if (
            not current_user.is_elevated()
            and ticket.owner_id != current_user.id
    ):
        return jsonify({"msg": "You do not have permission to close this ticket"}), 400

    ticket.status = "closed"
    db.session.commit()
    return jsonify({"msg": "Ticket closed"}), 200


@api.route('/ticket/<string:ticket_id>/open', methods=['POST'])
@login_required
def open_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        return jsonify({"msg": "Ticket not found"}), 400

    if (
            not current_user.is_elevated()
            and ticket.owner_id != current_user.id
    ):
        return jsonify({"msg": "You do not have permission to close this ticket"}), 400

    ticket.status = "open"
    db.session.commit()
    return jsonify({"msg": "Ticket opened"}), 200


@api.route('/ticket/<string:ticket_id>/change_department', methods=['POST'])
@staff_required
def ticket_change_department(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        return jsonify({"msg": "Ticket not found"}), 400

    department = request.get_json().get('department', None)
    if not department:
        return jsonify({"msg": "Missing department"}), 400

    department = TicketDepartment.query.filter_by(id=department).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    ticket.department_id = department.id
    db.session.commit()
    return jsonify({"msg": "Department changed"}), 200


@api.route('/ticket/<string:ticket_id>/change_status', methods=['POST'])
@staff_required
def ticket_change_status(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        return jsonify({"msg": "Ticket not found"}), 400

    status = request.get_json().get('status', None)
    if not status:
        return jsonify({"msg": "Missing status"}), 400

    ticket.status = status
    db.session.commit()
    return jsonify({"msg": "Status changed"}), 200


@api.route('/ticket/<string:ticket_id>/reply', methods=['POST'])
@login_required
def ticket_reply(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        flash('Invalid ticket', 'danger')
        return redirect(url_for('ticket.mine'))

    if (
            not current_user.is_elevated()
            and ticket.owner_id != current_user.id
    ):
        return jsonify({"msg": "You do not have permission to close this ticket"}), 400

    reply_content = request.form.get('reply_content', None)
    if not reply_content:
        flash('Reply content is required', 'danger')
        return redirect(url_for('ticket.view', ticket_id=ticket_id))

    # Add the reply
    reply = TicketReply(ticket=ticket, content=reply_content, user=current_user)
    db.session.add(reply)

    if (current_user.is_elevated() and ticket.owner_id != current_user.id) and ticket.status != 'answered':
        ticket.status = 'answered'
        ticket.last_replied_at = dt.utcnow()
        broadcast_notification_to_user(ticket.owner.id, 'A new reply has been posted to your ticket', 'info',
                                       'New Ticket Reply')
    else:
        ticket.status = 'replied'
        ticket.last_replied_at = dt.utcnow()
        # Client replied to ticket, send webhook
        Thread(target=new_ticket_reply, args=(ticket, reply_content)).start()

    db.session.commit()
    flash('Reply added', 'success')
    # Return them to the page they were on
    if request.referrer:
        return redirect(request.referrer)
    else:
        return redirect(url_for('ticket.view', ticket_id=ticket_id))


@api.route('/department/<int:department_id>/hide', methods=['POST'])
@admin_required
def hide_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    department.is_hidden = True
    db.session.commit()
    return jsonify({"msg": "Department hidden"}), 200


@api.route('/department/<int:department_id>/unhide', methods=['POST'])
@admin_required
def unhide_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    department.is_hidden = False
    db.session.commit()
    return jsonify({"msg": "Department unhidden"}), 200


@api.route('/department/<int:department_id>/disable', methods=['POST'])
@admin_required
def disable_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    department.is_disabled = True
    db.session.commit()
    return jsonify({"msg": "Department disabled"}), 200


@api.route('/department/<int:department_id>/enable', methods=['POST'])
@admin_required
def enable_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    department.is_disabled = False
    db.session.commit()
    return jsonify({"msg": "Department enabled"}), 200


@api.route('/department/<int:department_id>/delete', methods=['POST'])
@admin_required
def delete_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).one()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    db.session.delete(department)
    db.session.commit()
    return jsonify({"msg": "Department deleted"}), 200


def get_form_values(form):
    name = form.get('name', None)
    description = form.get('description', None)
    is_hidden = form.get('is_hidden', None) == '1'
    is_disabled = form.get('is_disabled', None) == '1'
    return name, description, is_hidden, is_disabled


@api.route('/department/<int:department_id>/edit', methods=['POST'])
@admin_required
def edit_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('admin.departments'))

    name, description, is_hidden, is_disabled = get_form_values(request.form)
    if not name:
        flash('Name is required', 'danger')
        return redirect(url_for('admin.departments'))
    if not description:
        flash('Description is required', 'danger')
        return redirect(url_for('admin.departments'))

    try:
        department.name = name
        department.description = description
        department.is_hidden = is_hidden
        department.is_disabled = is_disabled
        db.session.commit()
        flash('Department edited', 'success')
        return redirect(url_for('admin.departments'))
    except SQLAlchemyError:
        flash('Error editing department', 'danger')
        return redirect(url_for('admin.departments'))


@api.route('/department/new', methods=['POST'])
@admin_required
def new_department():
    name, description, is_hidden, is_disabled = get_form_values(request.form)

    if not name:
        flash('Department name is required', 'danger')
        return redirect(url_for('admin.departments'))
    if not description:
        flash('Department description is required', 'danger')
        return redirect(url_for('admin.departments'))

    try:
        department = TicketDepartment(name=name, description=description, is_hidden=is_hidden, is_disabled=is_disabled)
        db.session.add(department)
        db.session.commit()
        flash('Department added', 'success')
        return redirect(url_for('admin.departments'))
    except SQLAlchemyError as e:
        flash(f'Error adding department: {e}', 'danger')
        return redirect(url_for('admin.departments'))


@api.route('/department/<int:department_id>', methods=['GET'])
@admin_required
def get_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    return jsonify(department.to_dict())


@api.route('/application/<int:application_id>/accept', methods=['POST'])
@admin_required
def accept_application(application_id):
    application = Application.query.filter_by(id=application_id).first()
    if not application:
        return jsonify({"msg": "Application not found"}), 400

    application.is_accepted = True
    application.is_rejected = False
    success = application_accepted(application)
    if not success:
        return jsonify({"msg": "Error accepting application"}), 400
    else:
        db.session.commit()
        return jsonify({"msg": "Application accepted"}), 200


@api.route('/application/<int:application_id>/reject', methods=['POST'])
@admin_required
def reject_application(application_id):
    application = Application.query.filter_by(id=application_id).first()
    if not application:
        return jsonify({"msg": "Application not found"}), 400

    # Get the rejection reason
    reason = request.form.get('reason')

    application.is_rejected = True
    application.is_accepted = False
    application.rejection_reason = reason
    db.session.commit()
    return jsonify({"msg": "Application rejected"}), 200


@api.route('/user/<int:user_id>/unwhitelist', methods=['POST'])
@admin_required
def unwhitelist_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    user.set_is_whitelisted(False)
    return jsonify({"msg": "User unwhitelisted"}), 200


@api.route('/user/<int:user_id>/whitelist', methods=['POST'])
@admin_required
def whitelist_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    user.set_is_whitelisted(True)
    return jsonify({"msg": "User whitelisted"}), 200


@api.route('/minecraft/<string:uuid>/allow_connection', methods=['GET'])
@cache.cached(timeout=60)
@auth_key_required
def allow_connection(uuid):
    print(f"Checking connection for {uuid}")
    user = User.query.filter_by(minecraft_uuid=uuid).first()
    if not user:
        return jsonify({"msg": "User not found. Please create an account on the portal.", "allow": False}), 200

    if user.is_banned:
        return jsonify({"msg": "User is banned. Reason: TODO", "allow": False}), 200

    if user.is_whitelisted:
        if user.has_character():
            print(f"User {user.username} is whitelisted and has a character. Allowing connection.")
            log_connect(user)

            @copy_current_request_context
            def check_command_queue(user_id):
                # Wait 30 seconds to ensure the user has properly connected
                time.sleep(30)
                # We need app context to do a query here
                commands = CommandQueue.query.filter_by(user_id=user_id).all()

                for command in commands:
                    success = send_command_to_server("staging_server_uuid", command.command)
                    if success:
                        # Remove command
                        db.session.delete(command)
                        db.session.commit()

            Thread(target=check_command_queue, args=(user.id,)).start()
            return jsonify({"allow": True}), 200
        else:
            return jsonify({"allow": False, "msg": "You need to make a character on your profile."}), 200
    else:
        return jsonify({"allow": False, "msg": "You're not whitelisted."}), 200


@api.route('/user/<int:user_id>/ban', methods=['POST'])
@admin_required
def ban_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    user.set_is_banned(True)
    return jsonify({"msg": "User banned"}), 200


@api.route('/user/<int:user_id>/unban', methods=['POST'])
@admin_required
def unban_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    user.set_is_banned(False)
    return jsonify({"msg": "User unbanned"}), 200


@api.route('/user/<int:user_id>/command', methods=['POST'])
@admin_required
def add_command(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    command = request.form.get('command')
    if not command:
        return jsonify({"msg": "Command not found"}), 400

    user.add_command(command)
    return jsonify({"msg": "Command added"}), 200


@api.route('/update_server_status', methods=['POST'])
@auth_key_required
def update_server_status():
    # Get the JSON body from the request
    data = request.get_json()
    broadcast_server_status(data)
    status_obj = ServerStatus(data)
    db.session.add(status_obj)
    db.session.commit()
    return jsonify({"msg": "Server status updated", "data": data}), 200


@api.route('/get_faction_info/<int:faction_id>', methods=['GET'])
def get_faction_info(faction_id):
    faction = Faction.query.filter_by(id=faction_id).first()
    if not faction:
        return jsonify({"msg": "Faction not found"}), 400

    data = {
        "name": faction.name,
        "classes": faction.classes,
        "races": [{"name": race.name, "id": race.id} for race in faction.races if not race.hidden]
    }
    return jsonify(data)
