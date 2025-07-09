"""
Conforama Session Manager
Handles login, session management, and phone number extraction
"""

import httpx
import re


class ConforamaSession:
    """Session manager for Conforama login with proper cookie and redirect handling"""
    
    def __init__(self):
        self.session = httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",  # Removed 'br' to avoid Brotli compression issues on Windows
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "same-origin",
                "Te": "trailers"
            }
        )
        
    def _get_decoded_content(self, response):
        """Get properly decoded content with Brotli fallback handling"""
        try:
            # Try normal text decoding first
            return response.text
        except Exception:
            # If normal decoding fails, try manual decompression
            content_encoding = response.headers.get('content-encoding', '').lower()
            
            if content_encoding == 'br':
                try:
                    import brotli
                    decompressed = brotli.decompress(response.content)
                    return decompressed.decode('utf-8')
                except ImportError:
                    # Brotli module not available, use replacement decoding
                    return response.content.decode('utf-8', errors='replace')
                except Exception:
                    # Brotli decompression failed, use replacement decoding
                    return response.content.decode('utf-8', errors='replace')
            else:
                # Other encoding or no encoding, use replacement decoding
                return response.content.decode('utf-8', errors='replace')
    
    def get_login_page(self):
        """Get the login page to establish session"""
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
        """Perform login with credentials"""
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
        """Access order history to maintain session"""
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
        """Get customer address page and extract phone number"""
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
        """Extract mobile phone number from HTML content (only numbers starting with 6)"""
        patterns = [
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
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                for match in matches:
                    phone = match
                    if isinstance(phone, tuple):
                        phone = phone[-1]  # Get the last group if it's a tuple
                    
                    # Clean up the phone number
                    phone = re.sub(r'[^\d+]', '', phone)
                    
                    # Only return if it's a mobile number starting with 6
                    if phone and len(phone) >= 9:
                        # Extract the 9-digit number
                        digits = re.search(r'\d{9}', phone)
                        if digits:
                            number = digits.group(0)
                            # Only return if it starts with 6 (mobile)
                            if number.startswith('6'):
                                return number
        
        return None
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
