# wsgi.py - Phiên bản đơn giản
# Theo mặc định, monkey patching đã được thực hiện trong cả hai framework

import os
from flask import Flask
from flask_socketio import SocketIO

# Tạo ứng dụng Flask cơ bản
app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def home():
    return 'Novel Downloader API is running!'

@app.route('/ping')
def ping():
    return 'pong'

# Hàm này sẽ được gọi bởi Gunicorn
def create_app():
    return app

# Nếu chạy trực tiếp file này
if __name__ == "__main__":
    # Sử dụng PORT từ biến môi trường
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)