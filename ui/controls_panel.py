from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton


class ControlsPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.btn_manage_models = QPushButton("Gerenciar modelos")
        self.btn_config_model = QPushButton("Configurar modelo")

        layout.addWidget(self.btn_manage_models)
        layout.addWidget(self.btn_config_model)
        layout.addStretch(1)
