from flask import Blueprint, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from .decorators import staff_required, admin_required, auth_key_required
from .models import MinecraftAuthentication, db, DiscordAuthentication, User, \
    Ticket, TicketReply, TicketDepartment, Application, Character
from .helpers import send_template_to_email, session_scope

from .helpers import get_username_from_uuid, MojangAPIError
from datetime import datetime as dt
import os

api = Blueprint('api', __name__)


def application_accepted(application: Application):
    # Get the user
    user = application.user
    # Set their is_whitelisted to True
    user.is_whitelisted = True
    # Create a new character for them, based on the application
    try:
        with session_scope() as session:
            character = Character(
                user_id=user.id,
                name=application.character_name,
                faction=application.faction,
                subrace=application.character_race,
                clazz=application.character_class,
                backstory=application.backstory,
                description=application.description,
                starting_power={},
                is_permad=False
            )
            session.add(character)
            print("Accepted application for user {}".format(user.username))
            # Email the user
            return send_template_to_email(
                email=user.email,
                template="application_accepted",
                subject="Congratulations! Your application has been accepted!"
            )
    except SQLAlchemyError as e:
        print("Error accepting application for user {}: {}".format(user.username, e))
        return False


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
            with session_scope() as session:
                session.delete(search)
                session.commit()
                return jsonify({"msg": "Auth code already used"}), 400
        else:
            # Return the auth code
            return jsonify({"msg": "Auth code already used"}), 400
    else:
        # We can add the auth code to the database
        with session_scope() as session:
            auth = MinecraftAuthentication(uuid=uuid, username=username, auth_code=auth_code)
            session.add(auth)
            session.commit()
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
    with session_scope() as session:
        user.minecraft_username = new_username
        session.commit()
        return jsonify({"msg": "Username updated", "username": new_username}), 200


@api.route('/ticket/<string:ticket_id>/close', methods=['POST'])
@login_required
def close_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        return jsonify({"msg": "Ticket not found"}), 400

    if not current_user.is_elevated():
        if ticket.owner_id != current_user.id:
            return jsonify({"msg": "You do not have permission to close this ticket"}), 400

    with session_scope() as session:
        ticket.status = "closed"
        session.commit()
        return jsonify({"msg": "Ticket closed"}), 200


@api.route('/ticket/<string:ticket_id>/open', methods=['POST'])
@login_required
def open_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        return jsonify({"msg": "Ticket not found"}), 400

    if not current_user.is_elevated():
        if ticket.owner_id != current_user.id:
            return jsonify({"msg": "You do not have permission to open this ticket"}), 400

    with session_scope() as session:
        ticket.status = "open"
        session.commit()
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

    with session_scope() as session:
        ticket.department_id = department.id
        session.commit()
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

    with session_scope() as session:
        ticket.status = status
        session.commit()
        return jsonify({"msg": "Status changed"}), 200


@api.route('/ticket/<string:ticket_id>/reply', methods=['POST'])
@login_required
def ticket_reply(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        flash('Invalid ticket', 'danger')
        return redirect(url_for('ticket.mine'))

    if not current_user.is_elevated():
        if ticket.owner_id != current_user.id:
            flash('You do not have permission to view this ticket', 'danger')
            return redirect(url_for('ticket.mine'))

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
    else:
        ticket.status = 'replied'
        ticket.last_replied_at = dt.utcnow()

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

    with session_scope() as session:
        department.is_hidden = True
        session.commit()
        return jsonify({"msg": "Department hidden"}), 200


@api.route('/department/<int:department_id>/unhide', methods=['POST'])
@admin_required
def unhide_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    with session_scope() as session:
        department.is_hidden = False
        session.commit()
        return jsonify({"msg": "Department unhidden"}), 200


@api.route('/department/<int:department_id>/disable', methods=['POST'])
@admin_required
def disable_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    with session_scope() as session:
        department.is_disabled = True
        session.commit()
        return jsonify({"msg": "Department disabled"}), 200


@api.route('/department/<int:department_id>/enable', methods=['POST'])
@admin_required
def enable_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).first()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    with session_scope() as session:
        department.is_disabled = False
        session.commit()
        return jsonify({"msg": "Department enabled"}), 200


