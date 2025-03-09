import threading
import time
import requests
import os
import logging

logger = logging.getLogger('keep_alive')

class KeepAlive:
    def __init__(self, interval=300):
        """
        Initialize the keep-alive system

        Args:
            interval: Time between pings in seconds (default: 300 seconds = 5 minutes)
        """
        self.interval = interval
        self.is_running = False
        self.thread = None
        self.replit_url = None

    def start(self, url=None):
        """
        Start the keep-alive system

        Args:
            url: The URL to ping. If None, it will use the REPLIT_URL environment variable
                 or try to detect the Replit URL automatically
        """
        if self.is_running:
            logger.info("Keep-alive service is already running")
            return

        # Determine URL to ping
        self.replit_url = url or os.environ.get('REPLIT_URL')

        # If URL is still None, try to detect it from Replit environment
        if not self.replit_url and os.environ.get('REPL_ID') and os.environ.get('REPL_OWNER'):
            repl_id = os.environ.get('REPL_ID')
            repl_owner = os.environ.get('REPL_OWNER')
            self.replit_url = f"https://{repl_id}.{repl_owner}.repl.co"

        if not self.replit_url:
            logger.warning("No URL provided and couldn't detect Replit URL. Keep-alive service not started.")
            return

        # Start the ping thread
        self.is_running = True
        self.thread = threading.Thread(target=self._ping_thread, daemon=True)
        self.thread.start()

        logger.info(f"Keep-alive service started. Will ping {self.replit_url} every {self.interval} seconds")

    def stop(self):
        """Stop the keep-alive system"""
        if not self.is_running:
            return

        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)

        logger.info("Keep-alive service stopped")

    def _ping_thread(self):
        """Thread function that periodically pings the URL"""
        while self.is_running:
            try:
                response = requests.get(self.replit_url, timeout=10)
                logger.debug(f"Keep-alive ping: {self.replit_url} - Response: {response.status_code}")
            except Exception as e:
                logger.warning(f"Keep-alive ping failed: {str(e)}")

            # Sleep for the specified interval
            for _ in range(self.interval):
                if not self.is_running:
                    break
                time.sleep(1)  # Check every second if we should stop