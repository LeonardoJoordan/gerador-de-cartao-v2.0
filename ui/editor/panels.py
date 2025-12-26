# ui/editor/panels.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, 
                               QFormLayout, QTextEdit, QFontComboBox, QPushButton, 
                               QComboBox, QDoubleSpinBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor, QTextBlockFormat, QTextCharFormat

# Importação para Type Hinting (ajuda na IDE)
from .canvas_items import DesignerBox

# --- 3. Painel de Propriedades (Dimensões) ---
class CaixaDeTextoPanel(QWidget):
    widthChanged = Signal(int)
    heightChanged = Signal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        lbl = QLabel("CAIXA DE TEXTO")
        lbl.setStyleSheet("font-weight: bold; font-size: 12px; margin-bottom: 5px;")
        layout.addWidget(lbl)
        
        form = QFormLayout()
        form.setSpacing(8)

        self.spin_w = QSpinBox()
        self.spin_w.setRange(10, 5000)
        self.spin_w.setSuffix(" px")
        self.spin_w.valueChanged.connect(self.widthChanged.emit)
        form.addRow("Largura:", self.spin_w)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(10, 5000)
        self.spin_h.setSuffix(" px")
        self.spin_h.valueChanged.connect(self.heightChanged.emit)
        form.addRow("Altura:", self.spin_h)

        layout.addLayout(form)
        layout.addStretch()

    def load_from_item(self, box: DesignerBox):
        self.blockSignals(True) 
        rect = box.rect()
        self.spin_w.setValue(int(rect.width()))
        self.spin_h.setValue(int(rect.height()))
        self.blockSignals(False)


