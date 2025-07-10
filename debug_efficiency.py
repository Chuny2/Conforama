#!/usr/bin/env python3
"""
Debug script to test the efficiency mode
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from credential_manager import CredentialManager
import config

def test_credential_loading():
    print("Testing credential loading...")
    
    # Test loading credentials
    credential_manager = CredentialManager()
    
    try:
        credentials = credential_manager.get_valid_credentials()
        print(f"Loaded {len(credentials)} credentials")
        
        # Test threshold
        is_large = len(credentials) > config.LARGE_DATASET_THRESHOLD
        print(f"Large dataset threshold: {config.LARGE_DATASET_THRESHOLD}")
        print(f"Is large dataset: {is_large}")
        
        if is_large:
            batch_size = max(5, min(50, len(credentials) // 20))
            print(f"Calculated batch size: {batch_size}")
            
            if len(credentials) > 10000:
                batch_size = min(25, len(credentials) // 100)
                print(f"Very large dataset - adjusted batch size: {batch_size}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_credential_loading()
