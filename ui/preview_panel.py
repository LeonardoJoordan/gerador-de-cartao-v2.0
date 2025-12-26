import re
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QComboBox
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QResizeEvent, QPainter, QImage, QTextDocument
from pathlib import Path


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

        # Preview Responsivo
        self.preview = ResizingLabel()
        self.preview.setText("Nenhum modelo selecionado")
        self.preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        # O '1' aqui é importante: diz para o layout que esse widget deve ocupar todo o espaço extra
        layout.addWidget(self.preview, 1)

    def set_preview_text(self, text: str):
        self.preview.setText(text)

    def set_preview_image(self, path: str):
        """Carrega a imagem do disco e exibe no label redimensionada."""
        self.preview.set_image_path(path)

    def set_preview_pixmap(self, pixmap: QPixmap):
        self.preview.set_pixmap_direct(pixmap)

class ResizingLabel(QLabel):
    """QLabel que redimensiona a imagem interna automaticamente mantendo proporção."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(200) # Altura mínima para não sumir
        self._pixmap = None # Guarda a original em alta resolução

    def set_image_path(self, path: str):
        if not path or not Path(path).exists():
            self.setText("Sem imagem")
            self._pixmap = None
            return
        
        self._pixmap = QPixmap(path)
        self._update_view()

    def resizeEvent(self, event: QResizeEvent):
        """Chamado automaticamente quando o tamanho do painel muda."""
        self._update_view()
        super().resizeEvent(event)

    def _update_view(self):
        if self._pixmap and not self._pixmap.isNull():
            # Redimensiona para o tamanho ATUAL do widget
            w = self.width()
            h = self.height()
            
            # KeepAspectRatio garante que cabe dentro sem distorcer
            scaled = self._pixmap.scaled(w, h, 
                                       Qt.AspectRatioMode.KeepAspectRatio, 
                                       Qt.TransformationMode.SmoothTransformation)
            super().setPixmap(scaled)
        elif not self.text():
            self.setText("Sem prévia")

    def set_pixmap_direct(self, pixmap: QPixmap):
        """Define um pixmap diretamente (já carregado ou gerado)."""
        if not pixmap or pixmap.isNull():
            self.setText("Erro na prévia")
            self._pixmap = None
        else:
            self._pixmap = pixmap
            self._update_view()