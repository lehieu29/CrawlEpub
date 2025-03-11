# Thực hiện monkey-patching với eventlet thay vì gevent
import eventlet
eventlet.monkey_patch()

# Sau đó import các module khác
import os
from main import app, socketio, start_worker_thread

# Hàm này sẽ được gọi bởi Gunicorn
def create_app():
    # Khởi động worker thread khi ứng dụng khởi động
    start_worker_thread()
    return socketio.middleware(app)

# Nếu chạy trực tiếp file này
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port)