@api.route('/department/<int:department_id>/delete', methods=['POST'])
@admin_required
def delete_department(department_id):
    department = TicketDepartment.query.filter_by(id=department_id).one()
    if not department:
        return jsonify({"msg": "Department not found"}), 400

    with session_scope() as session:
        session.delete(department)
        session.commit()
        return jsonify({"msg": "Department deleted"}), 200


def get_form_values(form):
    name = form.get('name', None)
    description = form.get('description', None)
    is_hidden = True if form.get('is_hidden', None) == '1' else False
    is_disabled = True if form.get('is_disabled', None) == '1' else False
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
        with session_scope() as session:
            department.name = name
            department.description = description
            department.is_hidden = is_hidden
            department.is_disabled = is_disabled
            session.commit()
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
        with session_scope() as session:
            department = TicketDepartment(name=name, description=description, is_hidden=is_hidden, is_disabled=is_disabled)
            session.add(department)
            session.commit()
            flash('Department added', 'success')
            return redirect(url_for('admin.departments'))
    except SQLAlchemyError as e:
        flash('Error adding department: {}'.format(e), 'danger')
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

    try:
        with session_scope() as session:
            application.is_accepted = True
            application.is_rejected = False
            success = application_accepted(application)
            if not success:
                return jsonify({"msg": "Error accepting application"}), 400
            else:
                session.commit()
                return jsonify({"msg": "Application accepted"}), 200
    except SQLAlchemyError as e:
        return jsonify({"msg": "Error accepting application: {}".format(e)}), 400


@api.route('/application/<int:application_id>/reject', methods=['POST'])
@admin_required
def reject_application(application_id):
    application = Application.query.filter_by(id=application_id).first()
    if not application:
        return jsonify({"msg": "Application not found"}), 400

    try:
        with session_scope() as session:
            application.is_rejected = True
            application.is_accepted = False
            db.session.commit()
            return jsonify({"msg": "Application rejected"}), 200
    except SQLAlchemyError as e:
        return jsonify({"msg": "Error rejecting application: {}".format(e)}), 400


@api.route('/user/<int:user_id>/unwhitelist', methods=['POST'])
@admin_required
def unwhitelist_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    try:
        with session_scope() as session:
            user.is_whitelisted = False
            session.commit()
            return jsonify({"msg": "User unwhitelisted"}), 200
    except SQLAlchemyError as e:
        return jsonify({"msg": "Error unwhitelisting user: {}".format(e)}), 400


@api.route('/user/<int:user_id>/whitelist', methods=['POST'])
@admin_required
def whitelist_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    try:
        with session_scope() as session:
            user.is_whitelisted = True
            session.commit()
            return jsonify({"msg": "User whitelisted"}), 200
    except SQLAlchemyError as e:
        return jsonify({"msg": "Error whitelisting user: {}".format(e)}), 400


@api.route('/minecraft/<string:uuid>/allow_connection', methods=['GET'])
@auth_key_required
def allow_connection(uuid):
    user = User.query.filter_by(minecraft_uuid=uuid).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    if user.is_banned:
        return jsonify({"msg": "User is banned", "allow": False}), 200

    if user.is_whitelisted:
        if user.has_character():
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

    try:
        with session_scope() as session:
            user.is_banned = True
            session.commit()
            return jsonify({"msg": "User banned"}), 200
    except SQLAlchemyError as e:
        return jsonify({"msg": "Error banning user: {}".format(e)}), 400


@api.route('/user/<int:user_id>/unban', methods=['POST'])
@admin_required
def unban_user(user_id):
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 400

    try:
        with session_scope() as session:
            user.is_banned = False
            session.commit()
            return jsonify({"msg": "User unbanned"}), 200
    except SQLAlchemyError as e:
        return jsonify({"msg": "Error unbanned user: {}".format(e)}), 400
