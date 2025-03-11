import secrets
import os
import time
import json
import threading
import eventlet.queue as queue
import hashlib
import datetime
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
from flask_cors import CORS
import logging
from dotenv import load_dotenv
from flask import send_from_directory
from flask import send_file

# Load environment variables
load_dotenv()

# Import our modules
from novel_downloader import NovelDownloader
from dropbox_storage import DropboxStorage
from keep_alive import KeepAlive
from dropbox_auth import DropboxAuth

# Tạo secret key duy nhất cho mỗi phiên Replit
if not os.environ.get('SECURE_PATH_KEY'):
    os.environ['SECURE_PATH_KEY'] = secrets.token_hex(16)

# Tạo thư mục bảo mật dựa trên secret key
def get_secure_path(base_path):
    try:
        # Tạo hash từ secret key
        secure_hash = hashlib.sha256(os.environ['SECURE_PATH_KEY'].encode()).hexdigest()[:12]
        # Tạo đường dẫn bảo mật
        secure_path = os.path.join(base_path, secure_hash)
        os.makedirs(secure_path, exist_ok=True)
        return secure_path
    except Exception as e:
        print(f"Error creating secure path: {e}")
        # Fallback to base path
        os.makedirs(base_path, exist_ok=True)
        return base_path

# Cập nhật đường dẫn novel_temp và novel_output
NOVEL_TEMP = get_secure_path(os.path.join(os.getcwd(), 'novel_temp'))
NOVEL_OUTPUT = get_secure_path(os.path.join(os.getcwd(), 'novel_output'))
LOG_DIR = get_secure_path(os.path.join(os.getcwd(), 'logs'))

# Create secure directory for tokens
SECURE_DIR = get_secure_path(os.path.join(os.getcwd(), 'secure'))

# Create necessary directories
os.makedirs(NOVEL_TEMP, exist_ok=True)
os.makedirs(NOVEL_OUTPUT, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SECURE_DIR, exist_ok=True)

# Initialize keep-alive system
keep_alive = KeepAlive(interval=300)  # Ping every 5 minutes

# Set up logging
log_file = os.path.join(LOG_DIR, 'novel_downloader.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger('novel_downloader_api')

# Create a custom logger handler that will store recent logs
class RecentLogsHandler(logging.Handler):
    def __init__(self, capacity=100):
        super().__init__()
        self.capacity = capacity
        self.logs = []

    def emit(self, record):
        log_entry = self.format(record)
        self.logs.append(log_entry)
        if len(self.logs) > self.capacity:
            self.logs.pop(0)

    def get_logs(self, n=None):
        if n is None:
            return self.logs
        return self.logs[-n:]

# Create our recent logs handler
recent_logs_handler = RecentLogsHandler()
recent_logs_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(recent_logs_handler)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'novel-downloader-secret')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Queue for download tasks
download_queue = queue.Queue()

# Dictionary to store active downloads
active_downloads = {}

# Initialize Dropbox storage
dropbox_auth = DropboxAuth(logger=logger, socket=socketio)
dropbox_storage = DropboxStorage(logger=logger, socket=socketio, dropbox_auth=dropbox_auth)

# Initialize the novel downloader with the specified parameters
downloader = NovelDownloader(
    logger=logger,
    socket=socketio,
    dropbox=dropbox_storage
)

# Initialize dropbox auth with the app
dropbox_auth.init_app(app)

