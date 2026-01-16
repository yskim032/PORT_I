import sys
from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt5.QtWidgets import QApplication
try:
    print(f"Python version: {sys.version}")
    print(f"PyQt version: {PYQT_VERSION_STR}")
    print(f"Qt version: {QT_VERSION_STR}")
    app = QApplication(sys.argv)
    print(f"Platform: {app.platformName()}")
    print(f"Active window: {app.activeWindow()}")
except Exception as e:
    print(f"ERROR: {e}")
