from flask_login import current_user
from flask_socketio import emit
from flask_socketio import join_room, leave_room, rooms

from ..extensions import socketio


@socketio.on('connect')
def handle_message(_):
    emit('after connect', {'data': 'Connected'})


@socketio.on('disconnect')
def handle_disconnect():
    # Remove user from all rooms that they're in
    for room in rooms():
        leave_room(room)


@socketio.on('server listen')
def listen_server_status(_):
    join_room('server')


def broadcast_server_status(status):
    socketio.emit('server status', {'data': status}, to='server')


# User notifications
@socketio.on('notifications join')
def handle_notifications_join(_):
    join_room(f'notifications-{current_user.id}')


def broadcast_notification_to_user(user_id, message, notif_type='info', notif_title="System Notification"):
    socketio.emit('new notification', {'message': message, 'type': notif_type, 'title': notif_title}, to=f'notifications-{user_id}')
