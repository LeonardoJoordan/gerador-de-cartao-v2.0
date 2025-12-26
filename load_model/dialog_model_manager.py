from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QIcon, QPainter, QFont


def _make_placeholder_icon(text: str, w: int = 220, h: int = 140) -> QIcon:
    """
    Ícone de preview fake (por enquanto).
    Depois vamos substituir pelo preview real gerado do SVG/template.
    """
    pix = QPixmap(w, h)
    pix.fill(Qt.GlobalColor.black)

    painter = QPainter(pix)
    painter.fillRect(0, 0, w, h, Qt.GlobalColor.darkGray)

    painter.setPen(Qt.GlobalColor.white)
    font = QFont()
    font.setPointSize(10)
    font.setBold(True)
    painter.setFont(font)

    # texto centralizado
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()

    return QIcon(pix)


class ModelManagerDialog(QDialog):
    """
    Diálogo "Gerenciar modelos":
    - Lista de modelos com preview (fake por enquanto)
    - Botões: Adicionar / Duplicar / Excluir
    - Botões finais: Usar selecionado / Fechar

    Etapa atual: UI + comportamento básico (sem persistência ainda).
    """
    def __init__(self, parent=None, initial_models=None):
        super().__init__(parent)
        self.setWindowTitle("Gerenciar modelos")
        self.resize(980, 520)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # -------- ESQUERDA: Lista com previews
        left = QVBoxLayout()
        left.setSpacing(8)

        title = QLabel("Modelos cadastrados")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        left.addWidget(title)

        self.list_models = QListWidget()
        self.list_models.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_models.setSpacing(6)
        self.list_models.setUniformItemSizes(False)
        left.addWidget(self.list_models, 1)

        hint = QLabel("Dica: dê duplo clique para usar o modelo selecionado.")
        hint.setStyleSheet("color: #cfcfcf;")
        left.addWidget(hint)

        root.addLayout(left, 7)

        # -------- DIREITA: Botões de ação
        right = QVBoxLayout()
        right.setSpacing(10)

        action_title = QLabel("Ações")
        action_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        right.addWidget(action_title)

        self.btn_add = QPushButton("Adicionar modelo…")
        self.btn_duplicate = QPushButton("Duplicar modelo")
        self.btn_config_model = QPushButton("Configurar modelo")
        self.btn_delete = QPushButton("Excluir modelo")

        right.addWidget(self.btn_add)
        right.addWidget(self.btn_duplicate)
        right.addWidget(self.btn_config_model)
        right.addWidget(self.btn_delete)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        right.addWidget(line)

        self.btn_use = QPushButton("Usar selecionado")
        self.btn_close = QPushButton("Fechar")

        self.btn_use.setMinimumHeight(42)
        right.addWidget(self.btn_use)
        right.addWidget(self.btn_close)

        right.addStretch(1)

        root.addLayout(right, 3)

        # -------- eventos
        self.btn_close.clicked.connect(self.reject)
        self.btn_use.clicked.connect(self._use_selected)
        self.list_models.itemDoubleClicked.connect(lambda _: self._use_selected())

        self.btn_add.clicked.connect(self._add_model_fake)
        self.btn_duplicate.clicked.connect(self._duplicate_model_fake)
        self.btn_delete.clicked.connect(self._delete_model_fake)

        # -------- carregar modelos iniciais (fake)
        if initial_models is None:
            initial_models = [
                "Cartão Aniversário",
                "Cartão Promoção",
                "Cartão Despedida",
                "Cartão Boas-vindas",
                "Cartão Condolências",
            ]

        for name in initial_models:
            self._add_list_item(name)

        if self.list_models.count() > 0:
            self.list_models.setCurrentRow(0)

        self.selected_model_name = None  # setado quando o usuário clicar "Usar selecionado"
        self.btn_config_model.clicked.connect(self._open_model_config)


    def _add_list_item(self, name: str):
        item = QListWidgetItem()
        item.setText(name)
        item.setIcon(_make_placeholder_icon(name))
        item.setSizeHint(item.sizeHint().expandedTo(QSize(260, 90)))
        self.list_models.addItem(item)

    def _get_selected_item(self):
        items = self.list_models.selectedItems()
        return items[0] if items else None

    def _use_selected(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.information(self, "Atenção", "Selecione um modelo na lista.")
            return
        self.selected_model_name = item.text()
        self.accept()

    # ---------- ações fake (Etapa 1 do gerenciador)
    def _add_model_fake(self):
        # Por enquanto, só cria um modelo genérico.
        # Depois: abrir QFileDialog -> importar SVG -> abrir Configurar Modelo -> salvar template.
        new_name = f"Novo Modelo {self.list_models.count() + 1}"
        self._add_list_item(new_name)
        self.list_models.setCurrentRow(self.list_models.count() - 1)

    def _duplicate_model_fake(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.information(self, "Atenção", "Selecione um modelo para duplicar.")
            return
        base = item.text()
        copy_name = f"{base} (cópia)"
        self._add_list_item(copy_name)
        self.list_models.setCurrentRow(self.list_models.count() - 1)

    def _delete_model_fake(self):
        row = self.list_models.currentRow()
        if row < 0:
            QMessageBox.information(self, "Atenção", "Selecione um modelo para excluir.")
            return

        name = self.list_models.item(row).text()
        resp = QMessageBox.question(
            self,
            "Confirmar exclusão",
            f"Tem certeza que deseja excluir o modelo:\n\n{name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.list_models.takeItem(row)
            if self.list_models.count() > 0:
                self.list_models.setCurrentRow(min(row, self.list_models.count() - 1))

    def _open_model_config(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.information(self, "Atenção", "Selecione um modelo para configurar.")
            return

        selected_model = item.text()
        self.accept() # Fecha o gerenciador

        # Abre o Editor Visual (novo fluxo)
        from ui.editor.editor_window import EditorWindow
        self.editor_ptr = EditorWindow(self.parent())
        self.editor_ptr.show()

