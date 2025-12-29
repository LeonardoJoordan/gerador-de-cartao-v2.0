# ui/editor/editor_window.py

import json
from PySide6.QtWidgets import (QMainWindow, QGraphicsView, QGraphicsScene, QWidget, 
                               QHBoxLayout, QVBoxLayout, QFrame, QLabel, QPushButton, 
                               QMessageBox, QInputDialog, QListWidget, QAbstractItemView,
                               QListWidgetItem)
from PySide6.QtGui import (QPainter, QBrush, QPen, QColor, QAction, QShortcut, 
                           QKeySequence, QTextCursor, QTextCharFormat)
from PySide6.QtCore import Qt, Signal, QEvent
from pathlib import Path
import shutil

# Importa os módulos que acabamos de separar
from .canvas_items import DesignerBox, Guideline, px_to_mm, SignatureItem
from .panels import CaixaDeTextoPanel, EditorDeTextoPanel, AssinaturaPanel


class EditorWindow(QMainWindow):
    # Agora envia: (Nome do Modelo, Lista de Placeholders)
    modelSaved = Signal(str, list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor Visual de Modelo (AutoMakeCard)")
        self.resize(1200, 800)

        # Configuração da UI Principal
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- 0. PAINEL ESQUERDO (CAMADAS) ---
        left_container = QWidget()
        left_container.setFixedWidth(220)
        left_layout = QVBoxLayout(left_container)
        
        # Título
        lbl_layers = QLabel("<b>CAMADAS</b>")
        left_layout.addWidget(lbl_layers)

        # A Lista
        self.layer_list = QListWidget()
        # [SIMPLIFICAÇÃO] Conectamos o CLIQUE do item a uma função simples
        self.layer_list.itemClicked.connect(self._on_layer_list_clicked)
        left_layout.addWidget(self.layer_list)
        
        main_layout.addWidget(left_container)

        # --- 1. ÁREA DE DESENHO (CENA) ---
        # Tamanho fixo inicial de 1000x1000 (será dinâmico no futuro com a imagem de fundo)
        self.scene = QGraphicsScene(0, 0, 1000, 1000)
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor("#e0e0e0")))
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        # Captura teclas pressionadas quando o foco está na view (setas, delete)
        self.view.installEventFilter(self)
        
        # Referências para o fundo (Imagem ou Fallback branco)
        self.bg_item = None  # Armazenará o QGraphicsPixmapItem da imagem
        self.background_path = None
        
        # Retângulo branco de fallback (mantém a área visível se não houver imagem)
        self.fallback_bg = self.scene.addRect(0, 0, 1000, 1000, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
        self.fallback_bg.setZValue(-100)
        
        main_layout.addWidget(self.view, 1)

        # --- 2. PAINEL LATERAL (CONTROLES) ---
        right_container = QWidget()
        right_container.setFixedWidth(400)
        right_layout = QVBoxLayout(right_container)
        
        # Grupo: Guias (Layout Otimizado)
        grp_guides = QFrame()
        ly_guides = QVBoxLayout(grp_guides)
        ly_guides.setContentsMargins(0, 0, 0, 10)
        
        # Cabeçalho unificado
        lbl_guides = QLabel("<b>LINHAS GUIA</b> <small style='color:gray'>(Duplo clique p/ editar)</small>")
        ly_guides.addWidget(lbl_guides)
        
        # Botões lado a lado
        row_guides = QHBoxLayout()
        row_guides.setSpacing(10)
        
        btn_guide_v = QPushButton("Vertical (|)")
        btn_guide_v.clicked.connect(lambda: self.add_guide(vertical=True))
        
        btn_guide_h = QPushButton("Horizontal (—)")
        btn_guide_h.clicked.connect(lambda: self.add_guide(vertical=False))
        
        row_guides.addWidget(btn_guide_v)
        row_guides.addWidget(btn_guide_h)
        ly_guides.addLayout(row_guides)

        right_layout.addWidget(grp_guides)

        # Separador
        self._add_separator(right_layout)

        # Grupo: Adicionar Elementos (Layout Otimizado)
        grp_boxes = QFrame()
        ly_boxes = QVBoxLayout(grp_boxes)
        ly_boxes.setContentsMargins(0, 0, 0, 10)
        ly_boxes.addWidget(QLabel("<b>ELEMENTOS</b>"))
        
        # 1. Botão Principal (Texto) - Mantém largura total
        self.btn_add = QPushButton("+ Adicionar Caixa Texto")
        self.btn_add.setMinimumHeight(40)
        self.btn_add.clicked.connect(self.add_new_box)
        ly_boxes.addWidget(self.btn_add)

        # 2. Botões Secundários (Fundo e Assinatura) - Lado a Lado
        row_assets = QHBoxLayout()
        row_assets.setSpacing(10)

        self.btn_add_bg = QPushButton("🖼️ Fundo")
        self.btn_add_bg.setToolTip("Definir imagem de fundo")
        self.btn_add_bg.setMinimumHeight(40) # Mesma altura do botão de texto
        self.btn_add_bg.clicked.connect(self._on_click_load_bg)
        
        self.btn_add_sig = QPushButton("✍️ Assinatura")
        self.btn_add_sig.setToolTip("Adicionar imagem de assinatura")
        self.btn_add_sig.setMinimumHeight(40) # Mesma altura do botão de texto
        self.btn_add_sig.clicked.connect(self._on_click_add_signature)
        
        row_assets.addWidget(self.btn_add_bg)
        row_assets.addWidget(self.btn_add_sig)
        ly_boxes.addLayout(row_assets)

        right_layout.addWidget(grp_boxes)

        # Separador
        self._add_separator(right_layout)

       # --- PAINÉIS DE PROPRIEDADES (Importados) ---
        
        # CONTAINER MISTO: Dimensões (Esq) | Separador | Ordem Colunas (Dir)
        container_misto = QWidget()
        layout_misto = QHBoxLayout(container_misto)
        layout_misto.setContentsMargins(0, 0, 0, 0)
        layout_misto.setSpacing(10)

        # 1. LADO ESQUERDO: Painel de Dimensões
        self.caixa_texto_panel = CaixaDeTextoPanel()
        self.caixa_texto_panel.setEnabled(False)
        self.caixa_texto_panel.widthChanged.connect(self.update_width)
        self.caixa_texto_panel.heightChanged.connect(self.update_height)
        self.caixa_texto_panel.rotationChanged.connect(self.update_rotation)
        layout_misto.addWidget(self.caixa_texto_panel, 1)

        # 2. SEPARADOR VERTICAL
        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.Shape.VLine)
        v_sep.setFrameShadow(QFrame.Shadow.Sunken)
        v_sep.setStyleSheet("color: #ccc;") # Cor sutil
        layout_misto.addWidget(v_sep)

        # 3. LADO DIREITO: Ordem das Colunas
        grp_cols_compact = QWidget()
        ly_cols_compact = QVBoxLayout(grp_cols_compact)
        ly_cols_compact.setContentsMargins(0, 0, 0, 0)
        ly_cols_compact.setSpacing(2)
        
        # [UX] Título padronizado com <b>
        lbl_cols = QLabel("<b>ORDEM NA TABELA</b>")
        ly_cols_compact.addWidget(lbl_cols)

        self.lst_placeholders = QListWidget()
        self.lst_placeholders.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.lst_placeholders.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.lst_placeholders.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lst_placeholders.setFixedHeight(75) 
        ly_cols_compact.addWidget(self.lst_placeholders)
        
        layout_misto.addWidget(grp_cols_compact, 1)

        right_layout.addWidget(container_misto)
        
        self._add_separator(right_layout)

        self.editor_texto_panel = EditorDeTextoPanel()
        self.editor_texto_panel.setEnabled(False)

        # Conexões dos sinais do painel para os slots desta janela
        self.editor_texto_panel.htmlChanged.connect(self.update_text_html)
        self.editor_texto_panel.htmlChanged.connect(self._on_content_updated)
        self.editor_texto_panel.fontFamilyChanged.connect(self.update_font_family)
        self.editor_texto_panel.fontSizeChanged.connect(self.update_font_size)
        self.editor_texto_panel.alignChanged.connect(self.update_align)
        self.editor_texto_panel.verticalAlignChanged.connect(self.update_vertical_align)
        self.editor_texto_panel.indentChanged.connect(self.update_indent)
        self.editor_texto_panel.lineHeightChanged.connect(self.update_line_height)
        right_layout.addWidget(self.editor_texto_panel)

        self.assinatura_panel = AssinaturaPanel()
        self.assinatura_panel.setVisible(False) # Começa oculto
        self.assinatura_panel.sideChanged.connect(self.update_signature_size)
        right_layout.addWidget(self.assinatura_panel)

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

        self._updating_selection = False

        # --- ATALHOS ---
        self.shortcut_dup = QShortcut(QKeySequence("Ctrl+J"), self)
        self.shortcut_dup.activated.connect(self.duplicate_selected)

        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.export_to_json)

    def showEvent(self, event):
        super().showEvent(event)
        # Garante o fit ao exibir a janela pela primeira vez
        self._zoom_to_fit()

    def _zoom_to_fit(self):
        """Ajusta o zoom para que a cena inteira caiba na visualização, com margem."""
        if not self.scene.sceneRect().isEmpty():
            # Adiciona 50px de margem visual ao redor da área da cena
            # Isso faz o fit considerar uma área maior, deixando a imagem 'descolada' das bordas
            margin = 50
            view_rect = self.scene.sceneRect().adjusted(-margin, -margin, margin, margin)
            
            self.view.fitInView(view_rect, Qt.AspectRatioMode.KeepAspectRatio)
    
    def sync_placeholders_list(self):
        """Sincroniza a QListWidget com os itens da cena, preservando ordem manual."""
        # 1. O que existe na cena agora?
        current_vars = set(self.get_all_model_placeholders())

        # 2. O que já está na lista visual?
        existing_items_map = {} # map: text -> row
        for i in range(self.lst_placeholders.count()):
            existing_items_map[self.lst_placeholders.item(i).text()] = i

        # 3. Remover da lista o que não existe mais na cena
        # (De trás pra frente para não invalidar índices)
        for i in range(self.lst_placeholders.count() - 1, -1, -1):
            txt = self.lst_placeholders.item(i).text()
            if txt not in current_vars:
                self.lst_placeholders.takeItem(i)

        # 4. Adicionar novos no final (append)
        for var in sorted(list(current_vars)):
            if var not in existing_items_map:
                self.lst_placeholders.addItem(var)
    
    def _import_asset(self, source_path: str, model_dir: Path) -> str | None:
        """Copia o arquivo para a pasta assets/ do modelo e retorna caminho relativo."""
        if not source_path: 
            return None
        
        src = Path(source_path)
        if not src.exists():
            return None
            
        # Se já é relativo ou está dentro da pasta assets, assume que está ok
        # (Isso evita copiar recursivamente se salvar múltiplas vezes)
        if "assets" in src.parts and model_dir in src.parents:
            return f"assets/{src.name}"

        assets_dir = model_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        dest = assets_dir / src.name
        
        # Copia o arquivo (sobrescreve se existir para garantir atualização)
        try:
            shutil.copy2(src, dest)
            return f"assets/{src.name}"
        except Exception as e:
            print(f"Erro ao copiar asset: {e}")
            return source_path # Fallback para o original
    
    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

    # --- Lógica de Eventos (Filtro) ---
    def eventFilter(self, source, event):
        if source == self.view and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            
            # 1. Deletar itens
            if key == Qt.Key.Key_Delete:
                selected = self.scene.selectedItems()
                for item in selected: 
                    self.scene.removeItem(item)
                self.on_selection_changed()
                self.sync_placeholders_list()
                return True # Evento consumido
            
            # 2. Mover itens (Setas)
            elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
                step = 1
                # Se segurar Shift, move mais rápido (opcional, mas útil)
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    step = 10
                
                dx, dy = 0, 0
                if key == Qt.Key.Key_Left: dx = -step
                elif key == Qt.Key.Key_Right: dx = step
                elif key == Qt.Key.Key_Up: dy = -step
                elif key == Qt.Key.Key_Down: dy = step
                
                sel_items = self.scene.selectedItems()
                if sel_items:
                    for item in sel_items:
                        item.moveBy(dx, dy)
                    return True # Evento consumido (evita scroll da tela)
        
        return super().eventFilter(source, event)

    def add_guide(self, vertical):
        # Calcula o centro exato do documento atual
        rect = self.scene.sceneRect()
        
        if vertical:
            # Guia Vertical: Fica no meio da Largura (X)
            pos = rect.width() / 2
        else:
            # Guia Horizontal: Fica no meio da Altura (Y)
            pos = rect.height() / 2

        self.scene.addItem(Guideline(pos, is_vertical=vertical))

    def add_new_box(self):
        # Cria box padrão
        box = DesignerBox(350, 450, 300, 60, "{campo}")
        
        # [FIX] Força configuração inicial de fonte para sincronia visual imediata
        # Garante que o objeto visual tenha a mesma fonte que será salva no JSON
        from PySide6.QtGui import QFont
        initial_font = QFont("Arial", 16)
        box.text_item.setFont(initial_font)
        box.text_item.document().setDefaultFont(initial_font)
        
        self.scene.addItem(box)
        
        # Seleciona a nova box automaticamente
        self.scene.clearSelection()
        box.setSelected(True)
        self.refresh_layer_list()

    def on_selection_changed(self):
        sel = self.scene.selectedItems()
        boxes = [i for i in sel if isinstance(i, DesignerBox)]
        signatures = [i for i in sel if isinstance(i, SignatureItem)]
        
        # Painéis de Texto
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

        # Painel de Assinatura
        if signatures:
            self.assinatura_panel.load_from_item(signatures[0])
            self.assinatura_panel.setVisible(True)
        else:
            self.assinatura_panel.setVisible(False)

    def duplicate_selected(self):
        original = self._get_selected()
        if not original: return

        # 1. Cria nova caixa com deslocamento
        offset = 20
        new_x = original.x() + offset
        new_y = original.y() + offset
        rect = original.rect()
        
        # Cria a nova instância
        new_box = DesignerBox(new_x, new_y, rect.width(), rect.height(), "")
        
        # 2. Reseta ID (para o refresh gerar um novo)
        new_box.layer_id = None 
        self.scene.addItem(new_box)
        self.refresh_layer_list()
        
        # 3. Copia Propriedades
        new_box.setRotation(original.rotation())
        new_box.vertical_align = original.vertical_align
        new_box.update_center()
        
        # HTML e Estilo
        html = original.text_item.toHtml()
        new_box.text_item.setHtml(html)
        
        # Fonte Container
        orig_font = original.text_item.font()
        new_box.text_item.setFont(orig_font)
        new_box.text_item.document().setDefaultFont(orig_font)
        
        # Bloco
        opt = original.text_item.document().defaultTextOption()
        new_box.text_item.document().setDefaultTextOption(opt)
        
        cursor = QTextCursor(original.text_item.document())
        fmt = cursor.blockFormat()
        new_box.set_block_format(indent=fmt.textIndent(), line_height=fmt.lineHeight()/100.0 if fmt.lineHeightType() == 1 else 1.15)

        # 4. Adiciona
        self.scene.addItem(new_box)
        
        # 5. Atualiza Camadas e Seleciona a nova
        self.refresh_layer_list()
        
        self.scene.clearSelection()
        new_box.setSelected(True)
        
        # Sincroniza lista da direita (Tabela)
        self.sync_placeholders_list()

    def _get_selected(self) -> DesignerBox | None:
        sel = self.scene.selectedItems()
        boxes = [i for i in sel if isinstance(i, DesignerBox)]
        return boxes[0] if boxes else None

    # --- Slots de Atualização (Painel -> Cena) ---
    def update_text_html(self, html_content):
        box = self._get_selected()
        if box: 
            # 1. Guarda a fonte que o usuário escolheu (está salva no Item)
            current_font = box.text_item.font()
            
            # 2. Define o HTML (Isso "reseta" o documento e mata o DefaultFont)
            box.text_item.setHtml(html_content)
            
            # 3. [CORREÇÃO] Restaura a fonte padrão imediatamente após o reset do HTML
            box.text_item.document().setDefaultFont(current_font)
            
            box.recalculate_text_position()
    
    def update_font_family(self, font):
        box = self._get_selected()
        if box:
            # 1. Atualiza propriedades do container e padrão (para texto futuro)
            f = box.text_item.font()
            f.setFamily(font.family())
            box.text_item.setFont(f)
            box.text_item.document().setDefaultFont(f) 
                        
            cursor = QTextCursor(box.text_item.document())
            cursor.select(QTextCursor.SelectionType.Document)
            
            fmt = QTextCharFormat()
            fmt.setFontFamily(font.family())
            
            cursor.mergeCharFormat(fmt)

    def update_font_size(self, size):
        box = self._get_selected()
        if box:
            # 1. Atualiza propriedades do container e padrão
            f = box.text_item.font()
            f.setPointSize(size)
            box.text_item.setFont(f)
            box.text_item.document().setDefaultFont(f)
                        
            cursor = QTextCursor(box.text_item.document())
            cursor.select(QTextCursor.SelectionType.Document)
            
            fmt = QTextCharFormat()
            fmt.setFontPointSize(size) # Nota: Aqui usamos setFontPointSize, não setPointSize
            
            cursor.mergeCharFormat(fmt)
            
            # Força recálculo imediato da posição (pois mudar tamanho afeta a altura da linha)
            box.recalculate_text_position()

    def update_width(self, width):
        box = self._get_selected()
        if box:
            r = box.rect()
            box.setRect(0, 0, width, r.height())
            box.recalculate_text_position()
            box.update_center() # Garante que o eixo de rotação continue no meio

    def update_height(self, height):
        box = self._get_selected()
        if box:
            r = box.rect()
            box.setRect(0, 0, r.width(), height)
            box.recalculate_text_position()
            box.update_center() # Garante que o eixo de rotação continue no meio

    def update_rotation(self, angle):
        box = self._get_selected()
        if box:
            box.setRotation(angle)

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
        Gera a estrutura de dados JSON unificada para o novo modelo V3.
        Salva: Background, Assinaturas e Caixas de Texto.
        """
        boxes_data = []
        signatures_data = []
        
        # Percorre os itens da cena para separar assinaturas e caixas
        for item in self.scene.items():
            # 1. Processar Caixas de Texto
            if isinstance(item, DesignerBox):
                pos = item.pos()
                r = item.rect()
                font = item.text_item.font()
                fmt = item.text_item.document().begin().blockFormat()
                
                # Alinhamento Horizontal
                opt = item.text_item.document().defaultTextOption()
                h_code = opt.alignment()
                h_align = "left"
                if h_code & Qt.AlignmentFlag.AlignCenter: h_align = "center"
                elif h_code & Qt.AlignmentFlag.AlignRight: h_align = "right"
                elif h_code & Qt.AlignmentFlag.AlignJustify: h_align = "justify"

                boxes_data.append({
                    "id": item.text_item.toPlainText().replace("{", "").replace("}", "").strip(),
                    "html": item.text_item.toHtml(),
                    "x": int(pos.x()),
                    "y": int(pos.y()),
                    "w": int(r.width()),
                    "h": int(r.height()),
                    "rotation": int(item.rotation()),
                    "font_family": item.text_item.document().defaultFont().family(),
                    "font_size": int(item.text_item.document().defaultFont().pointSize()),
                    "align": h_align,
                    "vertical_align": item.vertical_align,
                    "indent_px": int(fmt.textIndent()),
                    "line_height": float(f"{fmt.lineHeight() / 100.0:.2f}") if fmt.lineHeightType() == 1 else 1.15
                })
            
            # 2. Processar Assinaturas
            elif isinstance(item, SignatureItem):
                pos = item.pos()
                pix = item.pixmap()
                signatures_data.append({
                    "path": getattr(item, "_original_path", ""), # Precisaremos guardar isso no item
                    "x": int(pos.x()),
                    "y": int(pos.y()),
                    "width": int(pix.width()),
                    "height": int(pix.height()),
                    "longest_side": max(pix.width(), pix.height())
                })

        # Coleta placeholders na ordem visual definida pelo usuário
        ordered_placeholders = []
        for i in range(self.lst_placeholders.count()):
            ordered_placeholders.append(self.lst_placeholders.item(i).text())

        # Estrutura Final do Modelo V3
        data = {
            "name": "modelo_v3_projeto",
            "canvas_size": {"w": int(self.scene.width()), "h": int(self.scene.height())},
            "background_path": self.background_path,
            "placeholders": ordered_placeholders,
            "signatures": signatures_data,
            "boxes": boxes_data
        }
                
        # 1. Define o nome do arquivo/pasta (slug)
        from core.template_v2 import slugify_model_name
        model_name = self.windowTitle().replace("Editor Visual de Modelo - ", "")
        if not model_name or "AutoMakeCard" in model_name:
            model_name, ok = QInputDialog.getText(self, "Salvar Modelo", "Nome do Modelo:")
            if not ok or not model_name: return
            self.setWindowTitle(f"Editor Visual de Modelo - {model_name}")

        slug = slugify_model_name(model_name)
        model_dir = Path("models") / slug
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # --- Lógica de Assets (Portabilidade) ---
        # 1. Processa Background
        if self.background_path:
            rel_bg = self._import_asset(self.background_path, model_dir)
            data["background_path"] = rel_bg

        # 2. Processa Assinaturas
        for sig in data["signatures"]:
            # O item guarda o path original em "path", precisamos atualizá-lo no JSON
            rel_sig = self._import_asset(sig["path"], model_dir)
            if rel_sig:
                sig["path"] = rel_sig
        # ----------------------------------------

        file_path = model_dir / "template_v3.json"
        
        # 2. Salva o JSON
        data["name"] = model_name
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        # Avisa aos interessados: (Nome do Modelo, Variáveis)
        self.modelSaved.emit(model_name, data["placeholders"])
        
        QMessageBox.information(self, "Sucesso", f"Modelo '{model_name}' salvo com sucesso em:\n{file_path}")

    def update_signature_size(self, size):
        sel = self.scene.selectedItems()
        if sel and isinstance(sel[0], SignatureItem):
            sel[0].resize_by_longest_side(size)
    
    def load_background_image(self, path):
        """Carrega a imagem de fundo e ajusta o tamanho da cena."""
        from PySide6.QtGui import QPixmap
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        
        if self.bg_item:
            self.scene.removeItem(self.bg_item)
            
        self.background_path = path
        self.bg_item = self.scene.addPixmap(pixmap)
        self.bg_item.setZValue(-95) # Acima do fallback, abaixo dos itens
        
        # Ajusta a cena e a visualização para o tamanho exato da imagem
        rect = pixmap.rect()
        self.scene.setSceneRect(rect)
        self.view.setSceneRect(rect)
        
        # Oculta o fundo branco padrão
        self.fallback_bg.hide()

        # Ajusta o zoom para caber na tela
        self._zoom_to_fit()

    def _on_click_load_bg(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Fundo", "", "Imagens (*.png *.jpg *.jpeg)")
        if path:
            self.load_background_image(path)

    def _on_click_add_signature(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Assinatura", "", "Imagens (*.png)")
        if path:
            sig = SignatureItem(path)
            # Posiciona no centro da visão atual para facilitar
            center = self.view.mapToScene(self.view.viewport().rect().center())
            sig.setPos(center)
            self.scene.addItem(sig)

    def get_all_model_placeholders(self):
        """Varre o canvas e retorna o conjunto único de todos os placeholders."""
        placeholders = set()
        for item in self.scene.items():
            if isinstance(item, DesignerBox):
                placeholders.update(item.get_placeholders())
        return sorted(list(placeholders))
    
    def _on_content_updated(self, html):
        # Atualiza o texto na box (já existente)
        self.update_text_html(html)
        # Sincroniza lista visual
        self.sync_placeholders_list()
        self.refresh_layer_list()

    def load_from_json(self, file_path):
        """Carrega um modelo V3 e reconstrói o canvas."""
        import json
        path = Path(file_path)
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Limpa o canvas atual
        self.scene.clear()
        self.background_path = None
        self.bg_item = None
        
        # Restaura o tamanho da cena
        canvas_w = data.get("canvas_size", {}).get("w", 1000)
        canvas_h = data.get("canvas_size", {}).get("h", 1000)
        self.scene.setSceneRect(0, 0, canvas_w, canvas_h)
        
        # Recria o fallback (necessário pois o clear remove tudo)
        self.fallback_bg = self.scene.addRect(0, 0, canvas_w, canvas_h, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
        self.fallback_bg.setZValue(-100)

        # 2. Restaura o Fundo
        if data.get("background_path"):
            bg_path_raw = data["background_path"]
            # Resolve caminho relativo vs absoluto
            bg_path = path.parent / bg_path_raw if not Path(bg_path_raw).is_absolute() else Path(bg_path_raw)
            
            if bg_path.exists():
                self.load_background_image(str(bg_path))

        # 3. Restaura as Assinaturas
        from .canvas_items import SignatureItem
        for sig_data in data.get("signatures", []):
            raw_path = sig_data["path"]
            # Resolve caminho relativo
            sig_path = path.parent / raw_path if not Path(raw_path).is_absolute() else Path(raw_path)

            if sig_path.exists():
                sig = SignatureItem(str(sig_path))
                sig.setPos(sig_data["x"], sig_data["y"])
                sig.resize_by_longest_side(sig_data["longest_side"])
                self.scene.addItem(sig)

        # 4. Restaura as Caixas de Texto
        for b in data.get("boxes", []):
            # Criamos a box com as coordenadas e tamanho corretos
            box = DesignerBox(
                x=b.get("x", 0), 
                y=b.get("y", 0), 
                w=b.get("w", 300), 
                h=b.get("h", 60), 
                text=b.get("id", "Placeholder") # Texto puro inicial
            )
            
            # Agora aplicamos o HTML (texto rico) que contém a formatação (negrito, etc)
            if "html" in b:
                box.text_item.setHtml(b["html"])
                
                # [FIX CRÍTICO] Define a fonte padrão do documento para evitar reset ao editar
                from PySide6.QtGui import QFont
                default_font = QFont(b.get("font_family", "Arial"), b.get("font_size", 16))
                box.text_item.document().setDefaultFont(default_font)

            box.vertical_align = b.get("vertical_align", "top")

            # Aplica rotação
            box.setRotation(b.get("rotation", 0))
            box.update_center() # Ajusta o pivô

            # [FIX] Aplica o alinhamento horizontal visualmente ao carregar
            if "align" in b:
                box.set_alignment(b["align"])
            
            # Adicionamos à cena
            self.scene.addItem(box)
            
            # Força a atualização da posição do texto dentro da caixa
            box.recalculate_text_position()

            # 5. Restaura Ordem das Colunas (Placeholders)
            saved_placeholders = data.get("placeholders", [])
            self.lst_placeholders.clear()
            # Primeiro adiciona na ordem salva
            for p in saved_placeholders:
                self.lst_placeholders.addItem(p)
            # Depois roda o sync para garantir que nada faltou ou sobrou
            self.sync_placeholders_list()
            
            # Aplica recuo e entrelinha salvos
            box.set_block_format(
                indent=b.get("indent_px", 0),
                line_height=b.get("line_height", 1.15)
            )
        # Ajusta o zoom ao terminar de carregar
        self._zoom_to_fit()

        self.setWindowTitle(f"Editor Visual de Modelo - {data['name']}")
        self.refresh_layer_list()

    # --- SISTEMA DE CAMADAS (Helpers) ---
    def _get_next_layer_id(self):
        """Retorna o menor ID (0-99) disponível na cena."""
        used = set()
        for item in self.scene.items():
            if hasattr(item, 'layer_id') and item.layer_id is not None:
                used.add(item.layer_id)
        for i in range(100):
            if i not in used: return i
        return 99

    def _generate_layer_name(self, layer_id, item):
        """Gera o nome visual: '01_{texto}...'"""
        prefix = f"{layer_id:02d}"
        
        # Se for Caixa de Texto
        if isinstance(item, DesignerBox):
            raw = item.text_item.toPlainText().strip().replace("\n", " ")
            if len(raw) > 15: raw = raw[:12] + "..."
            if not raw: raw = "{vazio}"
            return f"{prefix}_{raw}"
            
        # Se for Assinatura
        elif isinstance(item, SignatureItem):
            return f"{prefix}_Assinatura"
            
        # Se for o Fundo
        if item == self.bg_item:
            return f"{prefix}_Fundo"
            
        return f"{prefix}_Objeto"

    def refresh_layer_list(self):
        """Reconstroi a lista da esquerda (Unidirecional: Cena -> Lista)."""
        self.layer_list.clear()
        
        # Pega itens da cena
        items = self.scene.items()
        
        valid_items = []
        for item in items:
            if isinstance(item, (DesignerBox, SignatureItem)) or item == self.bg_item:
                valid_items.append(item)
                
                # Garante ID se não tiver
                if not hasattr(item, 'layer_id') or item.layer_id is None:
                    item.layer_id = self._get_next_layer_id()

        # Adiciona na lista
        for item in valid_items:
            name = self._generate_layer_name(item.layer_id, item)
            list_item = QListWidgetItem(name)
            # Guarda a referência do objeto real "escondida" no item da lista
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.layer_list.addItem(list_item)

    def _on_layer_list_clicked(self, list_item):
        """
        Ao clicar na lista, selecionamos o objeto na cena.
        Isso dispara o 'selectionChanged' da cena naturalmente,
        o que fará o painel da direita carregar os dados.
        """
        target_item = list_item.data(Qt.ItemDataRole.UserRole)
        
        if target_item:
            # Limpa seleção anterior da cena
            self.scene.clearSelection()
            
            # Seleciona o novo item (Isso acorda o Editor da Direita)
            target_item.setSelected(True)
            
            # Garante que ele esteja visível na tela (scroll)
            self.view.ensureVisible(target_item)

            # [FIX] Devolve o foco do teclado para a View imediatamente.
            # Assim, as setas movem o objeto, e não a seleção da lista.
            self.view.setFocus()