from ..extensions import socketio
from flask_socketio import send, emit
from flask_socketio import join_room, leave_room, rooms
from flask_login import current_user


@socketio.on('connect')
def handle_message(data):
    emit('after connect', {'data': 'Connected'})


@socketio.on('disconnect')
def handle_disconnect():
    # Remove user from all rooms that they're in
    for room in rooms():
        leave_room(room)
    return


@socketio.on('server listen')
def listen_server_status(data):
    join_room('server')
    return


def broadcast_server_status(status):
    socketio.emit('server status', {'data': status}, to='server')


# User notifications
@socketio.on('notifications join')
def handle_notifications_join(data):
    join_room(f'notifications-{current_user.id}')
    return


def broadcast_notification_to_user(user_id, message, notif_type='info', notif_title="System Notification"):
    socketio.emit('new notification', {'message': message, 'type': notif_type, 'title': notif_title}, to=f'notifications-{user_id}')
