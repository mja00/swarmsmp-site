from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .decorators import admin_required

from .models import User, db, Ticket, TicketDepartment, SystemSetting, Faction, Application

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
@login_required
@admin_required
def before_request():
    """ Protect all routes in this blueprint """
    pass


@admin_bp.route('/')
def index():
    factions = Faction.query.order_by(Faction.id.desc()).all()
    pending = Application.query.filter(db.and_(
        Application.is_accepted == False,
        Application.is_rejected == False
    )).count()
    accepted = Application.query.filter(Application.is_accepted == True).count()
    rejected = Application.query.filter(Application.is_rejected == True).count()
    return render_template(
        'admin/index.html',
        title='Dashboard',
        factions=factions,
        pending_count=pending,
        accepted_count=accepted,
        rejected_count=rejected
    )


@admin_bp.route('/users')
def users():
    users = User.query.all()
    return render_template('admin/users.html', users=users, title='Users')


@admin_bp.route('/users/data')
def users_data():
    query = User.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            User.username.like(f'%{search}%'),
            User.email.like(f'%{search}%')
        ))

    total_filtered = query.count()

    # order by id
    query = query.order_by(User.id.desc())

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # resp
    return jsonify({
        'data': [user.to_dict() for user in query.all()],
        'recordsFiltered': total_filtered,
        'recordsTotal': User.query.count(),
        'draw': request.args.get('draw', type=int)
    })


@admin_bp.route('/tickets')
def tickets():
    tickets = Ticket.query.filter(Ticket.status != 'closed') \
        .filter(Ticket.status != 'answered').order_by(Ticket.updated_at.asc()).all()
    return render_template('admin/tickets.html', tickets=tickets, title='Tickets')


@admin_bp.route('/closed-tickets')
def closed_tickets():
    tickets = Ticket.query.filter(Ticket.status == 'closed').order_by(Ticket.updated_at.asc()).all()
    return render_template('admin/tickets.html', tickets=tickets, title='Closed Tickets')


@admin_bp.route('/answered-tickets')
def answered_tickets():
    tickets = Ticket.query.filter(Ticket.status == 'answered').order_by(Ticket.updated_at.asc()).all()
    return render_template('admin/tickets.html', tickets=tickets, title='Answered Tickets')


@admin_bp.route('/tickets/view/<string:ticket_id>', methods=['GET'])
def view_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        flash('Invalid ticket', 'danger')
        return redirect(url_for('admin.tickets'))

    return render_template('admin/view_ticket.html', ticket=ticket, title='View Ticket',
                           departments=TicketDepartment.query.filter_by(is_disabled=False).all())


@admin_bp.route('/departments')
def departments():
    departments_list = TicketDepartment.query.order_by(TicketDepartment.id.asc()).all()
    return render_template('admin/departments.html', departments=departments_list, title='Departments')


@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == "POST":
        applications_open = True if request.form.get('applications_open') == 'on' else False

        # update settings
        settings_list = SystemSetting.query.first()
        settings_list.applications_open = applications_open
        db.session.commit()

        flash('Settings updated', 'success')
        return redirect(url_for('admin.settings'))
    else:
        settings_list = SystemSetting.query.first()
        return render_template('admin/settings.html', title='Settings', settings=settings_list)


@admin_bp.route('/applications')
def applications():
    applications_list = Application.query.filter(db.and_(
        Application.is_accepted == False,
        Application.is_rejected == False
    )).order_by(Application.id.asc()).all()
    return render_template('admin/applications.html', applications=applications_list, title='Applications')


@admin_bp.route('/accepted-applications')
def accepted_applications():
    applications_list = Application.query.filter(Application.is_accepted == True).order_by(Application.id.asc()).all()
    return render_template('admin/applications.html', applications=applications_list, title='Accepted Applications')


@admin_bp.route('/rejected-applications')
def rejected_applications():
    applications_list = Application.query.filter(Application.is_rejected == True).order_by(Application.id.asc()).all()
    return render_template('admin/applications.html', applications=applications_list, title='Rejected Applications')


@admin_bp.route('/applications/<int:application_id>')
def view_application(application_id):
    application = Application.query.filter_by(id=application_id).first()
    if not application:
        flash('Invalid application', 'danger')
        return redirect(url_for('admin.applications'))

    return render_template('admin/view_application.html', application=application, title='View Application')
