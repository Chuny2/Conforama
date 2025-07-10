"""
Conforama Session Manager
Handles login, session management, and phone number extraction
"""

import httpx
import re
import config

PHONE_PATTERNS = [
    re.compile(r'(\+34\s?)?[6-9]\d{8}', re.IGNORECASE),
    re.compile(r'(\+34\s?)?[8-9]\d{8}', re.IGNORECASE),
    re.compile(r'tel[^>]*>([^<]+)', re.IGNORECASE),
    re.compile(r'phone[^>]*>([^<]+)', re.IGNORECASE),
    re.compile(r'telefono[^>]*>([^<]+)', re.IGNORECASE),
    re.compile(r'móvil[^>]*>([^<]+)', re.IGNORECASE),
    re.compile(r'\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b', re.IGNORECASE),
    re.compile(r'value="([6-9]\d{8})"', re.IGNORECASE),
    re.compile(r'>\s*([6-9]\d{8})\s*<', re.IGNORECASE),
]

PHONE_CLEANUP_PATTERN = re.compile(r'[^\d+]')
DIGITS_PATTERN = re.compile(r'\d{9}')


class ConforamaSession:
    def __init__(self):
        timeout = httpx.Timeout(
            connect=config.HTTP_CONNECT_TIMEOUT,
            read=config.HTTP_READ_TIMEOUT,
            write=config.HTTP_TIMEOUT,
            pool=config.HTTP_TIMEOUT
        )
        
        limits = httpx.Limits(
            max_connections=config.HTTP_CONNECTION_POOL_SIZE,
            max_keepalive_connections=config.HTTP_MAX_KEEPALIVE_CONNECTIONS
        )
        
        self.session = httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            limits=limits,
            headers={
                "User-Agent": config.USER_AGENT,
                "Accept-Language": config.ACCEPT_LANGUAGE,
                "Accept-Encoding": "gzip, deflate",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "same-origin",
                "Te": "trailers"
            }
        )
        
    def _get_decoded_content(self, response):
        try:
            return response.text
        except Exception:
            content_encoding = response.headers.get('content-encoding', '').lower()
            
            if content_encoding == 'br':
                try:
                    import brotli
                    decompressed = brotli.decompress(response.content)
                    return decompressed.decode('utf-8')
                except ImportError:
                    return response.content.decode('utf-8', errors='replace')
                except Exception:
                    return response.content.decode('utf-8', errors='replace')
            else:
                return response.content.decode('utf-8', errors='replace')
    
    def get_login_page(self):
        login_page_url = "https://www.conforama.es/customer/account/login?returnUrl=%2Fsales%2Forder%2Fhistory"
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Priority": "u=0, i"
        }
        
        try:
            response = self.session.get(login_page_url, headers=headers)
            if response.status_code == 401:
                return "banned"
            return response.status_code == 200
        except Exception:
            return False
    
    def perform_login(self, username, password):
        login_url = "https://www.conforama.es/customer/account/login?ReturnUrl=%2Fsales%2Forder%2Fhistory"
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.conforama.es",
            "Referer": "https://www.conforama.es/customer/account/login?returnUrl=%2Fsales%2Forder%2Fhistory",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Priority": "u=0, i"
        }
        
        form_data = {
            "Login": username,
            "Password": password
        }
        
        try:
            response = self.session.post(login_url, headers=headers, data=form_data)
            if response.status_code == 401:
                return "banned"
            return "sales/order/history" in str(response.url)
        except Exception:
            return False
    
    def get_order_history(self):
        order_history_url = "https://www.conforama.es/sales/order/history"
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Priority": "u=0, i"
        }
        
        try:
            response = self.session.get(order_history_url, headers=headers)
            if response.status_code == 401:
                return "banned"
            return response.status_code == 200
        except Exception:
            return False
    
    def get_customer_address(self):
        address_url = "https://www.conforama.es/customer/address"
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.conforama.es/sales/order/history",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Priority": "u=0, i"
        }
        
        try:
            response = self.session.get(address_url, headers=headers)
            if response.status_code == 401:
                return "banned"
            if response.status_code == 200:
                html_content = self._get_decoded_content(response)
                return self.extract_phone_number(html_content)
            return None
        except Exception:
            return None
    
    def extract_phone_number(self, html_content):
        for pattern in PHONE_PATTERNS:
            matches = pattern.findall(html_content)
            if matches:
                for match in matches:
                    phone = match
                    if isinstance(phone, tuple):
                        phone = phone[-1]
                    
                    phone = PHONE_CLEANUP_PATTERN.sub('', phone)
                    
                    if phone and len(phone) >= 9:
                        digits = DIGITS_PATTERN.search(phone)
                        if digits:
                            number = digits.group(0)
                            if number.startswith('6'):
                                return number
        
        return None
    
    def close(self):
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
