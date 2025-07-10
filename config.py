"""
Configuration settings for Conforama Phone Extractor GUI
"""

import platform

# Platform detection for optimizations
IS_WINDOWS = platform.system() == "Windows"

DEFAULT_MAX_WORKERS = 10
MAX_WORKERS_LIMIT = 100

HTTP_TIMEOUT = 10.0
HTTP_CONNECTION_POOL_SIZE = 15
HTTP_MAX_KEEPALIVE_CONNECTIONS = 8
HTTP_CONNECT_TIMEOUT = 3.0
HTTP_READ_TIMEOUT = 7.0

# Platform-specific thread delay (Windows needs longer delays)
THREAD_STARTUP_DELAY = 0.05 if IS_WINDOWS else 0.02

# Platform-specific GUI update settings
GUI_UPDATE_BATCH_SIZE = 20 if IS_WINDOWS else 10
GUI_UPDATE_INTERVAL = 0.2 if IS_WINDOWS else 0.1

MAX_LOG_ENTRIES = 1000
EXPORT_CHUNK_SIZE = 100
LARGE_DATASET_THRESHOLD = 1000
MAX_TABLE_ROWS = 5000

# Platform-specific log limits
MAX_LOG_LINES = 200 if IS_WINDOWS else 400

BASE_URL = "https://www.conforama.es"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
ACCEPT_LANGUAGE = "en-US,en;q=0.5"
ACCEPT_ENCODING = "gzip, deflate, br"

DEFAULT_CREDENTIALS_FILE = "read.txt"

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
WINDOW_TITLE = "Conforama Phone Extractor"
