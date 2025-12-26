# ui/editor/editor_window.py
import json
from PySide6.QtWidgets import (QMainWindow, QGraphicsView, QGraphicsScene, QWidget, 
                               QHBoxLayout, QVBoxLayout, QFrame, QLabel, QPushButton, 
                               QMessageBox)
from PySide6.QtGui import QPainter, QBrush, QPen, QColor, QAction
from PySide6.QtCore import Qt

# Importa os módulos que acabamos de separar
from .canvas_items import DesignerBox, Guideline, px_to_mm
from .panels import CaixaDeTextoPanel, EditorDeTextoPanel


class EditorWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor Visual de Modelo (AutoMakeCard)")
        self.resize(1200, 800)

        # Configuração da UI Principal
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- 1. ÁREA DE DESENHO (CENA) ---
        # Tamanho fixo inicial de 1000x1000 (será dinâmico no futuro com a imagem de fundo)
        self.scene = QGraphicsScene(0, 0, 1000, 1000) 
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor("#e0e0e0")))
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
        # Retângulo branco representando o papel/cartão
        self.bg_rect = self.scene.addRect(0, 0, 1000, 1000, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
        self.bg_rect.setZValue(-100)
        
        # Info de debug (tamanho)
        total_w_mm = px_to_mm(1000)
        total_h_mm = px_to_mm(1000)
        self.scene.addText(f"Canvas: {total_w_mm:.1f}mm x {total_h_mm:.1f}mm").setPos(10, 10)
        
        main_layout.addWidget(self.view, 1)

        # --- 2. PAINEL LATERAL (CONTROLES) ---
        right_container = QWidget()
        right_container.setFixedWidth(320)
        right_layout = QVBoxLayout(right_container)
        
        # Grupo: Guias
        grp_guides = QFrame()
        ly_guides = QVBoxLayout(grp_guides)
        ly_guides.setContentsMargins(0, 0, 0, 10)
        ly_guides.addWidget(QLabel("<b>LINHAS GUIA</b>"))
        ly_guides.addWidget(QLabel("<small>Duplo clique na linha para editar (mm)</small>"))
        
        btn_guide_v = QPushButton("Add Guia Vertical (|)")
        btn_guide_v.clicked.connect(lambda: self.add_guide(vertical=True))
        
        btn_guide_h = QPushButton("Add Guia Horizontal (-)")
        btn_guide_h.clicked.connect(lambda: self.add_guide(vertical=False))
        
        ly_guides.addWidget(btn_guide_v)
        ly_guides.addWidget(btn_guide_h)
        right_layout.addWidget(grp_guides)

        # Separador
        self._add_separator(right_layout)

        # Grupo: Adicionar Elementos
        grp_boxes = QFrame()
        ly_boxes = QVBoxLayout(grp_boxes)
        ly_boxes.setContentsMargins(0, 0, 0, 10)
        ly_boxes.addWidget(QLabel("<b>ELEMENTOS</b>"))
        
        self.btn_add = QPushButton("+ Adicionar Caixa Texto")
        self.btn_add.setMinimumHeight(40)
        self.btn_add.clicked.connect(self.add_new_box)
        ly_boxes.addWidget(self.btn_add)
        right_layout.addWidget(grp_boxes)

        # Separador
        self._add_separator(right_layout)

        # --- PAINÉIS DE PROPRIEDADES (Importados) ---
        self.caixa_texto_panel = CaixaDeTextoPanel()
        self.caixa_texto_panel.setEnabled(False)
        self.caixa_texto_panel.widthChanged.connect(self.update_width)
        self.caixa_texto_panel.heightChanged.connect(self.update_height)
        right_layout.addWidget(self.caixa_texto_panel)

        self._add_separator(right_layout)

        self.editor_texto_panel = EditorDeTextoPanel()
        self.editor_texto_panel.setEnabled(False)
        # Conexões dos sinais do painel para os slots desta janela
        self.editor_texto_panel.htmlChanged.connect(self.update_text_html)
        self.editor_texto_panel.fontFamilyChanged.connect(self.update_font_family)
        self.editor_texto_panel.fontSizeChanged.connect(self.update_font_size)
        self.editor_texto_panel.alignChanged.connect(self.update_align)
        self.editor_texto_panel.verticalAlignChanged.connect(self.update_vertical_align)
        self.editor_texto_panel.indentChanged.connect(self.update_indent)
        self.editor_texto_panel.lineHeightChanged.connect(self.update_line_height)
        right_layout.addWidget(self.editor_texto_panel)

        # Botão Salvar
        right_layout.addStretch()
        self.btn_save = QPushButton("Salvar Modelo (JSON)")
        self.btn_save.setMinimumHeight(50)
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 14px;")
        self.btn_save.clicked.connect(self.export_to_json)
        right_layout.addWidget(self.btn_save)

        main_layout.addWidget(right_container)

        # Conecta evento de seleção da cena
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

    # --- Lógica da Cena ---
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected = self.scene.selectedItems()
            for item in selected: 
                self.scene.removeItem(item)
            self.on_selection_changed() # Atualiza estado dos painéis
        else:
            super().keyPressEvent(event)

    def add_guide(self, vertical):
        # Adiciona no meio da tela visível (aprox)
        pos = 500 
        self.scene.addItem(Guideline(pos, is_vertical=vertical))

    def add_new_box(self):
        # Cria box padrão
        box = DesignerBox(350, 450, 300, 60, "{campo}")
        self.scene.addItem(box)
        
        # Seleciona a nova box automaticamente
        self.scene.clearSelection()
        box.setSelected(True)

    def on_selection_changed(self):
        sel = self.scene.selectedItems()
        boxes = [i for i in sel if isinstance(i, DesignerBox)]
        
        if boxes:
            target_box = boxes[0]
            # Carrega dados da box nos painéis
            self.editor_texto_panel.load_from_item(target_box)
            self.editor_texto_panel.setEnabled(True)
            
            self.caixa_texto_panel.load_from_item(target_box)
            self.caixa_texto_panel.setEnabled(True)
        else:
            self.editor_texto_panel.setEnabled(False)
            self.caixa_texto_panel.setEnabled(False)

    def _get_selected(self) -> DesignerBox | None:
        sel = self.scene.selectedItems()
        boxes = [i for i in sel if isinstance(i, DesignerBox)]
        return boxes[0] if boxes else None

    # --- Slots de Atualização (Painel -> Cena) ---
    def update_text_html(self, html_content):
        box = self._get_selected()
        if box: 
            box.text_item.setHtml(html_content)
            box.recalculate_text_position()
    
    def update_font_family(self, font):
        box = self._get_selected()
        if box:
            f = box.text_item.font()
            f.setFamily(font.family())
            box.text_item.setFont(f)

    def update_font_size(self, size):
        box = self._get_selected()
        if box:
            f = box.text_item.font()
            f.setPointSize(size)
            box.text_item.setFont(f)

    def update_width(self, width):
        box = self._get_selected()
        if box:
            r = box.rect()
            box.setRect(0, 0, width, r.height())
            box.recalculate_text_position()

    def update_height(self, height):
        box = self._get_selected()
        if box:
            r = box.rect()
            box.setRect(0, 0, r.width(), height)
            box.recalculate_text_position()

    def update_align(self, align_str):
        box = self._get_selected()
        if box: box.set_alignment(align_str)

    def update_vertical_align(self, align_str):
        box = self._get_selected()
        if box: box.set_vertical_alignment(align_str)

    def update_indent(self, val):
        box = self._get_selected()
        if box: box.set_block_format(indent=val)

    def update_line_height(self, val):
        box = self._get_selected()
        if box: box.set_block_format(line_height=val)

    # --- Exportação ---
    def export_to_json(self):
        """
        Gera a estrutura de dados JSON baseada no que está na tela.
        No futuro, isso salvará no arquivo template.json real.
        """
        boxes_data = []
        for item in self.scene.items():
            if isinstance(item, DesignerBox):
                pos = item.pos()
                r = item.rect()
                font = item.text_item.font()
                
                # Alinhamento Horizontal
                opt = item.text_item.document().defaultTextOption()
                h_code = opt.alignment()
                h_align = "left"
                if h_code & Qt.AlignmentFlag.AlignCenter: h_align = "center"
                elif h_code & Qt.AlignmentFlag.AlignRight: h_align = "right"
                elif h_code & Qt.AlignmentFlag.AlignJustify: h_align = "justify"

                # Formatação de Bloco
                fmt = item.text_item.document().begin().blockFormat()
                lh = 1.15
                if fmt.lineHeightType() == 1: # ProportionalHeight
                    lh = fmt.lineHeight() / 100.0

                box_dict = {
                    "id": item.text_item.toPlainText().replace("{", "").replace("}", "").strip(),
                    "html": item.text_item.toHtml(),
                    "text_clean": item.text_item.toPlainText(),
                    "x": int(pos.x()),
                    "y": int(pos.y()),
                    "w": int(r.width()),
                    "h": int(r.height()),
                    "font_family": font.family(), 
                    "font_size": int(font.pointSize()),
                    "align": h_align,
                    "vertical_align": item.vertical_align,
                    "indent_px": int(fmt.textIndent()),
                    "line_height": float(f"{lh:.2f}")
                }
                boxes_data.append(box_dict)

        data = {
            "name": "modelo_editor_visual",
            "boxes": boxes_data,
            "canvas_w": int(self.scene.width()),
            "canvas_h": int(self.scene.height())
        }
        
        # Por enquanto apenas imprime para debug (conforme POC)
        # Na integração final, salvaremos em arquivo
        print(json.dumps(data, indent=2))
        QMessageBox.information(self, "Exportar JSON", "JSON gerado no console (Debug).\nPronto para salvar em arquivo.")