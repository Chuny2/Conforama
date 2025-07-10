"""
PyQt5 GUI Interface for Conforama Phone Extractor
"""

import sys
import platform
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                            QProgressBar, QSpinBox, QFileDialog, QMessageBox,
                            QTableWidget, QTableWidgetItem, QTabWidget,
                            QGroupBox, QGridLayout, QLineEdit, QCheckBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QTextCursor
from typing import List
import time
import threading

from credential_manager import CredentialManager
from phone_extractor import PhoneExtractor, PhoneResult
import config

# Detect Windows for CPU optimizations
IS_WINDOWS = platform.system() == "Windows"


class ExtractionWorker(QThread):
    progress_updated = pyqtSignal(object, int, int)
    batch_progress_updated = pyqtSignal(list, int, int)
    extraction_finished = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    startup_progress = pyqtSignal(str)
    
    def __init__(self, credentials, max_workers=3, gui_update_batch_size=10, gui_update_interval=0.1):
        super().__init__()
        self.credentials = credentials
        self.max_workers = max_workers
        self.extractor = None
        self.is_stopped = False
        self.total_accounts = len(credentials)
        
        self.result_batch = []
        self.last_update_time = 0
        self.batch_lock = threading.Lock()
        
        # GUI update settings (platform-specific)
        if IS_WINDOWS:
            # More conservative settings for Windows to reduce CPU usage
            self.gui_update_batch_size = gui_update_batch_size * 2  # Larger batches
            self.gui_update_interval = gui_update_interval * 1.5    # Longer intervals
        else:
            # Standard settings for Linux/other systems
            self.gui_update_batch_size = gui_update_batch_size
            self.gui_update_interval = gui_update_interval
    
    def run(self):
        try:
            self.startup_progress.emit("Initializing optimized HTTP clients...")
            
            self.extractor = PhoneExtractor(
                max_workers=self.max_workers,
                callback=self.progress_callback
            )
            
            self.startup_progress.emit("Starting staggered thread execution...")
            
            # For large datasets, show submission progress
            if self.total_accounts > 10000:
                self.startup_progress.emit(f"Submitting {self.total_accounts} tasks in batches...")
            
            self.startup_progress.emit("Extraction started - watching for first results...")
            
            self.extractor.process_accounts_threaded(self.credentials)
            
            if not self.is_stopped:
                self.extraction_finished.emit(self.total_accounts)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def progress_callback(self, result: PhoneResult, completed: int, total: int):
        if self.is_stopped:
            return
            
        current_time = time.time()
        
        # For real-time feedback, send more results immediately
        if completed <= 200:
            # First 200 results always immediate
            self.batch_progress_updated.emit([(result, completed, total)], completed, total)
            return
        
        # For large datasets, continue immediate updates longer for real-time logs
        if total > 50000 and completed <= 1000:
            self.batch_progress_updated.emit([(result, completed, total)], completed, total)
            return
        elif total > 10000 and completed <= 500:
            self.batch_progress_updated.emit([(result, completed, total)], completed, total)
            return
        
        with self.batch_lock:
            self.result_batch.append((result, completed, total))
            
            # More aggressive batching for real-time feedback
            force_early_update = (completed <= 200) or (completed % 10 == 0)
            
            should_update = (
                len(self.result_batch) >= self.gui_update_batch_size or
                current_time - self.last_update_time >= self.gui_update_interval or
                completed == total or
                force_early_update
            )
            
            if should_update:
                batch_copy = self.result_batch.copy()
                self.result_batch.clear()
                self.last_update_time = current_time
                
                self.batch_progress_updated.emit(batch_copy, completed, total)
    
    def stop(self):
        self.is_stopped = True
        if self.extractor:
            self.extractor.stop()


