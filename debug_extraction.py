#!/usr/bin/env python3
"""
Minimal test to debug extraction worker
"""
import sys
import time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread, pyqtSignal

# Import our modules
from credential_manager import CredentialManager
from phone_extractor import PhoneExtractor, PhoneResult

class SimpleExtractionWorker(QThread):
    progress_signal = pyqtSignal(str)
    
    def __init__(self, credentials):
        super().__init__()
        self.credentials = credentials[:5]  # Only test first 5 credentials
        
    def run(self):
        self.progress_signal.emit("Starting extraction test...")
        
        def progress_callback(result: PhoneResult, completed: int, total: int):
            self.progress_signal.emit(f"Result {completed}/{total}: {result.username} -> {result.success}")
        
        try:
            extractor = PhoneExtractor(max_workers=2, callback=progress_callback)
            self.progress_signal.emit("PhoneExtractor created successfully")
            
            extractor.process_accounts_threaded(self.credentials)
            self.progress_signal.emit("Extraction completed")
            
        except Exception as e:
            self.progress_signal.emit(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()

def main():
    app = QApplication(sys.argv)
    
    # Load credentials
    cred_manager = CredentialManager()
    credentials = cred_manager.get_valid_credentials()
    
    print(f"Loaded {len(credentials)} credentials")
    
    if not credentials:
        print("No credentials loaded, exiting")
        return
    
    # Create worker
    worker = SimpleExtractionWorker(credentials)
    worker.progress_signal.connect(lambda msg: print(f"Progress: {msg}"))
    worker.finished.connect(app.quit)
    
    # Start worker
    worker.start()
    
    # Run for max 30 seconds
    import threading
    def timeout():
        time.sleep(30)
        print("Timeout reached, stopping")
        app.quit()
    
    timeout_thread = threading.Thread(target=timeout)
    timeout_thread.daemon = True
    timeout_thread.start()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
