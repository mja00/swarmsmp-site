from . import app
from .extensions import socketio

if __name__ == '__main__':
    # skipcq: BAN-B104
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)