import sys
from PyQt5.QtWidgets import QApplication, QWidget
app = QApplication(sys.argv)
w = QWidget()
w.setWindowTitle("TEST WINDOW")
w.resize(400, 300)
w.show()
print("Window shown, loop starting...")
sys.exit(app.exec_())
