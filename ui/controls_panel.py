# ui/controls_panel.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton


class ControlsPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.btn_add_model = QPushButton("Adicionar modelo")
        self.btn_duplicate_model = QPushButton("Duplicar modelo")
        self.btn_remove_model = QPushButton("Remover modelo")
        
        # [NOVO] Botão de Renomear
        self.btn_rename_model = QPushButton("Renomear modelo")
        
        self.btn_config_model = QPushButton("Configurar modelo")

        layout.addWidget(self.btn_add_model)
        layout.addWidget(self.btn_duplicate_model)
        layout.addWidget(self.btn_remove_model)
        layout.addWidget(self.btn_rename_model) # Inserido aqui
        layout.addWidget(self.btn_config_model)
        