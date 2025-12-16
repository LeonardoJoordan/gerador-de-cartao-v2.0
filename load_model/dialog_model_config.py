# load_model/dialog_model_config.py
from __future__ import annotations

import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QWidget, QMessageBox, QComboBox, 
    QTabWidget, QSplitter
)
from PySide6.QtCore import Qt

# Importamos o Core (Zona 1)
from core.svg_scanner import scan_svg
from core.model_v2 import build_model_from_scan, ModelV2, ModelBox


class ModelConfigDialog(QDialog):
    """
    Diálogo para analisar o SVG, visualizar as boxes/imagens detectadas
    e salvar o template_v2.json oficial.
    Agora integrado com o Scanner Real e ModelV2.
    """
    def __init__(self, parent=None, model_name=None, model_dir=None, svg_path=None):
        super().__init__(parent)
        
        # Tenta pegar contexto do parent se não passado explicitamente
        if parent and hasattr(parent, 'active_model_name'):
            self.model_name = parent.active_model_name
            # Assume estrutura padrão: models/{slug}/
            # (Na V3 o manager deve passar paths explícitos, por enquanto inferimos)
            from core.template_v2 import slugify_model_name
            slug = slugify_model_name(self.model_name)
            self.model_dir = Path(f"models/{slug}")
            self.svg_path = self.model_dir / "modelo.svg"
        else:
            self.model_name = model_name or "Desconhecido"
            self.model_dir = Path(model_dir) if model_dir else None
            self.svg_path = Path(svg_path) if svg_path else None

        self.output_pattern = "cartao_{nome}" 
        self.setWindowTitle(f"Configurar Modelo: {self.model_name}")
        self.resize(1100, 700)

        # Layout Principal
        main_layout = QVBoxLayout(self)

        # --- Topo: Info e Ações
        top_bar = QHBoxLayout()
        
        lbl_info = QLabel(f"<b>Modelo:</b> {self.model_name}<br><b>Pasta:</b> {self.model_dir}")
        top_bar.addWidget(lbl_info)
        top_bar.addStretch()

        self.btn_analyze = QPushButton("1. Analisar SVG (Scanner)")
        self.btn_analyze.setMinimumHeight(40)
        self.btn_analyze.setStyleSheet("background-color: #2c3e50; font-weight: bold;")
        self.btn_analyze.clicked.connect(self._on_analyze)
        top_bar.addWidget(self.btn_analyze)

        main_layout.addLayout(top_bar)

        # --- Corpo: Abas (Boxes e Imagens)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # ABA 1: Boxes (Texto e Layout)
        self.tab_boxes = QWidget()
        self._init_tab_boxes()
        self.tabs.addTab(self.tab_boxes, "Camadas de Texto (Boxes)")

        # ABA 2: Imagens (Assets)
        self.tab_images = QWidget()
        self._init_tab_images()
        self.tabs.addTab(self.tab_images, "Ativos de Imagem")

        # --- Rodapé: Salvar
        bottom_bar = QHBoxLayout()
        self.btn_save = QPushButton("2. Salvar Configuração (JSON)")
        self.btn_save.setMinimumHeight(45)
        self.btn_save.setStyleSheet("background-color: #27ae60; font-weight: bold;")
        self.btn_save.clicked.connect(self._on_save)
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)

        bottom_bar.addStretch()
        bottom_bar.addWidget(self.btn_cancel)
        bottom_bar.addWidget(self.btn_save)

        main_layout.addLayout(bottom_bar)
        
        # Estado interno
        self.current_model_v2: ModelV2 | None = None

    def _init_tab_boxes(self):
        layout = QVBoxLayout(self.tab_boxes)
        
        # Tabela
        self.table_boxes = QTableWidget()
        cols = ["Ativo", "Origem", "ID (SVG)", "Preview Texto", "Align", "Font", "Size", "Color", "Indent", "LineH"]
        self.table_boxes.setColumnCount(len(cols))
        self.table_boxes.setHorizontalHeaderLabels(cols)
        self.table_boxes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Coluna preview estica
        self.table_boxes.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.table_boxes)

    def _init_tab_images(self):
        layout = QVBoxLayout(self.tab_images)
        
        self.table_images = QTableWidget()
        cols = ["ID (SVG)", "Tipo", "Caminho Relativo (src)", "Geometria (x, y, w, h)", "Z-Index"]
        self.table_images.setColumnCount(len(cols))
        self.table_images.setHorizontalHeaderLabels(cols)
        self.table_images.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.table_images)

    def _on_analyze(self):
        """Executa o scanner e popula a UI."""
        if not self.svg_path or not self.svg_path.exists():
            QMessageBox.critical(self, "Erro", f"Arquivo SVG não encontrado:\n{self.svg_path}")
            return

        try:
            # 1. Scanner (Zona 1) - Extrai raw data e salva assets
            scan_result = scan_svg(self.svg_path, output_model_dir=self.model_dir)
            
            # 2. Model Builder (Zona 1) - Consolida lógica
            self.current_model_v2 = build_model_from_scan(scan_result)
            
            # 3. Preenche UI
            self._fill_boxes_table(self.current_model_v2)
            self._fill_images_table(self.current_model_v2)
            
            QMessageBox.information(self, "Sucesso", 
                f"Análise concluída!\n"
                f"- Boxes detectadas: {len(self.current_model_v2.boxes_by_id)}\n"
                f"- Imagens extraídas: {len(self.current_model_v2.images)}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Erro Fatal", f"Falha ao analisar SVG:\n{e}")

    def _fill_boxes_table(self, model: ModelV2):
        self.table_boxes.setRowCount(0)
        
        # Ordena boxes (idealmente por z-index, aqui por ordem de processamento)
        boxes = model.boxes_in_order()
        
        self.table_boxes.setRowCount(len(boxes))
        
        for row, box in enumerate(boxes):
            # Col 0: Checkbox (Editable/Ativo)
            item_check = QTableWidgetItem()
            item_check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            # Por padrão, se tiver texto, marcamos como ativo
            state = Qt.CheckState.Checked if box.template_text else Qt.CheckState.Unchecked
            item_check.setCheckState(state)
            self.table_boxes.setItem(row, 0, item_check)

            # Col 1: Origem (Tag)
            # Infere origem baseada nos dados
            origin = "UNKNOWN"
            if box.w > 0 and box.template_text:
                origin = "MERGED" # Rect + Text
            elif box.w > 0:
                origin = "LAYOUT" # Só Rect
            elif box.template_text:
                origin = "TEXT"   # Só Text
            
            item_origin = QTableWidgetItem(origin)
            item_origin.setFlags(Qt.ItemFlag.ItemIsEnabled) # Read-only
            self.table_boxes.setItem(row, 1, item_origin)

            # Col 2: ID
            item_id = QTableWidgetItem(box.id)
            item_id.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table_boxes.setItem(row, 2, item_id)

            # Col 3: Preview Texto
            self.table_boxes.setItem(row, 3, QTableWidgetItem(box.template_text))

            # Col 4: Align (Combo)
            cmb_align = QComboBox()
            cmb_align.addItems(["left", "center", "right", "justify"])
            cmb_align.setCurrentText(box.align)
            self.table_boxes.setCellWidget(row, 4, cmb_align)

            # Col 5: Font (Combo simples ou LineEdit)
            # Para MVP: LineEdit
            self.table_boxes.setItem(row, 5, QTableWidgetItem(box.font))

            # Col 6: Size
            self.table_boxes.setItem(row, 6, QTableWidgetItem(str(int(box.size))))

            # Col 7: Color
            self.table_boxes.setItem(row, 7, QTableWidgetItem(box.color))
            
            # Col 8: Indent
            self.table_boxes.setItem(row, 8, QTableWidgetItem(str(box.indent_px)))

            # Col 9: LineHeight
            self.table_boxes.setItem(row, 9, QTableWidgetItem(str(box.line_height)))
            
            # Guardamos o objeto box na linha para referência futura se precisar
            item_origin.setData(Qt.ItemDataRole.UserRole, box)

    def _fill_images_table(self, model: ModelV2):
        self.table_images.setRowCount(0)
        self.table_images.setRowCount(len(model.images))
        
        for row, img in enumerate(model.images):
            # ID
            self.table_images.setItem(row, 0, QTableWidgetItem(img.element_id))
            
            # Tipo (Detecção simples por ID)
            role = "Asset"
            if "fundo" in img.element_id.lower() or "background" in img.element_id.lower():
                role = "BACKGROUND"
            elif "assinatura" in img.element_id.lower():
                role = "OVERLAY"
            self.table_images.setItem(row, 1, QTableWidgetItem(role))
            
            # Path
            self.table_images.setItem(row, 2, QTableWidgetItem(img.src_relative_path))
            
            # Geometria
            geo = f"{img.x:.0f}, {img.y:.0f} | {img.w:.0f}x{img.h:.0f}"
            self.table_images.setItem(row, 3, QTableWidgetItem(geo))
            
            # Z
            self.table_images.setItem(row, 4, QTableWidgetItem(str(img.z_index)))

    def _on_save(self):
        if not self.current_model_v2:
            QMessageBox.warning(self, "Aviso", "Analise o SVG primeiro.")
            return

        # Reconstrói lista de boxes baseada na tabela (usuário pode ter editado valores)
        final_boxes = []
        
        for r in range(self.table_boxes.rowCount()):
            # Se não estiver checado, ignora (ou salva como hidden? Por enquanto ignora)
            checked = self.table_boxes.item(r, 0).checkState() == Qt.CheckState.Checked
            if not checked:
                continue
            
            # Recupera dados das células
            b_id = self.table_boxes.item(r, 2).text()
            b_preview = self.table_boxes.item(r, 3).text()
            
            widget_align = self.table_boxes.cellWidget(r, 4)
            b_align = widget_align.currentText() if widget_align else "left"
            
            b_font = self.table_boxes.item(r, 5).text()
            b_size = float(self.table_boxes.item(r, 6).text() or 32)
            b_color = self.table_boxes.item(r, 7).text()
            b_indent = int(self.table_boxes.item(r, 8).text() or 0)
            b_lh = float(self.table_boxes.item(r, 9).text() or 1.15)

            # Recupera geometria original da box (está guardada no UserRole da col 1)
            original_box: ModelBox = self.table_boxes.item(r, 1).data(Qt.ItemDataRole.UserRole)
            
            box_dict = {
                "id": b_id,
                "x": int(original_box.x),
                "y": int(original_box.y),
                "w": int(original_box.w),
                "h": int(original_box.h),
                "align": b_align,
                "font": b_font,
                "size": int(b_size),
                "color": b_color,
                "line_height": b_lh,
                "indent_px": b_indent,
                "editable": False, # Futuro: checkbox na tabela
                "default_text": b_preview # Salva o texto do SVG como default
            }
            final_boxes.append(box_dict)

        # Detecta background (pega o primeiro asset marcado como BACKGROUND ou o primeiro asset geral)
        bg_file = "background.png" # Default
        for img in self.current_model_v2.images:
            if "fundo" in img.element_id.lower() or "background" in img.element_id.lower():
                bg_file = img.src_relative_path
                break
            # Fallback: se houver imagem grande
            if img.w > 500 and img.h > 500:
                bg_file = img.src_relative_path

        template_data = {
            "name": self.model_name,
            "dpi": 300, # TODO: Ler do SVG se possível
            "size_px": {"w": 1000, "h": 1000}, # TODO: Ler do SVG root width/height
            "background": bg_file,
            "boxes": final_boxes
        }

        # Tenta pegar tamanho real se tiver um rect de fundo ou do viewbox (implementação futura)
        # Por enquanto mantemos 1000x1000 ou o que vier do background se lermos o arquivo
        
        try:
            out_path = self.model_dir / "template_v2.json"
            out_path.write_text(json.dumps(template_data, indent=2, ensure_ascii=False), encoding="utf-8")
            
            QMessageBox.information(self, "Salvo", f"Template salvo com sucesso em:\n{out_path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar", str(e))