# Background worker to process download tasks
def download_worker():
    logger.info("Worker thread started")
    while True:
        try:
            # Get a task from the queue
            logger.info("Worker thread waiting for task... (current thread ID: %s)", threading.get_ident())

            try:
                task = download_queue.get(block=True, timeout=10)  # Chờ 5 giây
                download_id = task['id']
                url = task['url']
                cookie = task.get('cookie', '')
                logger.info(f"Worker thread got task: {download_id}")

                # Update status
                active_downloads[download_id] = {
                    'status': 'in_progress',
                    'url': url,
                    'start_time': time.time(),
                    'progress': 0
                }

                # Emit status update
                socketio.emit('status_update', {
                    'download_id': download_id,
                    'status': 'in_progress',
                    'message': f"Starting download for {url}"
                })

                # Run the download
                logger.info(f"Starting download for URL: {url} with ID: {download_id}")
                result = downloader.download_novel(url, cookie=cookie, download_id=download_id)

                if result['success']:
                    # Update status on success
                    active_downloads[download_id]['status'] = 'completed'
                    active_downloads[download_id]['file_path'] = result['file_path']
                    active_downloads[download_id]['dropbox_url'] = result.get('dropbox_url', '')
                    active_downloads[download_id]['end_time'] = time.time()

                    # Emit completion event
                    socketio.emit('download_completed', {
                        'download_id': download_id,
                        'url': url,
                        'file_path': result['file_path'],
                        'dropbox_url': result.get('dropbox_url', '')
                    })

                    logger.info(f"Download completed for ID: {download_id}")
                else:
                    # Update status on failure
                    active_downloads[download_id]['status'] = 'failed'
                    active_downloads[download_id]['error'] = result['error']
                    active_downloads[download_id]['end_time'] = time.time()

                    # Emit failure event
                    socketio.emit('download_failed', {
                        'download_id': download_id,
                        'url': url,
                        'error': result['error']
                    })

                    logger.error(f"Download failed for ID: {download_id}: {result['error']}")

                # Mark task as done
                download_queue.task_done()
            except queue.Empty:
                # Log nếu không có task trong 5 giây
                logger.info("No task in queue for 5 seconds")
                
                # Kiểm tra trạng thái queue
                logger.info(f"Current queue size: {download_queue.qsize()}")
                
                # Ngủ ngắn để tránh CPU spinning
                time.sleep(1)
                
                continue

        except Exception as e:
            logger.error(f"Error in download worker: {str(e)}")
            time.sleep(1)  # Prevent CPU spinning if there's a persistent error

# Start the download worker thread
worker_thread = threading.Thread(target=download_worker, daemon=True)
worker_thread.start()

def monitor_worker_thread():
    global worker_thread
    while True:
        if not worker_thread.is_alive():
            logger.error("Worker thread is dead! Restarting it...")
            worker_thread = threading.Thread(target=download_worker, daemon=True)
            worker_thread.start()
            logger.info("Worker thread restarted")
        time.sleep(60)  # Check every minute

# Start the monitor thread
monitor_thread = threading.Thread(target=monitor_worker_thread, daemon=True)
monitor_thread.start()

# Replace the existing worker thread initialization with this:
def start_worker_thread():
    global worker_thread
    try:
        # Chấm dứt thread cũ nếu còn tồn tại
        if 'worker_thread' in globals() and worker_thread is not None:
            logger.info("Terminating old worker thread if it exists")
        
        # Tạo và khởi động thread mới
        logger.info("Starting download worker thread")
        worker_thread = threading.Thread(target=download_worker, daemon=True)
        worker_thread.start()
        logger.info(f"Worker thread started, is_alive: {worker_thread.is_alive()}")
        return True
    except Exception as e:
        logger.error(f"Error starting worker thread: {str(e)}")
        return False
    
# start_worker_thread()

# Web Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api-docs')
def api_docs():
    # Get base URL from request
    base_url = request.url_root.rstrip('/')
    return render_template('api_docs.html', base_url=base_url)

@app.route('/ping')
def ping():
    """Simple ping endpoint for keep-alive services like UptimeRobot"""
    # Lấy thời gian UTC
    utc_time = time.gmtime()
    # Tạo timestamp là giờ UTC+7 (giờ Việt Nam)
    vn_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", 
                                time.gmtime(time.mktime(utc_time) + 7*3600))
    return render_template('ping.html', timestamp=vn_timestamp)

@app.route('/thread/status')
def thread_status():
    global worker_thread

    # Kiểm tra worker_thread có tồn tại không
    if 'worker_thread' not in globals():
        return "Worker thread is not initialized"
    
    # Kiểm tra worker_thread có phải None không
    if worker_thread is None:
        return "Worker thread is None"
    
    # Thread đang hoạt động bình thường
    return f"Worker thread is alive: {worker_thread.is_alive()}"

@app.route('/thread/start')
def ensure_worker_thread():
    global worker_thread
    
    # Kiểm tra và khởi tạo lại thread nếu không hoạt động
    if worker_thread is None or not worker_thread.is_alive():
        try:
            worker_thread = threading.Thread(target=download_worker, daemon=True)
            worker_thread.start()
            logger.info("Ensured worker thread is running")
            return "Đang khởi động lại worker"
        except Exception as e:
            logger.error(f"Failed to ensure worker thread: {e}")
            return f"Failed to ensure worker thread: {e}"
        
# New route for Dropbox status page
@app.route('/dropbox/status')
def dropbox_status_page():
    is_connected = dropbox_auth.is_authorized()
    context = {
        'is_connected': is_connected,
        'account_info': None,
        'token_expires_in': None,
        'token_expires_time': None
    }
    
    if is_connected:
        # Get account info
        account_info = dropbox_auth.get_account_info()
        context['account_info'] = account_info
        
        # Get token expiration info
        tokens = dropbox_auth.get_tokens()
        if tokens and 'expires_at' in tokens:
            expires_at = tokens['expires_at']
            expires_in = expires_at - int(time.time())
            context['token_expires_in'] = expires_in
            # Format expiration time
            expires_time = datetime.datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')
            context['token_expires_time'] = expires_time
    
    return render_template('dropbox_status.html', **context)

