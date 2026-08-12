 
 
'''
this module contains the main tool class and the main function to run the tool.
main purpose of this module is to implement UART COM send and receive functions via pqt5.
copyright (c) 2026 by oushaojun
'''
 
 
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import inspect
import os
import sys
import threading
import serial
import serial.tools.list_ports
import time
from datetime import datetime
from html import escape
 
_log_lock = threading.Lock()
 
def _log(message: str):
    # timestamp with milliseconds
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    caller = inspect.stack()[1]
    caller_filename = os.path.basename(caller.filename)
    caller_lineno = caller.lineno
    caller_func = caller.function
    with _log_lock:
        prefix = f"[{timestamp}] [{caller_filename}:{caller_lineno:04d}] {caller_func}()"
        print(f" {prefix} - {message}")
 
class SettingsDialog(QDialog):
    reopen_serial_port_signal = pyqtSignal()
 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 200)
        self.init_ui()
        self.setWindowModality(Qt.ApplicationModal)
 
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
 
        # Create a form layout for the settings
        form_layout = QFormLayout()
        layout.addLayout(form_layout)
 
        # Add a line edit for the COM port
        self.port_combo = QComboBox()
        ports = serial.tools.list_ports.comports()
        self.port_combo.addItems([port.device for port in ports])
        form_layout.addRow("COM Port:", self.port_combo)
 
        # Add a combo box for the baud rate
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        form_layout.addRow("Baudrate:", self.baudrate_combo)
 
        # Add a combo box for the parity
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["N", "E", "O", "M", "S"])
        form_layout.addRow("Parity:", self.parity_combo)
 
        # Add a combo box for the stop bits
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])
        form_layout.addRow("Stop Bits:", self.stopbits_combo)
 
        # Add OK and Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
 
    def accept(self):
        # Save the settings when the dialog is accepted
        self.parent().com_config["port"] = self.port_combo.currentText()
        self.parent().com_config["baudrate"] = int(self.baudrate_combo.currentText())
        self.parent().com_config["parity"] = self.parity_combo.currentText()
        self.parent().com_config["stopbits"] = int(self.stopbits_combo.currentText())
        self.parent().save_settings()
        self.reopen_serial_port_signal.emit()
        _log(f"Settings updated: {self.parent().com_config}")
        super().accept()
 
    def reject(self):
        # Discard changes when the dialog is rejected
        _log("Settings changes discarded.")
        super().reject()
 
 
