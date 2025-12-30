import os
import sys

# --- FIX teclado PT-BR no Qt (Linux) ---
# Ajuda o Qt a lidar corretamente com teclas "dead key" como ~ ´ ^
os.environ.setdefault("QT_IM_MODULE", "ibus")
os.environ.setdefault("GTK_IM_MODULE", "ibus")
os.environ.setdefault("XMODIFIERS", "@im=ibus")

from PySide6.QtWidgets import QApplication
from app_window import MainWindow


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
