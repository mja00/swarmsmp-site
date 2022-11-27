from flask_caching import Cache
from flask import Flask

cache = Cache()
app = Flask(__name__)