class ConforamaGUI(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.credential_manager = CredentialManager()
        self.extraction_worker = None
        self.credentials = []
        
        self.successful_count = 0
        self.failed_count = 0
        self.banned_count = 0
        
        self.export_data = []
        
        self.pending_table_updates = []
        self.last_table_update_time = 0
        
        self.log_entries = []
        self.is_large_dataset = False
        
        # Instance-specific GUI update settings (platform-aware)
        if IS_WINDOWS:
            # More conservative settings for Windows
            self.gui_update_batch_size = config.GUI_UPDATE_BATCH_SIZE * 2
            self.gui_update_interval = config.GUI_UPDATE_INTERVAL * 2
        else:
            # Standard settings for Linux/other systems
            self.gui_update_batch_size = config.GUI_UPDATE_BATCH_SIZE
            self.gui_update_interval = config.GUI_UPDATE_INTERVAL
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.flush_pending_updates)
        self.update_timer.start(int(self.gui_update_interval * 1000))
        
        self.na_item = "N/A"
        self.success_item = "✅ Success"
        self.banned_item = "🚫 BANNED"
        self.password_masks = {}
        
        self.init_ui()
        self.load_credentials()
    
    def init_ui(self):
        self.setWindowTitle(config.WINDOW_TITLE)
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        tab_widget = QTabWidget()
        
        main_tab = self.create_main_tab()
        tab_widget.addTab(main_tab, "📞 Extractor")
        
        results_tab = self.create_results_tab()
        tab_widget.addTab(results_tab, "📊 Results")
        
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "⚙️ Settings")
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(tab_widget)
        central_widget.setLayout(main_layout)
        
        self.statusBar().showMessage("Ready")
    
    def limit_log_lines(self, max_lines: int = None):
        if max_lines is None:
            # Use platform-specific log limits
            max_lines = config.MAX_LOG_LINES // 2 if IS_WINDOWS else config.MAX_LOG_LINES
            
        document = self.log_text.document()
        
        if document.lineCount() > max_lines:
            lines_to_remove = document.lineCount() - max_lines
            
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            
            for _ in range(lines_to_remove):
                cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
            
            cursor.removeSelectedText()
            
            if cursor.position() > 0:
                cursor.deletePreviousChar()
    
    def add_log_message(self, message: str):
        # For large datasets, show logs more selectively but still in real-time
        if self.is_large_dataset:
            # Show important messages and some failures for real-time feedback
            if any(indicator in message for indicator in ["✅", "🚫", "🚀", "⏹️", "🎉", "⚙️"]):
                # Always show successes, bans, and system messages
                pass
            elif "❌" in message and (self.failed_count % 20 == 0 or self.failed_count < 500):
                # Show every 20th failure for real-time progress indication OR first 500 failures
                pass
            else:
                # Skip routine failure messages to reduce spam
                return
        
        self.log_entries.append(message)
        
        if len(self.log_entries) > config.MAX_LOG_ENTRIES:
            self.log_entries = self.log_entries[-config.MAX_LOG_ENTRIES:]
            
        self.log_text.append(message)
        self.limit_log_lines()
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def create_main_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("🔍 Conforama Phone Number Extractor")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        cred_group = QGroupBox("📝 Credentials")
        cred_layout = QVBoxLayout()
        
        self.cred_info = QLabel("No credentials loaded")
        cred_layout.addWidget(self.cred_info)
        
        load_cred_btn = QPushButton("📂 Load Credentials File")
        load_cred_btn.clicked.connect(self.load_credentials_file)
        cred_layout.addWidget(load_cred_btn)
        
        cred_group.setLayout(cred_layout)
        layout.addWidget(cred_group)
        
        settings_group = QGroupBox("⚙️ Extraction Settings")
        settings_layout = QGridLayout()
        
        settings_layout.addWidget(QLabel("Threads:"), 0, 0)
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, config.MAX_WORKERS_LIMIT)
        self.thread_spinbox.setValue(config.DEFAULT_MAX_WORKERS)
        self.thread_spinbox.setToolTip("Number of concurrent threads. Higher values = faster processing but more server load.\nRecommended: 10-50 for most cases.")
        settings_layout.addWidget(self.thread_spinbox, 0, 1)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Start Extraction")
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }")
        self.start_btn.clicked.connect(self.start_extraction)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 10px; }")
        self.stop_btn.clicked.connect(self.stop_extraction)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        
        progress_group = QGroupBox("📈 Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Ready to start")
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        log_group = QGroupBox("📋 Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        tab.setLayout(layout)
        return tab
    
    def create_results_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("📊 Extraction Results")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Username", "Password", "Phone Number", "Status"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(False)
        self.results_table.setUpdatesEnabled(True)
        
        layout.addWidget(self.results_table)
        
        export_btn = QPushButton("💾 Export Results")
        export_btn.clicked.connect(self.export_results)
        layout.addWidget(export_btn)
        
        self.stats_label = QLabel("No results yet")
        layout.addWidget(self.stats_label)
        
        tab.setLayout(layout)
        return tab
    
    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("⚙️ Settings")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        cred_group = QGroupBox("📁 Credentials File")
        cred_layout = QGridLayout()
        
        cred_layout.addWidget(QLabel("File:"), 0, 0)
        self.cred_file_edit = QLineEdit(config.DEFAULT_CREDENTIALS_FILE)
        cred_layout.addWidget(self.cred_file_edit, 0, 1)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_credentials_file)
        cred_layout.addWidget(browse_btn, 0, 2)
        
        cred_group.setLayout(cred_layout)
        layout.addWidget(cred_group)
        
        advanced_group = QGroupBox("🔧 Advanced")
        advanced_layout = QGridLayout()
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        layout.addStretch()
        
        tab.setLayout(layout)
        return tab
    
    def load_credentials(self):
        try:
            self.credentials = self.credential_manager.get_valid_credentials()
            if self.credentials:
                self.cred_info.setText(f"✅ {len(self.credentials)} accounts loaded")
                self.start_btn.setEnabled(True)
            else:
                self.cred_info.setText("❌ No valid credentials found")
                self.start_btn.setEnabled(False)
        except Exception as e:
            self.cred_info.setText(f"❌ Error loading credentials: {str(e)}")
            self.start_btn.setEnabled(False)
    
    def load_credentials_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Credentials File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self.credential_manager.credentials_file = file_path
            self.cred_file_edit.setText(file_path)
            self.load_credentials()
    
    def browse_credentials_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Credentials File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self.cred_file_edit.setText(file_path)
    
    def start_extraction(self):
        if not self.credentials:
            QMessageBox.warning(self, "Warning", "No credentials loaded!")
            return
        
        credential_count = len(self.credentials)
        self.is_large_dataset = credential_count > config.LARGE_DATASET_THRESHOLD
        
        if self.is_large_dataset:
            self.add_log_message(f"🔍 Large dataset detected ({credential_count} accounts) - Enabling memory optimizations")
            
            # Use reasonable batch sizes that work well on both Windows and Linux
            if credential_count > 50000:
                self.gui_update_batch_size = 5  # Moderate batch size for massive datasets
                self.gui_update_interval = 0.1  # 100ms interval
                self.add_log_message(f"⚙️ Massive dataset - using batch size: {self.gui_update_batch_size}")
            elif credential_count > 10000:
                self.gui_update_batch_size = 8  # Medium batch size for very large datasets
                self.gui_update_interval = 0.12  # 120ms interval
                self.add_log_message(f"⚙️ Very large dataset - using batch size: {self.gui_update_batch_size}")
            else:
                self.gui_update_batch_size = 10  # Normal batch size for large datasets
                self.gui_update_interval = 0.15  # 150ms interval
                self.add_log_message(f"⚙️ Large dataset - using batch size: {self.gui_update_batch_size}")
            
            # Force immediate GUI update after setting parameters
            QApplication.processEvents()
            
            reply = QMessageBox.question(
                self, 
                "Large Dataset Detected", 
                f"You're about to process {credential_count} accounts.\n\n"
                f"Large dataset optimizations will be enabled:\n"
                f"• Reduced logging frequency\n"
                f"• Larger GUI update batches ({self.gui_update_batch_size} items)\n"
                f"• Update interval: {self.gui_update_interval}s\n"
                f"• Memory-efficient processing\n\n"
                f"Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.No:
                return
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setMaximum(len(self.credentials))
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        self.results_table.setRowCount(0)
        self.results_table.setUpdatesEnabled(True)
        self.results_table.setSortingEnabled(False)
        
        self.export_data = []
        self.log_entries = []
        
        self.successful_count = 0
        self.failed_count = 0
        self.banned_count = 0
        
        # Restart timer with new interval if efficient mode is enabled
        if self.is_large_dataset and hasattr(self, 'update_timer'):
            self.update_timer.stop()
            # Use more conservative timer intervals on Windows to prevent CPU spikes
            if credential_count > 50000:
                timer_interval = 200 if IS_WINDOWS else 100  # More conservative on Windows
            else:
                timer_interval = 250 if IS_WINDOWS else 150  # More conservative on Windows
            self.update_timer.start(timer_interval)
            self.add_log_message(f"⚙️ Timer restarted with {timer_interval/1000}s interval")
            if IS_WINDOWS:
                self.add_log_message("⚙️ Windows detected - using CPU-friendly timers")
            self.add_log_message(f"⚙️ Timer active: {self.update_timer.isActive()}")
        else:
            self.add_log_message(f"⚙️ Normal mode - using default timer interval")
        
        max_workers = self.thread_spinbox.value()
        self.extraction_worker = ExtractionWorker(
            self.credentials, 
            max_workers, 
            self.gui_update_batch_size, 
            self.gui_update_interval
        )
        self.extraction_worker.progress_updated.connect(self.on_progress_updated)
        self.extraction_worker.batch_progress_updated.connect(self.on_batch_progress_updated)
        self.extraction_worker.extraction_finished.connect(self.on_extraction_finished)
        self.extraction_worker.error_occurred.connect(self.on_error_occurred)
        self.extraction_worker.startup_progress.connect(self.on_startup_progress)
        self.extraction_worker.start()
        
        # Force immediate processing of pending events
        QApplication.processEvents()
        
        optimization_text = " + memory optimizations" if self.is_large_dataset else ""
        self.add_log_message(f"🚀 Started extraction with {max_workers} threads (optimized startup + batched updates{optimization_text})")
        self.statusBar().showMessage("Initializing optimized extraction...")
        
        # Force immediate GUI update
        if self.is_large_dataset:
            self.add_log_message("⚙️ Large dataset mode active - initializing...")
            self.add_log_message(f"⚙️ Will show updates every {self.gui_update_batch_size} results or {self.gui_update_interval}s")
            QApplication.processEvents()  # Force GUI update
    
    def stop_extraction(self):
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
            
        if self.extraction_worker:
            self.extraction_worker.stop()
            self.extraction_worker.wait()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("Extraction stopped")
        self.add_log_message("⏹️ Extraction stopped by user")
        
        # Reset GUI update settings to default
        self.gui_update_batch_size = config.GUI_UPDATE_BATCH_SIZE
        self.gui_update_interval = config.GUI_UPDATE_INTERVAL
        
        if hasattr(self, 'update_timer'):
            self.update_timer.start(int(self.gui_update_interval * 1000))
    
    def write_phone_immediately(self, phone: str):
        try:
            with open("phones.txt", "a", encoding="utf-8") as f:
                f.write(f"{phone}\n")
            self.add_log_message(f"📱 Phone {phone} written to phones.txt immediately")
        except Exception as e:
            self.add_log_message(f"⚠️ Failed to write phone {phone} to file: {e}")
    
    def get_password_mask(self, password_length: int) -> str:
        if password_length not in self.password_masks:
            self.password_masks[password_length] = "*" * password_length
        return self.password_masks[password_length]
    
    def add_result_to_table(self, result: PhoneResult):
        if not result.success and not result.banned and "Login failed" in result.error:
            return
        
        if self.is_large_dataset and self.results_table.rowCount() >= config.MAX_TABLE_ROWS:
            return
        
        if result.success:
            phone_display = result.phone
            status_display = self.success_item
        elif result.banned:
            phone_display = self.na_item
            status_display = self.banned_item
        else:
            phone_display = self.na_item
            status_display = f"❌ {result.error}"
        
        row_position = self.results_table.rowCount()
        self.results_table.insertRow(row_position)
        self.results_table.setItem(row_position, 0, QTableWidgetItem(result.username))
        self.results_table.setItem(row_position, 1, QTableWidgetItem(self.get_password_mask(len(result.password))))
        self.results_table.setItem(row_position, 2, QTableWidgetItem(phone_display))
        self.results_table.setItem(row_position, 3, QTableWidgetItem(status_display))
    
    def on_progress_updated(self, result: PhoneResult, completed: int, total: int):
        self.progress_bar.setValue(completed)
        self.progress_label.setText(f"Processing {completed}/{total}: {result.username}")
        
        self.add_result_to_table(result)
        
        if result.success:
            self.add_log_message(f"✅ {result.username} -> {result.phone}")
            
            self.write_phone_immediately(result.phone)
            
            self.export_data.append({
                'username': result.username,
                'password': result.password,
                'phone': result.phone
            })
            self.successful_count += 1
        elif result.banned:
            self.add_log_message(f"🚫 {result.username} -> BANNED (401)")
            self.banned_count += 1
        elif result.username == "" and result.password == "":
            # System message - always show
            self.add_log_message(f"⚙️ {result.error}")
        else:
            self.add_log_message(f"❌ {result.username} -> {result.error}")
            self.failed_count += 1
        
        self.update_live_stats(completed, total)
        
        if completed % 10 == 0 or completed == total:
            self.results_table.scrollToBottom()
    
    def on_batch_progress_updated(self, batch_results: List, completed: int, total: int):
        # Disable table updates during batch processing on Windows for better performance
        if IS_WINDOWS and self.is_large_dataset:
            self.results_table.setUpdatesEnabled(False)
            self.results_table.setSortingEnabled(False)
        elif self.is_large_dataset:
            self.results_table.setUpdatesEnabled(False)
            self.results_table.setSortingEnabled(False)
        
        for result, result_completed, result_total in batch_results:
            self.add_result_to_table(result)
            
            if result.success:
                self.add_log_message(f"✅ {result.username} -> {result.phone}")
                
                self.write_phone_immediately(result.phone)
                
                self.export_data.append({
                    'username': result.username,
                    'password': result.password,
                    'phone': result.phone
                })
                self.successful_count += 1
            elif result.banned:
                self.add_log_message(f"🚫 {result.username} -> BANNED (401)")
                self.banned_count += 1
            elif result.username == "" and result.password == "":
                # System message - always show
                self.add_log_message(f"⚙️ {result.error}")
            else:
                # Always call add_log_message - it will handle filtering internally
                self.add_log_message(f"❌ {result.username} -> {result.error}")
                self.failed_count += 1
        
        if self.is_large_dataset:
            self.results_table.setUpdatesEnabled(True)
        
        self.progress_bar.setValue(completed)
        
        if self.is_large_dataset:
            self.progress_label.setText(f"Processing {completed}/{total} ({(completed/total*100):.1f}% complete)")
        else:
            self.progress_label.setText(f"Processing {completed}/{total} (batch of {len(batch_results)} results)")
        
        self.update_live_stats(completed, total)
        
        # Platform-specific scroll frequency optimization
        if IS_WINDOWS:
            scroll_frequency = 100 if self.is_large_dataset else 20  # Less frequent on Windows
        else:
            scroll_frequency = 50 if self.is_large_dataset else 10   # Standard frequency
            
        if completed % scroll_frequency == 0 or completed == total:
            self.results_table.scrollToBottom()
        
        # Force GUI updates more frequently for real-time logs, but less on Windows
        if IS_WINDOWS:
            # On Windows, update GUI less frequently to reduce CPU usage
            if completed % 100 == 0:  # Every 100 results on Windows
                QApplication.processEvents()
        else:
            # On Linux/other systems, more frequent updates are fine
            if completed % 25 == 0:  # Every 25 results on Linux
                QApplication.processEvents()
        
        # Show periodic status updates for large datasets
        if self.is_large_dataset and completed % 2000 == 0:
            self.add_log_message(f"⚙️ Progress: {completed}/{total} ({(completed/total*100):.1f}% complete)")
            # Reduce frequency of processEvents calls on Windows to prevent CPU spikes
            if completed % (8000 if IS_WINDOWS else 4000) == 0:
                QApplication.processEvents()  # Less frequent GUI updates on Windows
    
    def update_live_stats(self, completed: int, total: int):
        success_rate = (self.successful_count / completed * 100) if completed > 0 else 0
        
        stats_text = f"""
📊 Live Statistics
Progress: {completed}/{total} ({(completed/total*100):.1f}%)
✅ Success: {self.successful_count}
❌ Failed: {self.failed_count}
🚫 Banned: {self.banned_count}
Success rate: {success_rate:.1f}%
        """
        
        self.stats_label.setText(stats_text)
    
    def on_extraction_finished(self, total_accounts: int):
        self.flush_pending_updates()
        
        if self.is_large_dataset:
            self.cleanup_memory()
            self.add_log_message(f"🧹 Final cleanup completed for large dataset ({total_accounts} accounts)")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Reset GUI update settings to default
        self.gui_update_batch_size = config.GUI_UPDATE_BATCH_SIZE
        self.gui_update_interval = config.GUI_UPDATE_INTERVAL
        
        self.results_table.setSortingEnabled(True)
        
        stats_text = f"""
📊 Extraction Complete!
Total accounts: {total_accounts}
✅ Success: {self.successful_count}
❌ Failed: {self.failed_count}
🚫 Banned: {self.banned_count}
Success rate: {(self.successful_count/total_accounts*100):.1f}%
        """
        
        if self.is_large_dataset:
            stats_text += f"\n🧹 Memory optimizations were active"
        
        self.stats_label.setText(stats_text)
        self.statusBar().showMessage("Extraction completed")
        self.add_log_message("🎉 Extraction completed!")
        
        self.results_table.scrollToBottom()
        
        completion_msg = f"Extraction completed!\n\n" \
                        f"Found {self.successful_count} phone numbers out of {total_accounts} accounts.\n" \
                        f"Banned accounts: {self.banned_count}"
        
        if self.is_large_dataset:
            completion_msg += f"\n\nLarge dataset optimizations were used to manage {total_accounts} accounts efficiently."
        
        QMessageBox.information(
            self, 
            "Extraction Complete", 
            completion_msg
        )
    
    def on_error_occurred(self, error: str):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("Error occurred")
        self.add_log_message(f"❌ Error: {error}")
        
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error}")
    
    def export_results(self):
        if not self.export_data:
            QMessageBox.warning(self, "Warning", "No results to export!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "results.txt", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                total_results = len(self.export_data)
                
                progress_dialog = None
                if total_results > config.EXPORT_CHUNK_SIZE:
                    progress_dialog = QMessageBox(self)
                    progress_dialog.setWindowTitle("Exporting Results")
                    progress_dialog.setText(f"Exporting {total_results} results...")
                    progress_dialog.setStandardButtons(QMessageBox.NoButton)
                    progress_dialog.show()
                    QApplication.processEvents()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("Conforama Phone Extraction Results\n")
                    f.write("=" * 40 + "\n\n")
                    
                    for i in range(0, total_results, config.EXPORT_CHUNK_SIZE):
                        chunk = self.export_data[i:i + config.EXPORT_CHUNK_SIZE]
                        
                        if progress_dialog:
                            progress_dialog.setText(f"Exporting {i + len(chunk)}/{total_results} results...")
                            QApplication.processEvents()
                        
                        for item in chunk:
                            f.write(f"{item['username']}:{item['password']}:{item['phone']}\n")
                
                if progress_dialog:
                    progress_dialog.close()
                
                QMessageBox.information(
                    self, 
                    "Export Complete", 
                    f"Results exported to {file_path}\n\n"
                    f"Exported {len(self.export_data)} phone numbers."
                )
                
            except Exception as e:
                if progress_dialog:
                    progress_dialog.close()
                QMessageBox.critical(self, "Export Error", f"Failed to export results:\n{str(e)}")
    
    def on_startup_progress(self, message: str):
        self.add_log_message(f"⚙️ {message}")
        self.statusBar().showMessage(message)
        # Force GUI update for startup messages
        QApplication.processEvents()
    
    def flush_pending_updates(self):
        if hasattr(self, 'extraction_worker') and self.extraction_worker and not self.extraction_worker.is_stopped:
            with self.extraction_worker.batch_lock:
                if self.extraction_worker.result_batch:
                    batch_copy = self.extraction_worker.result_batch.copy()
                    self.extraction_worker.result_batch.clear()
                    self.extraction_worker.last_update_time = time.time()
                    
                    if batch_copy:
                        last_result, completed, total = batch_copy[-1]
                        self.on_batch_progress_updated(batch_copy, completed, total)
        
        if self.is_large_dataset:
            self.cleanup_memory()
    
    def cleanup_memory(self):
        if self.is_large_dataset:
            if len(self.export_data) > config.MAX_LOG_ENTRIES:
                self.export_data = self.export_data[-config.MAX_LOG_ENTRIES:]
                self.add_log_message(f"🧹 Memory cleanup: Limited export data to {config.MAX_LOG_ENTRIES} entries")
            
            if len(self.log_entries) > config.MAX_LOG_ENTRIES:
                self.log_entries = self.log_entries[-config.MAX_LOG_ENTRIES//2:]
                self.add_log_message("🧹 Memory cleanup: Cleared old log entries")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Conforama Phone Extractor")
    
    window = ConforamaGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
