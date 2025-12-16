from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QPushButton, QApplication
from PySide6.QtCore import Qt

from ui.preview_panel import PreviewPanel
from ui.controls_panel import ControlsPanel
from ui.log_panel import LogPanel
from ui.table_panel import TablePanel

from load_model.dialog_model_config import ModelConfigDialog
from load_model.dialog_model_manager import ModelManagerDialog

from core.naming import build_output_filename
from core.template_v2 import load_template_for_model, TemplateError
from core.typography_engine import TypographyEngine
from core.svg_scanner import scan_svg
from core.model_v2 import build_model_from_scan
from core.compositor import compose_png_over_background


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoMakeCard V2")
        self.resize(1300, 750)

        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        self.current_output_pattern = "cartao_{nome}"

        # --- Painel ESQUERDO (Preview + Controles + Log)
        left = QWidget()
        splitter.addWidget(left)

        left_stack = QVBoxLayout(left)
        left_stack.setContentsMargins(0, 0, 0, 0)
        left_stack.setSpacing(10)

        self.preview_panel = PreviewPanel()

        # Modelos fake só para teste visual (depois virão do catálogo)
        self.preview_panel.cbo_models.addItems([
            "Cartão Aniversário",
            "Cartão Promoção",
            "Cartão Despedida",
            "Cartão Boas-vindas",
            "Cartão Condolências"
        ])

        self.controls_panel = ControlsPanel()
        self.log_panel = LogPanel()
        # Engine tipográfico (Playwright)
        self.typo_engine = TypographyEngine()

        left_stack.addWidget(self.preview_panel, 5)
        left_stack.addWidget(self.controls_panel, 0)
        left_stack.addWidget(self.log_panel, 3)

        # modelo ativo (vamos usar isso pra achar models/<slug>/template_v2.json)
        self.active_model_name = self.preview_panel.cbo_models.currentText()

        # atualiza preview + log já na inicialização (agora o log_panel já existe)
        self._on_model_changed(self.active_model_name)

        self.btn_generate_cards = QPushButton("Gerar cartões")
        self.btn_generate_cards.setMinimumHeight(44)  # opcional: deixa mais “botão principal”
        self.btn_generate_cards.clicked.connect(self._generate_cards_placeholder)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.typo_engine.close)
            left_stack.addWidget(self.btn_generate_cards, 0)

        # --- Painel DIREITO (Tabela)
        self.table_panel = TablePanel()
        splitter.addWidget(self.table_panel)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        # Por enquanto: abrir diálogo no botão "Configurar modelo"
        self.controls_panel.btn_config_model.clicked.connect(self._open_model_dialog)
        self.controls_panel.btn_manage_models.clicked.connect(self._open_models_manager)

    def _generate_cards_placeholder(self):
        used = set()

        # lê a tabela da direita e cria “linhas” (dict coluna->valor)
        table = self.table_panel.table
        headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]

        rows_plain = []
        rows_rich = []

        for r in range(table.rowCount()):
            row_plain = {}
            row_rich = {}
            empty = True

            for c, col in enumerate(headers):
                item = table.item(r, c)

                plain = (item.text() if item else "") or ""
                plain = plain.strip()

                # rich: pega do UserRole (se existir), senão usa plain
                rich = ""
                if item:
                    rich = item.data(Qt.ItemDataRole.UserRole) or ""
                rich = str(rich).strip() if rich else plain

                if plain:
                    empty = False

                row_plain[col] = plain
                row_rich[col] = rich

            if not empty:
                rows_plain.append(row_plain)
                rows_rich.append(row_rich)

        if not rows_plain:
            self.log_panel.append("Nenhuma linha válida na tabela para gerar.")
            return
        
        # guarda para as próximas etapas (motor tipográfico vai usar rows_rich)
        self._last_rows_plain = rows_plain
        self._last_rows_rich = rows_rich

        # --- Etapa atual (V2): carregar template do modelo ativo (sem render ainda)
        try:
            tpl, model_dir = load_template_for_model(self.active_model_name)
            self.log_panel.append(
                f"Template carregado: {tpl.name} | "
                f"{tpl.width}x{tpl.height}px | "
                f"boxes={len(tpl.boxes)} | "
                f"pasta={model_dir}"
            )

            # --- Scanner SVG (ATUALIZADO PARA NOVO FLUXO)
            try:
                svg_path = model_dir / "modelo.svg"
                scan = scan_svg(svg_path, output_model_dir=model_dir) # Passamos dir para salvar imagens

                # Logs ajustados para a nova estrutura do ScanResult
                self.log_panel.append(f"Scanner Raw:")
                self.log_panel.append(f"  - Textos detectados: {len(scan.texts)}")
                self.log_panel.append(f"  - Áreas (Rects): {len(scan.rects)}")
                self.log_panel.append(f"  - Imagens (Assets): {len(scan.images)}")
                
                for img in scan.images:
                    self.log_panel.append(f"    [IMG] id='{img.element_id}' path='{img.src_relative_path}'")

            except Exception as e:
                self.log_panel.append(f"ERRO scanner SVG: {e}")
                # Se falhar scanner, não tem como continuar muito bem
                return

            # --- Modelo interno (V2): construir estrutura consolidada
            model_v2 = build_model_from_scan(scan)

            self.log_panel.append(f"ModelV2 Consolidado: {len(model_v2.boxes_by_id)} boxes ativas")
            
            # Log das boxes consolidadas (Rect + Text mergeados)
            for b in model_v2.boxes_in_order():
                self.log_panel.append(
                    f"BOX[{b.id}] "
                    f"geo=({b.x},{b.y},{b.w},{b.h}) "
                    f"font='{b.font}' size={b.size} "
                    f"align={b.align}"
                )
                if b.template_text:
                    self.log_panel.append(f"  texto: '{b.template_text}'")

            # Placeholders agora vêm do model_v2
            if model_v2.all_placeholders:
                self.log_panel.append(f"Placeholders totais: {sorted(model_v2.all_placeholders)}")
            else:
                self.log_panel.append("Placeholders: (nenhum)")

            self.log_panel.append(f"Colunas para preencher: {model_v2.placeholder_columns()}")

            # --- Prova de resolução (V2): template_text + placeholders + rich
            row_plain_0 = self._last_rows_plain[0]
            row_rich_0 = self._last_rows_rich[0]

            self.log_panel.append("=== RESOLVE (linha 0) ===")
            for b in model_v2.boxes_in_order():
                resolved = model_v2.resolve_box_text(b, row_plain_0, row_rich_0)
                # Só loga se tiver conteudo resolvido pra nao poluir
                if resolved:
                    self.log_panel.append(f"[{b.id}] -> {resolved[:50]}...")

            # --- Render overlay FULL (todas as boxes presentes no template_v2)
            render_boxes = []

            # index rápido: boxes do template JSON por id (para pegar configs salvas se houver)
            # Nota: O template_v2.json pode estar desatualizado em relação ao SVG recém escaneado.
            # Idealmente, deveríamos usar o model_v2 como fonte primária de geometria agora?
            # Por enquanto, mantemos a lógica: JSON é soberano SE existir. Se não, usamos model_v2.
            
            tpl_by_id = {}
            for tb in tpl.boxes:
                tb_id = str(tb.get("id", "")).strip()
                if tb_id:
                    tpl_by_id[tb_id] = tb

            for mb in model_v2.boxes_in_order():
                # Tenta pegar config do JSON, senão usa do scan (model_v2)
                tb = tpl_by_id.get(mb.id, {})
                
                # Geometria: JSON > Model (Scan)
                # Se JSON tiver w=0, talvez devêssemos usar do scan? 
                # Vamos assumir que se está no JSON, está certo.
                
                # Resolve texto
                html_text = model_v2.resolve_box_text(mb, row_plain_0, row_rich_0)

                # Prioridade de valores: Template JSON > Model (Scan)
                final_x = tb.get("x", mb.x)
                final_y = tb.get("y", mb.y)
                final_w = tb.get("w", mb.w)
                final_h = tb.get("h", mb.h)
                
                final_align = tb.get("align", mb.align)
                final_font = tb.get("font", mb.font)
                final_size = tb.get("size", mb.size)
                final_color = tb.get("color", mb.color)
                
                final_lh = tb.get("line_height", mb.line_height)
                final_indent = tb.get("indent_px", mb.indent_px)

                # Se width for 0 (veio de <text> solto e não tem no JSON), o engine vai ter que lidar.
                # O TypographyEngine atual usa w para o canvas. Se w=0, pode dar problema.
                if final_w <= 0: final_w = tpl.width  # Fallback seguro
                if final_h <= 0: final_h = tpl.height # Fallback seguro

                render_boxes.append({
                    "id": mb.id,
                    "x": final_x,
                    "y": final_y,
                    "w": final_w,
                    "h": final_h,
                    "align": final_align,
                    "font": final_font,
                    "size": final_size,
                    "color": final_color,
                    "line_height": final_lh,
                    "indent_px": final_indent,
                    "html_text": html_text,
                })

            out_full = model_dir / "debug_overlay_full.png"
            self.typo_engine.render_overlay_multi_boxes(
                width=tpl.width,
                height=tpl.height,
                boxes=render_boxes,
                out_path=out_full
            )
            self.log_panel.append(f"Overlay FULL gerado: {out_full}")

            # --- Composição (background + overlay) -> final
            bg_path = model_dir / tpl.background  # vem do template_v2.json
            out_final = model_dir / "debug_final.png"

            # TODO: Aqui deveríamos usar as imagens extraídas pelo Scanner (model_v2.images)
            # Se o template JSON diz "background.png", mas o scanner achou "assets/fundo.png", 
            # precisamos alinhar isso. Por enquanto mantemos o fluxo antigo.

            if not bg_path.exists():
                self.log_panel.append(f"AVISO: Background não encontrado em {bg_path}")
            else:
                compose_png_over_background(
                    background_path=bg_path,
                    overlay_path=out_full,
                    out_path=out_final,
                )
                self.log_panel.append(f"FINAL (debug) gerado: {out_final}")


        except TemplateError as e:
            self.log_panel.append(f"ERRO template: {e}")
            return
        
        # --- MVP V2: Gerar nomes (mantido igual)
        self.log_panel.append(f"Gerando nomes (pattern: {self.current_output_pattern})")
        
        for row in rows_plain:
            name = build_output_filename(self.current_output_pattern, row, used)
            # self.log_panel.append(f"Arquivo: {name}.png") # Desabilitado pra não floodar

    def _open_models_manager(self):
        # Pega a lista atual do ComboBox (por enquanto ela é nossa "fonte de modelos")
        models = [self.preview_panel.cbo_models.itemText(i) for i in range(self.preview_panel.cbo_models.count())]

        dlg = ModelManagerDialog(self, initial_models=models)
        if dlg.exec() and dlg.selected_model_name:
            # Atualiza combo para refletir a lista do diálogo (por enquanto, só reconstruímos)
            self.preview_panel.cbo_models.blockSignals(True)
            self.preview_panel.cbo_models.clear()
            for i in range(dlg.list_models.count()):
                self.preview_panel.cbo_models.addItem(dlg.list_models.item(i).text())
            self.preview_panel.cbo_models.blockSignals(False)

            # Seleciona o modelo escolhido
            idx = self.preview_panel.cbo_models.findText(dlg.selected_model_name)
            if idx >= 0:
                self.preview_panel.cbo_models.setCurrentIndex(idx)

            self.log_panel.append(f"Modelo selecionado no gerenciador: {dlg.selected_model_name}")
        else:
            self.log_panel.append("Gerenciar modelos: fechado sem selecionar.")

    def _on_model_changed(self, name: str):
        self.preview_panel.set_preview_text(f"Prévia do modelo selecionado:\n{name}")
        self.log_panel.append(f"Modelo ativo: {name}")
        self.active_model_name = name


    def _open_model_dialog(self):
        # ATENÇÃO: ModelConfigDialog ainda precisa de update para o novo scanner
        # Se abrir agora e clicar em "Analisar", vai crashar.
        # Vamos tratar isso no próximo passo.
        dlg = ModelConfigDialog(self)
        if dlg.exec():
            self.log_panel.append("Modelo configurado (Etapa 1): diálogo confirmado.")

            if getattr(dlg, "output_pattern", ""):
                self.current_output_pattern = dlg.output_pattern
                self.log_panel.append(f"Padrão de saída definido: {self.current_output_pattern}")
        else:
            self.log_panel.append("Configuração de modelo cancelada.")