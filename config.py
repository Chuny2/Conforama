"""
Configuration settings for Conforama Phone Extractor GUI
"""

# HTTP Request Configuration
HTTP_TIMEOUT = 30.0
FOLLOW_REDIRECTS = True

# Threading Configuration
DEFAULT_MAX_WORKERS = 3
MAX_WORKERS_LIMIT = 10

# URL Configuration
BASE_URL = "https://www.conforama.es"
LOGIN_URL = f"{BASE_URL}/customer/account/login"
ORDER_HISTORY_URL = f"{BASE_URL}/sales/order/history"
CUSTOMER_ADDRESS_URL = f"{BASE_URL}/customer/address"

# Headers Configuration
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
ACCEPT_LANGUAGE = "en-US,en;q=0.5"
ACCEPT_ENCODING = "gzip, deflate, br"

# File Configuration
DEFAULT_CREDENTIALS_FILE = "read.txt"
DEFAULT_RESULTS_FILE = "results.txt"

# GUI Configuration
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
WINDOW_TITLE = "Conforama Phone Extractor"

# Phone Number Configuration
PHONE_PATTERNS = [
    r'(\+34\s?)?[6-9]\d{8}',       # All Spanish phone formats
    r'(\+34\s?)?[8-9]\d{8}',       # Spanish landline format
    r'tel[^>]*>([^<]+)',           # Phone in tel tags
    r'phone[^>]*>([^<]+)',         # Phone in phone tags
    r'telefono[^>]*>([^<]+)',      # Spanish phone tags
    r'móvil[^>]*>([^<]+)',         # Mobile tags
    r'\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b',  # Generic 9-digit pattern
    r'value="([6-9]\d{8})"',       # Phone in input value
    r'>\s*([6-9]\d{8})\s*<',       # Phone between tags
]

# Only extract mobile numbers (starting with 6)
MOBILE_ONLY = True
