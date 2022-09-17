from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from threading import Thread

from ..decorators import whitelist_required
from ..models import db, Ticket, TicketReply, TicketDepartment
from ..helpers import new_ticket_webhook

ticket_bp = Blueprint('ticket', __name__)


@ticket_bp.before_request
@login_required
@whitelist_required
# skipcq: PTC-W0049
def before_request():
    pass  # Limits only whitelisted players to access any of these routes


@ticket_bp.route('/mine/')
def mine():
    tickets = Ticket.query.filter_by(owner_id=current_user.id).order_by(Ticket.updated_at.desc()).all()
    return render_template('tickets/my_tickets.html', tickets=tickets, title='My Tickets')


@ticket_bp.route('/view/<string:ticket_id>/', methods=['GET'])
def view(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        flash('Invalid ticket', 'danger')
        return redirect(url_for('ticket.mine'))

    if ticket.owner_id != current_user.id:
        flash('You do not have permission to view this ticket', 'danger')
        return redirect(url_for('ticket.mine'))

    if current_user.is_admin and ticket.owner.id != current_user.id:
        return redirect(url_for('admin.view_ticket', ticket_id=ticket_id))

    return render_template('tickets/view_ticket.html', ticket=ticket, title=f'Ticket #{ticket.get_short_id()}')


@ticket_bp.route('/create/', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        form_data = request.form
        title = form_data.get('title', None)
        department_id = int(form_data.get('department', None))
        message = form_data.get('message', None)
        if not title or not message:
            flash('Title and message are required', 'danger')
            return redirect(url_for('ticket.create'))
        # Look up the department
        department = TicketDepartment.query.filter_by(id=department_id).first()
        if not department:
            flash('Invalid department', 'danger')
            return redirect(url_for('ticket.create'))

        # Create the ticket
        ticket = Ticket(owner=current_user, subject=title, department=department)
        db.session.add(ticket)
        db.session.commit()

        # Send our webhook
        new_ticket_webhook(ticket.id, message)

        # Add the message
        ticket_reply = TicketReply(ticket=ticket, content=message, user=current_user)
        db.session.add(ticket_reply)
        db.session.commit()
        flash('Ticket created', 'success')
        return redirect(url_for('ticket.mine'))
    else:
        # Get a list of ticket departments
        departments = TicketDepartment.query.filter_by(is_hidden=False, is_disabled=False).all()
        return render_template('tickets/create_ticket.html', departments=departments, title='Create Ticket')
