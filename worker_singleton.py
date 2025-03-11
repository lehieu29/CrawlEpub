# Trong một file riêng tên worker_singleton.py
import threading
import logging

class WorkerThreadSingleton:
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, target_function, logger=None):
        with cls._lock:
            if cls._instance is None or not cls._instance.is_alive():
                log = logger or logging.getLogger('worker_singleton')
                log.info("Creating new worker thread instance")
                cls._instance = threading.Thread(target=target_function, daemon=True)
                cls._instance.start()
                log.info(f"Worker thread started, is_alive: {cls._instance.is_alive()}")
            return cls._instance
    
    @classmethod
    def is_running(cls):
        return cls._instance is not None and cls._instance.is_alive()