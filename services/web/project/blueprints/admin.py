from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError

from ..decorators import admin_required
from ..models import User, db, Ticket, TicketDepartment, SystemSetting, Faction, Application, AuditLog, ServerStatus
from ..models import set_applications_status, set_site_theme, set_panel_settings, set_server_settings, get_server_settings
from ..extensions import cache
from ..helpers import is_server_online

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
@login_required
@admin_required
# skipcq: PTC-W0049
def before_request():
    """
    This function is executed before each request.
    pass
    :return: Nothing
    """
    pass


@admin_bp.route('/')
@cache.cached(timeout=1)
def index():
    factions = Faction.query.order_by(Faction.id.desc()).all()
    pending = Application.query.filter(db.and_(
        Application.is_accepted.is_(False),
        Application.is_rejected.is_(False)
    )).count()
    accepted = Application.query.filter(Application.is_accepted.is_(True)).count()
    rejected = Application.query.filter(Application.is_rejected.is_(True)).count()
    new_users = User.query.filter(db.and_(
        User.discord_uuid.is_(None),
        User.minecraft_uuid.is_(None)
    )).count()
    fully_authed = User.query.filter(db.and_(
        User.discord_uuid.is_not(None),
        User.minecraft_uuid.is_not(None),
        User.is_whitelisted.is_(False)
    )).count()
    whitelisted = User.query.filter(User.is_whitelisted.is_(True)).count()
    servers = get_server_settings()
    server_status = ServerStatus.query.order_by(ServerStatus.created_at.desc()).first()
    status_json = server_status.status_json if server_status else None
    return render_template(
        'admin/index.html',
        title='Dashboard',
        factions=factions,
        pending_count=pending,
        accepted_count=accepted,
        rejected_count=rejected,
        new_users_count=new_users,
        fully_authed_count=fully_authed,
        whitelisted_count=whitelisted,
        servers=servers,
        status_json=status_json,
        len=len
    )


@admin_bp.route('/user/<int:user_id>')
def user(user_id):
    user_obj = User.query.get_or_404(user_id)
    return render_template('admin/user.html', user=user_obj, title='View User', editing=False)


@admin_bp.route('/users')
def users():
    return render_template('admin/users.html', title='Users')


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
    tickets_list = Ticket.query.filter(Ticket.status != 'closed') \
        .filter(Ticket.status != 'answered').order_by(Ticket.updated_at.asc()).all()
    return render_template('admin/tickets.html', tickets=tickets_list, title='Tickets')


@admin_bp.route('/closed-tickets')
def closed_tickets():
    tickets_list = Ticket.query.filter(Ticket.status == 'closed').order_by(Ticket.updated_at.asc()).all()
    return render_template('admin/tickets.html', tickets=tickets_list, title='Closed Tickets')


@admin_bp.route('/answered-tickets')
def answered_tickets():
    tickets_list = Ticket.query.filter(Ticket.status == 'answered').order_by(Ticket.updated_at.asc()).all()
    return render_template('admin/tickets.html', tickets=tickets_list, title='Answered Tickets')


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
        applications_open = request.form.get('applications_open') == 'on'
        site_theme = request.form.get('siteTheme')
        panel_api_key = request.form.get('api_key')
        panel_api_url = request.form.get('api_url')
        live_server_uuid = request.form.get('live_server_uuid')
        staging_server_uuid = request.form.get('staging_server_uuid')
        fallback_server_uuid = request.form.get('fallback_server_uuid')

        # update settings
        set_applications_status(applications_open)
        set_site_theme(site_theme)
        set_panel_settings(panel_api_key, panel_api_url)
        set_server_settings(live_server_uuid, staging_server_uuid, fallback_server_uuid)

        flash('Settings updated', 'success')
        return redirect(url_for('admin.settings'))
    else:
        try:
            settings_list = SystemSetting.query.first()
            return render_template('admin/settings.html', title='Settings', settings=settings_list)
        except SQLAlchemyError:
            settings_obj = SystemSetting()
            db.session.add(settings_obj)
            db.session.commit()
            return redirect(url_for('admin.settings'))


@admin_bp.route('/applications')
def applications():
    applications_list = Application.query.filter(db.and_(
        Application.is_accepted.is_(False),
        Application.is_rejected.is_(False)
    )).order_by(Application.id.asc()).all()
    return render_template('admin/applications.html', applications=applications_list, title='Applications')


@admin_bp.route('/accepted-applications')
def accepted_applications():
    applications_list = Application.query.filter(Application.is_accepted.is_(True)).order_by(Application.id.asc()).all()
    return render_template('admin/applications.html', applications=applications_list, title='Accepted Applications')


@admin_bp.route('/rejected-applications')
def rejected_applications():
    applications_list = Application.query.filter(Application.is_rejected.is_(True)).order_by(Application.id.asc()).all()
    return render_template('admin/applications.html', applications=applications_list, title='Rejected Applications')


@admin_bp.route('/applications/<int:application_id>')
def view_application(application_id):
    application = Application.query.filter_by(id=application_id).first()
    if not application:
        flash('Invalid application', 'danger')
        return redirect(url_for('admin.applications'))

    return render_template('admin/view_application.html', application=application, title='View Application')


@admin_bp.route('/audit-logs')
def audit_logs():
    return render_template('admin/audit_logs.html', title='Audit Logs')


@admin_bp.route('/audit-logs/data')
def audit_logs_data():
    # DataTables data stuff
    query = AuditLog.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            AuditLog.user.has(User.username.like(f'%{search}%')),
            AuditLog.target_type.like(f'%{search}%'),
            AuditLog.action.like(f'%{search}%'),
        ))

    total_filtered = query.count()

    # order by date
    query = query.order_by(AuditLog.created_at.desc())

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # resp
    return jsonify({
        'data': [row.to_dict() for row in query.all()],
        'recordsFiltered': total_filtered,
        'recordsTotal': AuditLog.query.count(),
        'draw': request.args.get('draw', type=int)
    })
