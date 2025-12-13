from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QComboBox
from PySide6.QtCore import Qt


class PreviewPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Título novo
        title = QLabel("Selecione o modelo")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        # ComboBox (modelo ativo)
        self.cbo_models = QComboBox()
        self.cbo_models.setMinimumHeight(34)
        layout.addWidget(self.cbo_models)

        # Preview (mantemos por enquanto)
        self.preview = QLabel("Nenhum modelo selecionado")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(320)
        self.preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        layout.addWidget(self.preview, 1)

    def set_preview_text(self, text: str):
        self.preview.setText(text)
