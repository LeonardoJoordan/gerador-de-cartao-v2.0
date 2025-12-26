from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QPushButton, QApplication
from PySide6.QtCore import Qt

from ui.preview_panel import PreviewPanel
from ui.controls_panel import ControlsPanel
from ui.log_panel import LogPanel
from ui.table_panel import TablePanel

from ui.editor.editor_window import EditorWindow
from load_model.dialog_model_manager import ModelManagerDialog

from core.naming import build_output_filename
from core.template_v2 import load_template_for_model, TemplateError


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

            # --- Scanner SVG (teste controlado)
            try:
                svg_path = model_dir / "modelo.svg"
                scan = scan_svg(svg_path)

                self.log_panel.append(f"Scanner: {len(scan.boxes)} boxes detectadas")
                for box in scan.boxes:
                    self.log_panel.append(
                        f"BOX id='{box.element_id}' | texto='{box.template_text}'"
                    )

                if scan.placeholders:
                    self.log_panel.append(
                        f"Placeholders encontrados: {sorted(scan.placeholders)}"
                    )
                else:
                    self.log_panel.append("Nenhum placeholder encontrado no SVG")

            except Exception as e:
                self.log_panel.append(f"ERRO scanner SVG: {e}")

            # --- Modelo interno (V2): construir estrutura a partir do scan
            model_v2 = build_model_from_scan(scan)

            self.log_panel.append(f"ModelV2: {len(model_v2.boxes_by_id)} boxes no total")
            for b in model_v2.boxes_in_order():
                self.log_panel.append(
                    f"BOX[{b.id}] editable={b.editable} align={b.align} indent_px={b.indent_px} line_height={b.line_height}"
                )
                self.log_panel.append(f"  template_text: {b.template_text}")
                if b.placeholders():
                    self.log_panel.append(f"  placeholders: {sorted(b.placeholders())}")
                else:
                    self.log_panel.append("  placeholders: (nenhum)")

            self.log_panel.append(f"Colunas placeholders: {model_v2.placeholder_columns()}")
            self.log_panel.append(f"Colunas editáveis por ID (por enquanto vazias): {model_v2.editable_columns()}")

            # --- Prova de resolução (V2): template_text + placeholders + rich
            row_plain_0 = self._last_rows_plain[0]
            row_rich_0 = self._last_rows_rich[0]

            self.log_panel.append("=== RESOLVE (linha 0) ===")
            for b in model_v2.boxes_in_order():
                resolved = model_v2.resolve_box_text(b, row_plain_0, row_rich_0)
                self.log_panel.append(f"[{b.id}] -> {resolved}")

            # --- Render overlay FULL (todas as boxes presentes no template_v2)
            render_boxes = []

            # index rápido: boxes do template por id
            tpl_by_id = {}
            for tb in tpl.boxes:
                tb_id = str(tb.get("id", "")).strip()
                if tb_id:
                    tpl_by_id[tb_id] = tb

            for mb in model_v2.boxes_in_order():
                tb = tpl_by_id.get(mb.id)
                if not tb:
                    continue  # existe no SVG mas não existe no template_v2 (ok por enquanto)

                html_text = model_v2.resolve_box_text(mb, row_plain_0, row_rich_0)

                # defaults inteligentes:
                # - se for "mensagem" e ainda estiver left, assumimos justify + recuo padrão
                align = mb.align
                indent_px = mb.indent_px
                line_height = mb.line_height

                if mb.id.lower() == "mensagem":
                    if align == "left":
                        align = "justify"
                    if indent_px == 0:
                        indent_px = 40
                    if abs(line_height - 1.15) < 1e-6:
                        line_height = 1.35

                render_boxes.append({
                    "id": mb.id,
                    "x": tb.get("x", 0),
                    "y": tb.get("y", 0),
                    "w": tb.get("w", tpl.width),
                    "h": tb.get("h", tpl.height),
                    "align": tb.get("align", align),  # se template tiver align, ele manda por enquanto
                    "font": tb.get("font", "DejaVu Sans"),
                    "size": tb.get("size", 32),
                    "color": tb.get("color", "#FFFFFF"),
                    "line_height": line_height,
                    "indent_px": indent_px,
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
        
        # --- MVP V2: gerar 1 overlay (apenas caixa 'nome') usando a primeira linha rich
        try:
            row_rich_0 = self._last_rows_rich[0]
            nome_html = row_rich_0.get("nome", "")

            # acha a box "nome" dentro do template
            box_nome = None
            for b in tpl.boxes:
                if str(b.get("id", "")).strip().lower() == "nome":
                    box_nome = b
                    break

            if not box_nome:
                self.log_panel.append("ERRO: template não possui box com id='nome'")
                return

            out_overlay = model_dir / "debug_overlay_nome.png"
            self.typo_engine.render_overlay_one_box(
                width=tpl.width,
                height=tpl.height,
                box=box_nome,
                html_text=nome_html,
                out_path=out_overlay
            )
            self.log_panel.append(f"Overlay gerado (MVP): {out_overlay}")
        except Exception as e:
            self.log_panel.append(f"ERRO ao gerar overlay MVP: {e}")
            return

        self.log_panel.append(f"Gerando nomes (pattern: {self.current_output_pattern})")
        
        for row in rows_plain:
            name = build_output_filename(self.current_output_pattern, row, used)
            self.log_panel.append(f"Arquivo: {name}.png")

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
        """
        Abre o novo Editor Visual em vez do configurador antigo.
        """
        self.log_panel.append("Abrindo Editor Visual...")
        
        # Mantemos 'self' como pai para a janela não se perder
        self.editor_window = EditorWindow(self)
        self.editor_window.show()
