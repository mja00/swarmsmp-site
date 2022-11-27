from . import app
from flask import Flask

if __name__ == '__main__':
    # skipcq: BAN-B104
    Flask.run(app, debug=True, host='0.0.0.0', port=5000)
