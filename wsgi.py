# Đầu tiên, thực hiện monkey-patching trước khi import bất kỳ module nào khác
from gevent import monkey
monkey.patch_all()

# Sau đó import Flask app
from main import app, socketio

# Hàm này sẽ được gọi bởi Gunicorn
def create_app():
    return socketio.middleware(app)

# Nếu chạy trực tiếp file này
if __name__ == "__main__":
    socketio.run(app)