import secrets
import os
import time
import json
import threading
import queue
import hashlib
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

# Tạo secret key duy nhất cho mỗi phiên Replit
if not os.environ.get('SECURE_PATH_KEY'):
    os.environ['SECURE_PATH_KEY'] = secrets.token_hex(16)

# Tạo thư mục bảo mật dựa trên secret key
def get_secure_path(base_path):
    # Tạo hash từ secret key
    secure_hash = hashlib.sha256(os.environ['SECURE_PATH_KEY'].encode()).hexdigest()[:12]
    # Tạo đường dẫn bảo mật
    secure_path = os.path.join(base_path, secure_hash)
    os.makedirs(secure_path, exist_ok=True)
    return secure_path

# Cập nhật đường dẫn novel_temp và novel_output
NOVEL_TEMP = get_secure_path(os.path.join(os.getcwd(), 'novel_temp'))
NOVEL_OUTPUT = get_secure_path(os.path.join(os.getcwd(), 'novel_output'))
LOG_DIR = get_secure_path(os.path.join(os.getcwd(), 'logs'))

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
socketio = SocketIO(app, cors_allowed_origins="*")

# Queue for download tasks
download_queue = queue.Queue()

# Dictionary to store active downloads
active_downloads = {}

# Initialize Dropbox storage
dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN')
if not dropbox_token:
    logger.warning("DROPBOX_ACCESS_TOKEN not found! Dropbox storage will not work.")
dropbox_storage = DropboxStorage(logger=logger, socket=socketio, access_token=dropbox_token)

# Initialize the novel downloader with the specified parameters
downloader = NovelDownloader(
    logger=logger,
    socket=socketio,
    dropbox=dropbox_storage
)

# Background worker to process download tasks
def download_worker():
    while True:
        try:
            # Get a task from the queue
            task = download_queue.get()
            download_id = task['id']
            url = task['url']
            cookie = task.get('cookie', '')

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

        except Exception as e:
            logger.error(f"Error in download worker: {str(e)}")
            time.sleep(1)  # Prevent CPU spinning if there's a persistent error

# Start the download worker thread
worker_thread = threading.Thread(target=download_worker, daemon=True)
worker_thread.start()

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
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    return render_template('ping.html', timestamp=timestamp)

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
        download_queue.put(task)

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
    # Create necessary directories
    os.makedirs(NOVEL_TEMP, exist_ok=True)
    os.makedirs(NOVEL_OUTPUT, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
            
    # Determine port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))

    # Print server information
    logger.info(f"Starting Novel Downloader API on port {port}")
    logger.info(f"API documentation available at /")

    # Start the keep-alive service
    keep_alive.start()
    logger.info(f"Keep-alive service started. Will ping every 5 minutes.")

    # Start the server
    socketio.run(app, host='0.0.0.0', port=port)