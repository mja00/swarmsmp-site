from ..extensions import socketio
from flask_socketio import send, emit
from flask_socketio import join_room, leave_room


@socketio.on('connect')
def handle_message(data):
    emit('after connect', {'data': 'Connected'})


@socketio.on('server listen')
def listen_server_status(data):
    join_room('server')
    emit('server status', {'data': 'Connected'})


def broadcast_server_status(status):
    socketio.emit('server status', {'data': status}, to='server')
