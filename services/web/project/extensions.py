from flask_caching import Cache
from flask_socketio import SocketIO
from flask import Flask

cache = Cache()
socketio = SocketIO()
app = Flask(__name__)