# --- 3b. Painel de Editor de Texto (Turbinado) ---
class EditorDeTextoPanel(QWidget):
    htmlChanged = Signal(str)
    fontFamilyChanged = Signal(QFont)
    fontSizeChanged = Signal(int)
    boldChanged = Signal(bool) # (Sinal genérico, na prática controlamos via formatação direta)
    alignChanged = Signal(str)
    verticalAlignChanged = Signal(str)
    indentChanged = Signal(float)
    lineHeightChanged = Signal(float)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        lbl = QLabel("EDITOR DE TEXTO")
        lbl.setStyleSheet("font-weight: bold; font-size: 12px; border-bottom: 1px solid #ccc;")
        layout.addWidget(lbl)
        
        # 1. Conteúdo
        layout.addWidget(QLabel("Texto:"))
        self.txt_content = QTextEdit()
        self.txt_content.setMinimumHeight(80)
        self.txt_content.textChanged.connect(lambda: self.htmlChanged.emit(self.txt_content.toHtml()))
        layout.addWidget(self.txt_content)
        
        # 2. Fonte e Tamanho
        row_font = QHBoxLayout()
        self.cbo_font = QFontComboBox()
        self.cbo_font.currentFontChanged.connect(self.set_font_family)
        self.spin_size = QSpinBox()
        self.spin_size.setRange(6, 300)
        self.spin_size.valueChanged.connect(self.set_font_size)
        row_font.addWidget(self.cbo_font, 2)
        row_font.addWidget(self.spin_size, 1)
        layout.addLayout(row_font)

        # 3. Negrito e Alinhamentos
        row_style = QHBoxLayout()
        
        # --- BARRA DE FERRAMENTAS ---
        self.btn_bold = QPushButton("B")
        self.btn_bold.setFixedWidth(30)
        self.btn_bold.setStyleSheet("font-weight: bold")
        self.btn_bold.setCheckable(True)
        self.btn_bold.clicked.connect(lambda: self.set_format_attribute("bold"))

        self.btn_italic = QPushButton("I")
        self.btn_italic.setFixedWidth(30)
        self.btn_italic.setStyleSheet("font-style: italic")
        self.btn_italic.setCheckable(True)
        self.btn_italic.clicked.connect(lambda: self.set_format_attribute("italic"))

        self.btn_underline = QPushButton("U")
        self.btn_underline.setFixedWidth(30)
        self.btn_underline.setStyleSheet("text-decoration: underline")
        self.btn_underline.setCheckable(True)
        self.btn_underline.clicked.connect(lambda: self.set_format_attribute("underline"))

        row_style.addWidget(self.btn_bold)
        row_style.addWidget(self.btn_italic)
        row_style.addWidget(self.btn_underline)
        
        # Horizontal
        self.cbo_align = QComboBox()
        self.cbo_align.addItems(["Esq", "Cen", "Dir", "Just"])
        self.cbo_align.setToolTip("Alinhamento Horizontal")
        self._align_map = ["left", "center", "right", "justify"]
        self.cbo_align.currentIndexChanged.connect(lambda idx: self.alignChanged.emit(self._align_map[idx]))

        # Vertical
        self.cbo_valign = QComboBox()
        self.cbo_valign.addItems(["Topo", "Meio", "Base"])
        self.cbo_valign.setToolTip("Alinhamento Vertical")
        self._valign_map = ["top", "center", "bottom"]
        self.cbo_valign.currentIndexChanged.connect(lambda idx: self.verticalAlignChanged.emit(self._valign_map[idx]))

        row_style.addWidget(self.cbo_align)
        row_style.addWidget(self.cbo_valign)
        layout.addLayout(row_style)

        # 4. Espaçamentos
        form_space = QFormLayout()
        self.spin_indent = QDoubleSpinBox()
        self.spin_indent.setRange(0, 500)
        self.spin_indent.setSuffix(" px")
        self.spin_indent.valueChanged.connect(lambda val: self.indentChanged.emit(val))
        form_space.addRow("Recuo 1ª:", self.spin_indent)
        
        self.spin_lh = QDoubleSpinBox()
        self.spin_lh.setRange(0.5, 5.0)
        self.spin_lh.setSingleStep(0.1)
        self.spin_lh.setValue(1.15)
        self.spin_lh.valueChanged.connect(lambda val: self.lineHeightChanged.emit(val))
        form_space.addRow("Entrelinha:", self.spin_lh)
        
        layout.addLayout(form_space)
        layout.addStretch()
        self.txt_content.cursorPositionChanged.connect(self.update_buttons_state)

    def update_buttons_state(self):
        """Verifica a formatação onde o cursor está e atualiza os botões visualmente."""
        fmt = self.txt_content.currentCharFormat()
        
        self.btn_bold.blockSignals(True)
        self.btn_italic.blockSignals(True)
        self.btn_underline.blockSignals(True)

        self.btn_bold.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        self.btn_italic.setChecked(fmt.fontItalic())
        self.btn_underline.setChecked(fmt.fontUnderline())

        self.btn_bold.blockSignals(False)
        self.btn_italic.blockSignals(False)
        self.btn_underline.blockSignals(False)

    def set_font_family(self, font):
        cursor = self.txt_content.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)
        
        fmt = QTextCharFormat()
        fmt.setFontFamily(font.family())
        cursor.mergeCharFormat(fmt)
        self.txt_content.setFocus()
        self.fontFamilyChanged.emit(font)

    def set_font_size(self, size):
        cursor = self.txt_content.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)
        
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        cursor.mergeCharFormat(fmt)
        self.txt_content.setFocus()
        self.fontSizeChanged.emit(size)

    def set_format_attribute(self, attr_type):
        cursor = self.txt_content.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)

        fmt = cursor.charFormat()

        if attr_type == "bold":
            is_bold = fmt.fontWeight() == QFont.Weight.Bold
            new_weight = QFont.Weight.Normal if is_bold else QFont.Weight.Bold
            fmt.setFontWeight(new_weight)
        
        elif attr_type == "italic":
            fmt.setFontItalic(not fmt.fontItalic())
            
        elif attr_type == "underline":
            fmt.setFontUnderline(not fmt.fontUnderline())

        cursor.setCharFormat(fmt)
        self.txt_content.setFocus()

    def load_from_item(self, box: DesignerBox):
        self.blockSignals(True) 
        
        self.txt_content.setHtml(box.text_item.toHtml())
        
        font = box.text_item.font()
        self.cbo_font.setCurrentFont(font)
        self.spin_size.setValue(int(font.pointSize()))
        self.btn_bold.setChecked(font.bold())
        
        # Horizontal
        opt = box.text_item.document().defaultTextOption()
        align = opt.alignment()
        if align & Qt.AlignmentFlag.AlignRight: self.cbo_align.setCurrentIndex(2)
        elif align & Qt.AlignmentFlag.AlignCenter: self.cbo_align.setCurrentIndex(1)
        elif align & Qt.AlignmentFlag.AlignJustify: self.cbo_align.setCurrentIndex(3)
        else: self.cbo_align.setCurrentIndex(0)

        # Vertical
        v_idx = 0
        if box.vertical_align == "center": v_idx = 1
        elif box.vertical_align == "bottom": v_idx = 2
        self.cbo_valign.setCurrentIndex(v_idx)
        
        # Espaçamento
        cursor = QTextCursor(box.text_item.document())
        fmt = cursor.blockFormat()
        self.spin_indent.setValue(fmt.textIndent())
        
        # LineHeightTypes.ProportionalHeight = 1
        if fmt.lineHeightType() == 1:
            self.spin_lh.setValue(fmt.lineHeight() / 100.0)
        else:
            self.spin_lh.setValue(1.15)

        self.blockSignals(False)