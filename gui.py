"""
PyQt5 GUI Interface for Conforama Phone Extractor
"""

import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                            QProgressBar, QSpinBox, QFileDialog, QMessageBox,
                            QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
                            QGroupBox, QGridLayout, QLineEdit, QCheckBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap
import threading
from typing import List

from credential_manager import CredentialManager
from phone_extractor import PhoneExtractor, PhoneResult
import config


class ExtractionWorker(QThread):
    """Worker thread for phone extraction"""
    progress_updated = pyqtSignal(object, int, int)  # result, completed, total
    extraction_finished = pyqtSignal(list)  # results
    error_occurred = pyqtSignal(str)  # error message
    
    def __init__(self, credentials, max_workers=3):
        super().__init__()
        self.credentials = credentials
        self.max_workers = max_workers
        self.extractor = None
        self.is_stopped = False
    
    def run(self):
        """Run the extraction process"""
        try:
            # Create extractor with callback
            self.extractor = PhoneExtractor(
                max_workers=self.max_workers,
                callback=self.progress_callback
            )
            
            # Process accounts
            results = self.extractor.process_accounts_threaded(self.credentials)
            
            if not self.is_stopped:
                self.extraction_finished.emit(results)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def progress_callback(self, result: PhoneResult, completed: int, total: int):
        """Callback for progress updates"""
        if not self.is_stopped:
            self.progress_updated.emit(result, completed, total)
    
    def stop(self):
        """Stop the extraction process"""
        self.is_stopped = True
        if self.extractor:
            self.extractor.stop()