class SerialReadWorker(QObject):
    message_received = pyqtSignal(bytes)
 
    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.running = True
 
    @pyqtSlot()
    def run(self):
        _log("Serial read thread started.")
        while self.running:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    message = self.serial_port.readline()
                    if message:
                        self.message_received.emit(message)
            except Exception:
                # ignore transient serial errors during read
                pass
            time.sleep(0.05)  # Reduced sleep time to improve responsiveness
 
    @pyqtSlot()
    def update_serial_port(self, serial_port):
        _log("Serial port updated in read thread.")
        self.serial_port = serial_port
 
    @pyqtSlot()
    def stop(self):
        _log("Serial read thread stopping.")
        self.running = False
 
 
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_settings()    #call first to create variable self.com_config
        self.setWindowTitle("UART COM Tool")
        self.resize(1200, 600)
        self.init_ui()
        self.init_menu()
        self.open_serial_port()
 
    def open_serial_port(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        try:
            if hasattr(self, 'serial_port') and self.serial_port.is_open:
                self.serial_port.close()
                _log(f"Closed serial port: {self.com_config['port']}")
            
            self.serial_port = serial.Serial(self.com_config["port"], 
                                             self.com_config["baudrate"], 
                                             parity=self.com_config["parity"], 
                                             stopbits=self.com_config["stopbits"], 
                                             timeout=0.05)    #timeout=0.05 to avoid blocking read
            _log(f"Opened serial port: {self.com_config['port']} at {self.com_config['baudrate']} baud.")
        except serial.SerialException as e:
            _log(f"Error opening serial port: {e}")
            self.append_output(f"[{timestamp}] Error opening serial port: {e}", color="#BB0000")
        else:
            # Start a thread to read from the serial port
            if not hasattr(self, 'read_thread') or not self.read_thread.isRunning():
                self.read_thread = QThread()
                self.read_worker = SerialReadWorker(self.serial_port)
                self.read_worker.moveToThread(self.read_thread)
                self.read_thread.started.connect(self.read_worker.run)
                self.read_thread.finished.connect(self.read_worker.stop)
                self.read_worker.message_received.connect(self.handle_received_message)
                self.read_thread.start()
                _log("Started serial read thread.")
            else:
                if hasattr(self, 'read_worker') and self.read_worker is not None:
                    self.read_worker.update_serial_port(self.serial_port)
                _log("Serial read thread is already running.")
            self.append_output(f"\r\n[{timestamp}] Opened serial port: {self.com_config['port']} at {self.com_config['baudrate']} baudrate.", color="#BB0000")
            self.update_status_bar()
 
    def handle_received_message(self, message):
        _log(f"Received message({len(message)}): {message} hex:{message.hex().upper()}")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        msg = r'\x' + message.hex().lower() if self.output_hex_check.isChecked() else message.decode(errors='replace')
        self.append_output(
            f"[{timestamp}] Received({len(message)}): {msg}",
            color="#007700"
        )
 
    def append_output(self, text, color=None):
        if color:
            safe_text = escape(text, quote=False)
            self.output_text_edit.moveCursor(QTextCursor.End)
            self.output_text_edit.insertHtml(f"<span style=\"color:{color};\">{safe_text}</span><br>")
            self.output_text_edit.moveCursor(QTextCursor.End)
        else:
            self.output_text_edit.append(text)
 
    def init_settings(self):
        # Load settings from QSettings
        self.settings = QSettings("config.ini", QSettings.IniFormat)
        self.load_settings()
 
    def init_ui(self):
        # Create a central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
 
        # Create a layout for the central widget
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
 
        # Add a label to the layout
        label = QLabel("Output Message:")
        label.setAlignment(Qt.AlignLeft)
        layout.addWidget(label)
 
        #add a text edit to the layout to show the output message
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        layout.addWidget(self.output_text_edit)
        self.output_hex_check = QCheckBox("Hex Output")
        self.output_hex_check.setMinimumHeight(30)
        self.output_hex_check.setChecked(False)
        layout.addWidget(self.output_hex_check)
 
        #add a label to the layout
        label2 = QLabel("Input Message:")
        label2.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        layout.addWidget(label2)
 
        #add a text edit to the layout to input the message to send
        self.input_text_edit = QLineEdit()
        self.input_text_edit.setFixedHeight(25)
        layout.addWidget(self.input_text_edit)
 
        #add a button to the layout to send the message
        hbox = QHBoxLayout()
        self.hex_check = QCheckBox("Hex Input")
        self.hex_check.setChecked(False)
        hbox.addWidget(self.hex_check)
        hbox.addStretch()
        self.send_button = QPushButton("Send")
        self.send_button.setFixedHeight(30)
        self.send_button.setFixedWidth(100)
        self.send_button.clicked.connect(self.send_message)
        hbox.addWidget(self.send_button)
        layout.addLayout(hbox)
 
        #status bar to show the current COM port and baudrate
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_bar = QStatusBar()
        self.status_bar.addPermanentWidget(self.status_label, 1)
        self.status_label.setText(
            f"COM Port: {self.com_config['port']} {'Opened' if hasattr(self, 'serial_port') and self.serial_port.is_open else 'Closed'}, Baudrate: {self.com_config['baudrate']}, Parity: {self.com_config['parity']}, Stop Bits: {self.com_config['stopbits']}"
        )
        self.setStatusBar(self.status_bar)
 
    def send_message(self):
        # Get the message from the input text edit
        message = self.input_text_edit.text()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        if not message:
            _log("No message to send.")
            return
 
        # Send the message via the configured COM port and baudrate
        try:
            if not hasattr(self, 'serial_port') or not self.serial_port.is_open:
                _log("Serial port is not open. Attempting to open it.")
                self.open_serial_port()
                if not self.serial_port.is_open:
                    _log("Failed to open serial port. Cannot send message.")
                    self.append_output(f"[{timestamp}] Error: Serial port is not open.", color="#BB0000")
                    return
            
            if self.hex_check.isChecked() and all(c in "0123456789abcdefABCDEF" for c in message.replace(" ", "")) and len(message.replace(" ", "")) % 2 == 0:
                _log("hex string")
                message = bytes.fromhex(message)
            elif self.hex_check.isChecked():
                _log("Invalid hex input. Please enter a valid hex string.")
                self.append_output(f"[{timestamp}] Error: Invalid hex input.", color="#BB0000")
                return
            elif not self.hex_check.isChecked() and isinstance(message, str):
                _log("normal string")
                message = message.encode()
 
            self.serial_port.write(message)
            _log(f"Sent message({len(message)}): {message} hex:{message.hex().upper()}")
            msg = r'\x' + message.hex().lower() if self.output_hex_check.isChecked() else message.decode(errors='replace')
            self.append_output(
                f"[{timestamp}] Sent({len(message)}): {msg}",
                color="#0000BB"
            )
        except serial.SerialException as e:
            _log(f"Error sending message: {e}")
            self.append_output(f"[{timestamp}] Error: {e}", color="#BB0000")
            self.reopen_serial_port()
        else:
            # Clear the input text edit after sending
            #self.input_text_edit.clear()
            pass
 
    def reopen_serial_port(self):
        _log("Reopening serial port with updated settings.")
        self.open_serial_port()
        self.update_status_bar()
 
    def update_status_bar(self):
        self.status_label.setText(
            f"COM Port: {self.com_config['port']} {'Opened' if hasattr(self, 'serial_port') and self.serial_port.is_open else 'Closed'}, Baudrate: {self.com_config['baudrate']}, Parity: {self.com_config['parity']}, Stop Bits: {self.com_config['stopbits']}"
        )
        _log(f"Status bar updated: COM Port: {self.com_config['port']} {'Opened' if hasattr(self, 'serial_port') and self.serial_port.is_open else 'Closed'}, Baudrate: {self.com_config['baudrate']}, Parity: {self.com_config['parity']}, Stop Bits: {self.com_config['stopbits']}")
 
    def init_menu(self):
        # Create a menu bar
        menu_bar = self.menuBar()
 
        # menu bar contains two sub-menus: "File" and "Config"
        file_menu = menu_bar.addMenu("File")
        config_menu = menu_bar.addMenu("Settings")
        info_menu = menu_bar.addMenu("Info")
 
        # exit action to close the application
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
 
        # info action to show the tool information
        info_action = QAction("Info", self)
        info_action.triggered.connect(self.show_info)
 
        # save output message to a file action
        save_action = QAction("Save output", self)
        save_action.triggered.connect(self.save_output_to_file)
 
        #clear output message action
        clear_action = QAction("Clear output", self)
        clear_action.triggered.connect(self.output_text_edit.clear)
 
        #close comport action
        close_action = QAction("Close COM port", self)
        close_action.triggered.connect(self.close_serial_port)
 
        # add the exit action to the file menu
        file_menu.addAction(save_action)
        file_menu.addAction(clear_action)
        file_menu.addAction(close_action)
        file_menu.addAction(exit_action)
        file_menu.addSeparator()
 
        # add the settings action to the config menu
        config_menu.addAction("settings")
        config_menu.triggered.connect(self.open_settings_dialog)
 
        # info menu action to show the tool information
        info_menu.addAction(info_action)
 
    def close_serial_port(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        try:
            if hasattr(self, 'serial_port') and self.serial_port.is_open:
                self.serial_port.close()
                _log(f"Closed serial port: {self.com_config['port']}")
                self.append_output(f"[{timestamp}] Closed serial port: {self.com_config['port']}", color="#BB0000")
            else:
                _log("Serial port is already closed.")
                self.append_output(f"[{timestamp}] Serial port is already closed.", color="#BB0000")
        except Exception as e:
            _log(f"Error closing serial port: {e}")
            self.append_output(f"[{timestamp}] Error closing serial port: {e}", color="#BB0000")
        self.update_status_bar()
 
    def save_output_to_file(self):
        # Open a file dialog to select the file to save the output message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        filename = f"{timestamp.replace(' ', '_').replace(':', '-')}_{self.com_config['port']}.txt"
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Output Message", filename, "Text Files (*.txt);;All Files (*)", options=options)
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(self.output_text_edit.toPlainText())
                _log(f"Output message saved to {file_name}")
            except Exception as e:
                _log(f"Error saving output message: {e}")
                self.append_output(f"[{timestamp}] Error saving output message: {e}", color="#BB0000")
 
    def load_settings(self):
 
        ports = serial.tools.list_ports.comports()
        _log(f"Available COM ports: {[port.device for port in ports]}")
        if os.name == 'nt':
            # Windows: Use the first available COM port or default to COM1
            default_port = ports[0].device if ports else "COM1"
        elif os.name == 'posix':
            # Linux: Use the first available /dev/ttyUSB* or /dev/ttyS* port or default to /dev/ttyUSB0
            default_port = next((port.device for port in ports if port.device.startswith("/dev/ttyUSB") or port.device.startswith("/dev/ttyS")), "/dev/ttyUSB0")
        else:
            # Other OS: Default to COM1
            default_port = "COM1"
 
        self.com_config = {
            "port": self.settings.value("port", default_port),
            "baudrate": int(self.settings.value("baudrate", 115200)),
            "parity": self.settings.value("parity", "N"),
            "stopbits": int(self.settings.value("stopbits", 1)),
        }
        _log(f"Loaded settings: {self.com_config}")
 
    def save_settings(self):
        self.settings.setValue("port", self.com_config["port"])
        self.settings.setValue("baudrate", self.com_config["baudrate"])
        self.settings.setValue("parity", self.com_config["parity"])
        self.settings.setValue("stopbits", self.com_config["stopbits"])
        self.settings.sync()
        _log(f"Saved settings: {self.com_config}")
 
    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.port_combo.setCurrentText(self.com_config["port"])
        dialog.baudrate_combo.setCurrentText(str(self.com_config["baudrate"]))
        dialog.parity_combo.setCurrentText(self.com_config["parity"])
        dialog.stopbits_combo.setCurrentText(str(self.com_config["stopbits"]))
        dialog.reopen_serial_port_signal.connect(self.reopen_serial_port)
        dialog.exec_()
        self.update_status_bar()
 
    def closeEvent(self, event):
        # Save settings when the application is closed
        self.save_settings()
        if hasattr(self, 'read_thread') and self.read_thread is not None and self.read_thread.isRunning():
            try:
                # ask the worker to stop and quit the thread
                if hasattr(self, 'read_worker') and self.read_worker is not None:
                    self.read_worker.stop()
                self.read_thread.quit()
                self.read_thread.wait()
            except Exception:
                pass
        _log("Application closed. Settings saved.")
        event.accept()
 
    def show_info(self):
        # Show a custom info dialog with a fixed minimum size
        dialog = QDialog(self)
        dialog.setWindowTitle("Info")
        dialog.setMinimumSize(500, 200)
 
        layout = QVBoxLayout(dialog)
 
        title_label = QLabel(f"UART COM Tool\nVersion 1.0\nCopyright (C) 2026 by oushaojun \nBuild Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\npython version: {sys.version.split()[0]}\n")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
 
        info_label = QLabel("This tool is used for sending and receiving data via UART COM ports.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
 
        details_edit = QTextEdit()
        details_edit.setReadOnly(True)
        details_edit.setPlainText(
            "This tool is implemented using PyQt5 and provides a simple GUI for UART communication. "
            "It allows users to configure COM port settings, send data, and receive data in real-time."
        )
        details_edit.setMinimumHeight(200)
        layout.addWidget(details_edit)
 
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
 
        dialog.exec_()
 
 
 
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QApplication.style().standardIcon(QStyle.SP_ComputerIcon))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 