# API Routes
@app.route('/api/download', methods=['POST'])
def start_download():
    try:
        data = request.json

        # Validate input
        if not data or 'url' not in data:
            return jsonify({'success': False, 'error': 'URL is required'}), 400

        url = data['url']
        cookie = data.get('cookie', '')

        # Generate a unique ID for this download
        download_id = f"download_{int(time.time())}"

        # Create a new download task and add it to the queue
        task = {
            'id': download_id,
            'url': url,
            'cookie': cookie
        }

        # Kiểm tra trạng thái của queue trước khi put
        logger.info(f"Current thread: {threading.current_thread().name}")
        logger.info(f"Queue before put - size: {download_queue.qsize()}")

        # Đảm bảo task được đưa vào queue
        try:
            download_queue.put(task, block=False)
            logger.info(f"Task added to queue successfully")
        except queue.Full:
            logger.error("Queue is full. Could not add task.")
            return jsonify({'success': False, 'error': 'Download queue is full'}), 500
        
        logger.info(f"Queue after put - size: {download_queue.qsize()}")

        # Initialize download status
        active_downloads[download_id] = {
            'status': 'queued',
            'url': url,
            'submit_time': time.time()
        }

        # Log and return the download ID
        logger.info(f"New download queued for URL: {url} with ID: {download_id}")
        return jsonify({
            'success': True,
            'download_id': download_id,
            'message': 'Download has been queued'
        })

    except Exception as e:
        logger.error(f"Error starting download: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status/<download_id>', methods=['GET'])
def get_download_status(download_id):
    try:
        # Check if the download ID exists
        if download_id not in active_downloads:
            return jsonify({'success': False, 'error': 'Download ID not found'}), 404

        # Get the download status
        status = active_downloads[download_id]

        # Get the number of log entries to return
        n_logs = request.args.get('logs', 20, type=int)

        # Filter logs for this download
        download_logs = [log for log in recent_logs_handler.get_logs() 
                        if download_id in log][-n_logs:]

        # Return the status and logs
        return jsonify({
            'success': True,
            'download_id': download_id,
            'status': status,
            'logs': download_logs
        })

    except Exception as e:
        logger.error(f"Error getting download status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/downloads/<filename>')
def download_file(filename):
    output_folder = os.path.join(os.getcwd(), 'novel_output')
    return send_from_directory(output_folder, filename, as_attachment=True)

@app.route('/api/download_direct/<download_id>', methods=['GET'])
def download_direct(download_id):
    try:
        # Kiểm tra nếu download này tồn tại trong active_downloads
        if download_id in active_downloads:
            # Kiểm tra nếu download đã hoàn thành
            if active_downloads[download_id]['status'] == 'completed':
                file_path = active_downloads[download_id].get('file_path')
                if file_path and os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    return send_file(file_path, as_attachment=True, download_name=filename)

        # Nếu không tìm thấy hoặc chưa hoàn thành
        return jsonify({'success': False, 'error': 'File not found or download not completed'}), 404
    except Exception as e:
        logger.error(f"Error providing direct download: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/downloads')
def list_downloads():
    output_folder = os.path.join(os.getcwd(), 'novel_output')
    files = []
    if os.path.exists(output_folder):
        files = [f for f in os.listdir(output_folder) if f.endswith('.epub')]

    return render_template('downloads.html', files=files)

@app.route('/api/logs', methods=['GET'])
def get_recent_logs():
    try:
        # Get the number of log entries to return
        n_logs = request.args.get('n', 100, type=int)

        # Get recent logs
        logs = recent_logs_handler.get_logs(n_logs)

        return jsonify({
            'success': True,
            'logs': logs
        })

    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")

# Run the application
if __name__ == '__main__':
    # Determine port from environment variable or use default
    port = int(os.environ.get('PORT', 10000))

    # Print server information
    logger.info(f"Starting Novel Downloader API on port {port}")
    logger.info(f"API documentation available at /")

    # Start the keep-alive service
    keep_alive.start()
    logger.info(f"Keep-alive service started. Will ping every 5 minutes.")

    # Start the server
    socketio.run(app, host='0.0.0.0', port=port)

application = socketio.wsgi_app if hasattr(socketio, 'wsgi_app') else app