import os
# First, do monkey-patching before importing any other modules
from gevent import monkey
monkey.patch_all()

# Then import Flask app
from main import app, socketio

# This function will be called by Gunicorn
def create_app():
    port = int(os.environ.get('PORT', 'not set'))
    print(f"PORT environment variable: {port}")
    return socketio.middleware(app)

# If running this file directly
if __name__ == "__main__":
    # Make sure to use the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port)