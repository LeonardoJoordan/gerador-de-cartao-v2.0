from dataclasses import dataclass
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QWidget, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt


@dataclass
class DetectedLayer:
    element_id: str
    text_preview: str
    tag: str
    font_family: str
    font_size: str


class ModelConfigDialog(QDialog):
    """
    Etapa 1 (UI pura): mostra um diálogo único com uma tabela de "camadas detectadas" FAKE,
    só pra validar o layout e o fluxo de marcação de campos variáveis.

    Etapa 2: vamos substituir o fake por análise real do SVG.
    """
    def __init__(self, parent=None, initial_model_name=None):
        super().__init__(parent)
        self.selected_model_name = initial_model_name
        self.output_pattern = ""  # vamos preencher ao salvar
        self.setWindowTitle("Configurar Modelo")
        self.resize(1100, 650)

        self._loaded_svg_path = None
        self._detected: list[DetectedLayer] = []

        self.selected_model_name = initial_model_name

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ---------- ESQUERDA (preview + infos + botões)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        title = QLabel("Modelo")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        left_layout.addWidget(title)

        self.preview = QLabel("Pré-visualização\n(Etapa 1: placeholder)")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(360, 260)
        self.preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        left_layout.addWidget(self.preview)

        self.lbl_doc_info = QLabel("Documento: (não carregado)\nTamanho: -\nviewBox: -")
        self.lbl_doc_info.setStyleSheet("color: #cfcfcf;")
        left_layout.addWidget(self.lbl_doc_info)


        # Botões
        btn_row = QHBoxLayout()
        self.btn_load_svg = QPushButton("Carregar SVG…")
        self.btn_analyze = QPushButton("Analisar")
        btn_row.addWidget(self.btn_load_svg)
        btn_row.addWidget(self.btn_analyze)
        left_layout.addLayout(btn_row)

        # Nome do template
        self.ed_template_name = QLineEdit()
        self.ed_template_name.setPlaceholderText("Nome do template (ex: cartao_parabenizacao)")
        left_layout.addWidget(self.ed_template_name)
        lbl_out = QLabel("Nome do arquivo (padrão)")
        lbl_out.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(lbl_out)

        self.ed_output_pattern = QLineEdit()
        self.ed_output_pattern.setPlaceholderText("Ex: cartao_{nome}  |  Use {coluna} para variáveis")
        left_layout.addWidget(self.ed_output_pattern)

        left_layout.addStretch(1)



        lbl_out = QLabel("Nome do arquivo (padrão)")
        lbl_out.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(lbl_out)

        self.ed_output_pattern = QLineEdit()
        self.ed_output_pattern.setPlaceholderText("Ex: cartao_{nome}  |  Use {coluna} para variáveis")
        left_layout.addWidget(self.ed_output_pattern)

        self.lbl_out_help = QLabel("Variáveis serão substituídas a partir das colunas da tabela.")
        self.lbl_out_help.setStyleSheet("color: #cfcfcf;")
        left_layout.addWidget(self.lbl_out_help)

        # Botões finais
        bottom_row = QHBoxLayout()
        self.btn_save = QPushButton("Salvar Template")
        self.btn_cancel = QPushButton("Cancelar")
        bottom_row.addWidget(self.btn_save)
        bottom_row.addWidget(self.btn_cancel)
        left_layout.addLayout(bottom_row)

        # ---------- DIREITA (tabela)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        right_title = QLabel("Camadas de texto detectadas")
        right_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        right_layout.addWidget(right_title)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Variável",
            "Nome da coluna",
            "ID",
            "Texto atual",
            "Tag",
            "Fonte/Tam."
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 320)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 160)

        right_layout.addWidget(self.table, 1)

        root.addWidget(left, 4)
        root.addWidget(right, 6)

        # ---------- Conexões
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_load_svg.clicked.connect(self._on_load_svg)
        self.btn_analyze.clicked.connect(self._on_analyze)

        self.ed_template_name.setText(self.selected_model_name or "")
        if not self.ed_output_pattern.text().strip():
            self.ed_output_pattern.setText("cartao_{nome}")


        # Carrega dados fake
        self._load_fake_detected()
    

    def _load_fake_detected(self):
        self._detected = [
            DetectedLayer("nome", "NOME DO MILITAR", "text", "DejaVu Sans", "42px"),
            DetectedLayer("mensagem", "Mensagem de parabenização com várias linhas...", "text", "DejaVu Serif", "26px"),
            DetectedLayer("data", "12 DE DEZEMBRO DE 2025", "text", "DejaVu Sans", "22px"),
            DetectedLayer("comandante", "Cel Fulano de Tal", "text", "DejaVu Sans", "22px"),
            DetectedLayer("fixo_feliz_natal", "FELIZ NATAL", "text", "DejaVu Sans", "30px"),
        ]
        self._fill_table(self._detected)

    def _fill_table(self, items: list[DetectedLayer]):
        self.table.setRowCount(0)

        for layer in items:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox
            chk = QTableWidgetItem()
            chk.setFlags(chk.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, chk)

            # Nome da coluna (editável)
            col_name = QTableWidgetItem("")
            col_name.setFlags(col_name.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, col_name)

            # ID (readonly)
            id_item = QTableWidgetItem(layer.element_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, id_item)

            # Texto atual (readonly)
            txt_item = QTableWidgetItem(layer.text_preview)
            txt_item.setFlags(txt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, txt_item)

            # Tag (readonly)
            tag_item = QTableWidgetItem(layer.tag)
            tag_item.setFlags(tag_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, tag_item)

            # Fonte/Tam (readonly)
            fs_item = QTableWidgetItem(f"{layer.font_family} / {layer.font_size}")
            fs_item.setFlags(fs_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 5, fs_item)

        self.table.resizeRowsToContents()

    def _on_load_svg(self):
        # Etapa 1: simulação (na Etapa 2 usaremos QFileDialog e path real)
        self._loaded_svg_path = "modelo.svg"
        self.lbl_doc_info.setText(
            "Documento: modelo.svg\n"
            "Tamanho: 130x90mm (exemplo)\n"
            "viewBox: 0 0 1535 1063 (exemplo)"
        )
        self.preview.setText("Pré-visualização\n(modelo carregado - fake)")

    def _on_analyze(self):
        # Etapa 1: só recarrega a tabela fake
        self._load_fake_detected()

    def _on_save(self):
        name = self.ed_template_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Atenção", "Defina um nome para o template.")
            return
        
        pattern = self.ed_output_pattern.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Atenção", "Defina um padrão de nome de arquivo.")
            return
        
        self.output_pattern = pattern

        if "{" not in pattern or "}" not in pattern:
            # não é obrigatório ter variável, mas normalmente faz sentido avisar
            # se quiser, podemos deixar sem aviso.
            pass

        selected = self._get_selected_fields()
        if selected is None:
            QMessageBox.warning(self, "Atenção", "Para cada campo marcado como variável, preencha o Nome da coluna.")
            return
        if len(selected) == 0:
            QMessageBox.warning(self, "Atenção", "Marque pelo menos um campo como variável.")
            return



        self.accept()

    def _get_selected_fields(self):
        fields = []
        for row in range(self.table.rowCount()):
            is_var = self.table.item(row, 0).checkState() == Qt.CheckState.Checked
            col_name = (self.table.item(row, 1).text() or "").strip()
            element_id = self.table.item(row, 2).text()

            if is_var:
                if not col_name:
                    return None  # inválido
                fields.append((col_name, element_id))
        return fields