class ConforamaGUI(QMainWindow):
    """Main GUI window for Conforama Phone Extractor"""
    
    def __init__(self):
        super().__init__()
        self.credential_manager = CredentialManager()
        self.extraction_worker = None
        self.results = []
        self.credentials = []
        self.phone_buffer = []  # Buffer for batch writing phones
        
        self.init_ui()
        self.load_credentials()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle(config.WINDOW_TITLE)
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Main tab
        main_tab = self.create_main_tab()
        tab_widget.addTab(main_tab, "📞 Extractor")
        
        # Results tab
        results_tab = self.create_results_tab()
        tab_widget.addTab(results_tab, "📊 Results")
        
        # Settings tab
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "⚙️ Settings")
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(tab_widget)
        central_widget.setLayout(main_layout)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def create_main_tab(self):
        """Create the main extraction tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🔍 Conforama Phone Number Extractor")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Credentials section
        cred_group = QGroupBox("📝 Credentials")
        cred_layout = QVBoxLayout()
        
        # Credentials info
        self.cred_info = QLabel("No credentials loaded")
        cred_layout.addWidget(self.cred_info)
        
        # Load credentials button
        load_cred_btn = QPushButton("📂 Load Credentials File")
        load_cred_btn.clicked.connect(self.load_credentials_file)
        cred_layout.addWidget(load_cred_btn)
        
        cred_group.setLayout(cred_layout)
        layout.addWidget(cred_group)
        
        # Settings section
        settings_group = QGroupBox("⚙️ Extraction Settings")
        settings_layout = QGridLayout()
        
        # Thread count
        settings_layout.addWidget(QLabel("Threads:"), 0, 0)
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, config.MAX_WORKERS_LIMIT)
        self.thread_spinbox.setValue(config.DEFAULT_MAX_WORKERS)
        settings_layout.addWidget(self.thread_spinbox, 0, 1)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Control buttons
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
        
        # Progress section
        progress_group = QGroupBox("📈 Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Ready to start")
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Log section
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
        """Create the results tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📊 Extraction Results")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Username", "Password", "Phone Number", "Status"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)
        
        # Export button
        export_btn = QPushButton("💾 Export Results")
        export_btn.clicked.connect(self.export_results)
        layout.addWidget(export_btn)
        
        # Statistics
        self.stats_label = QLabel("No results yet")
        layout.addWidget(self.stats_label)
        
        tab.setLayout(layout)
        return tab
    
    def create_settings_tab(self):
        """Create the settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("⚙️ Settings")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Credentials file setting
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
        
        # Advanced settings
        advanced_group = QGroupBox("🔧 Advanced")
        advanced_layout = QGridLayout()
        
        advanced_layout.addWidget(QLabel("Max Workers:"), 0, 0)
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(1, config.MAX_WORKERS_LIMIT)
        self.max_workers_spin.setValue(config.DEFAULT_MAX_WORKERS)
        advanced_layout.addWidget(self.max_workers_spin, 0, 1)
        
        self.mobile_only_check = QCheckBox("Mobile numbers only (6xxxxxxxx)")
        self.mobile_only_check.setChecked(True)
        advanced_layout.addWidget(self.mobile_only_check, 1, 0, 1, 2)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # Spacer
        layout.addStretch()
        
        tab.setLayout(layout)
        return tab
    
    def load_credentials(self):
        """Load credentials from file"""
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
        """Load credentials from selected file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Credentials File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self.credential_manager.credentials_file = file_path
            self.cred_file_edit.setText(file_path)
            self.load_credentials()
    
    def browse_credentials_file(self):
        """Browse for credentials file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Credentials File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self.cred_file_edit.setText(file_path)
    
    def start_extraction(self):
        """Start the extraction process"""
        if not self.credentials:
            QMessageBox.warning(self, "Warning", "No credentials loaded!")
            return
        
        # Update UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setMaximum(len(self.credentials))
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        # Clear results table
        self.results_table.setRowCount(0)
        self.results = []
        self.phone_buffer = []  # Clear phone buffer for new session
        
        # Start worker thread
        max_workers = self.thread_spinbox.value()
        self.extraction_worker = ExtractionWorker(self.credentials, max_workers)
        self.extraction_worker.progress_updated.connect(self.on_progress_updated)
        self.extraction_worker.extraction_finished.connect(self.on_extraction_finished)
        self.extraction_worker.error_occurred.connect(self.on_error_occurred)
        self.extraction_worker.start()
        
        self.log_text.append(f"🚀 Started extraction with {max_workers} threads")
        self.statusBar().showMessage("Extraction in progress...")
    
    def stop_extraction(self):
        """Stop the extraction process"""
        if self.extraction_worker:
            self.extraction_worker.stop()
            self.extraction_worker.wait()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("Extraction stopped")
        self.log_text.append("⏹️ Extraction stopped by user")
        
        # Batch write any phones collected before stopping
        if self.phone_buffer:
            self.batch_write_phones()
    
    def on_progress_updated(self, result: PhoneResult, completed: int, total: int):
        """Handle progress updates"""
        self.progress_bar.setValue(completed)
        self.progress_label.setText(f"Processing {completed}/{total}: {result.username}")
        
        # Add to results table
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        self.results_table.setItem(row, 0, QTableWidgetItem(result.username))
        self.results_table.setItem(row, 1, QTableWidgetItem("*" * len(result.password)))  # Mask password
        
        if result.success:
            self.results_table.setItem(row, 2, QTableWidgetItem(result.phone))
            self.results_table.setItem(row, 3, QTableWidgetItem("✅ Success"))
            self.log_text.append(f"✅ {result.username} -> {result.phone}")
            
            # Add phone to buffer for batch writing
            self.phone_buffer.append(result.phone)
        else:
            self.results_table.setItem(row, 2, QTableWidgetItem("N/A"))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"❌ {result.error}"))
            self.log_text.append(f"❌ {result.username} -> {result.error}")
        
        # Auto-scroll to bottom
        self.log_text.moveCursor(self.log_text.textCursor().End)
        self.results_table.scrollToBottom()
    
    def on_extraction_finished(self, results: List[PhoneResult]):
        """Handle extraction completion"""
        self.results = results
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Update statistics
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        stats_text = f"""
📊 Extraction Complete!
Total accounts: {len(results)}
✅ Success: {len(successful)}
❌ Failed: {len(failed)}
Success rate: {(len(successful)/len(results)*100):.1f}%
        """
        
        self.stats_label.setText(stats_text)
        self.statusBar().showMessage("Extraction completed")
        self.log_text.append("🎉 Extraction completed!")
        
        # Batch write all phones to file
        self.batch_write_phones()
        
        # Show completion message
        QMessageBox.information(
            self, 
            "Extraction Complete", 
            f"Extraction completed!\n\n"
            f"Found {len(successful)} phone numbers out of {len(results)} accounts."
        )
    
    def batch_write_phones(self):
        """Batch write all collected phone numbers to phones.txt"""
        if not self.phone_buffer:
            return
            
        try:
            with open("phones.txt", "a", encoding="utf-8") as f:
                for phone in self.phone_buffer:
                    f.write(f"{phone}\n")
            
            self.log_text.append(f"📱 Appended {len(self.phone_buffer)} phone numbers to phones.txt")
            
        except Exception as e:
            self.log_text.append(f"⚠️ Failed to save phones to file: {e}")
            
        finally:
            self.phone_buffer.clear()  # Clear buffer after writing
    
    def on_error_occurred(self, error: str):
        """Handle errors"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("Error occurred")
        self.log_text.append(f"❌ Error: {error}")
        
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error}")
    
    def export_results(self):
        """Export results to file"""
        if not self.results:
            QMessageBox.warning(self, "Warning", "No results to export!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "results.txt", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                successful_results = [r for r in self.results if r.success]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("Conforama Phone Extraction Results\n")
                    f.write("=" * 40 + "\n\n")
                    
                    for result in successful_results:
                        f.write(f"{result.username}:{result.password}:{result.phone}\n")
                
                QMessageBox.information(
                    self, 
                    "Export Complete", 
                    f"Results exported to {file_path}\n\n"
                    f"Exported {len(successful_results)} phone numbers."
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export results:\n{str(e)}")


def main():
    """Main function to run the GUI"""
    app = QApplication(sys.argv)
    app.setApplicationName("Conforama Phone Extractor")
    
    # Create and show the main window
    window = ConforamaGUI()
    window.show()
    
    # Run the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
