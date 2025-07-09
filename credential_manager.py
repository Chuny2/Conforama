"""
Credential Management Module
Handles reading and processing credentials from files
"""

import os
from typing import List, Tuple


class CredentialManager:
    """Manages credential loading and validation"""
    
    def __init__(self, credentials_file: str = "read.txt"):
        self.credentials_file = credentials_file
    
    def read_credentials(self) -> List[Tuple[str, str]]:
        """Read credentials from file"""
        credentials = []
        
        if not os.path.exists(self.credentials_file):
            print(f"❌ {self.credentials_file} file not found!")
            return []
        
        try:
            with open(self.credentials_file, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if line and ':' in line:
                        try:
                            username, password = line.split(':', 1)
                            credentials.append((username.strip(), password.strip()))
                        except ValueError:
                            print(f"⚠️ Invalid format on line {line_num}: {line}")
                            continue
        except Exception as e:
            print(f"❌ Error reading credentials: {e}")
            return []
        
        return credentials
    
    def validate_credentials(self, credentials: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Validate credential format"""
        valid_credentials = []
        
        for username, password in credentials:
            if not username or not password:
                print(f"⚠️ Skipping invalid credential: {username}:{password}")
                continue
            
            if '@' not in username:
                print(f"⚠️ Invalid email format: {username}")
                continue
            
            valid_credentials.append((username, password))
        
        return valid_credentials
    
    def get_valid_credentials(self) -> List[Tuple[str, str]]:
        """Get all valid credentials from file"""
        raw_credentials = self.read_credentials()
        return self.validate_credentials(raw_credentials)
