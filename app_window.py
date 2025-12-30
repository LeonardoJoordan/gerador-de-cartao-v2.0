# app_window.py
from pathlib import Path
import shutil
import json
from datetime import datetime
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                                QSplitter, QPushButton, QApplication, QMessageBox,
                                  QLineEdit, QLabel, QFileDialog, QProgressBar,
                                  QInputDialog) # <--- Certifique-se que QInputDialog está aqui
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPainter, QImage, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from ui.preview_panel import PreviewPanel
from ui.controls_panel import ControlsPanel
from ui.log_panel import LogPanel
from ui.table_panel import TablePanel
from core.renderer_v3 import NativeRenderer
from ui.editor.editor_window import EditorWindow
from core.worker import RenderManager
from core.template_v2 import slugify_model_name
from ui.naming_dialog import NamingDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Cartões em Lote - GCL")
        self.resize(1300, 750)

        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        self.current_filename_suffix = "" 
        self.manager = None 

        # --- Painel ESQUERDO ---
        left = QWidget()
        left.setMinimumWidth(620)
        splitter.addWidget(left)

        left_stack = QVBoxLayout(left)
        left_stack.setContentsMargins(0, 0, 0, 0)
        left_stack.setSpacing(10)

        self.preview_panel = PreviewPanel()
        self.controls_panel = ControlsPanel()
        self.log_panel = LogPanel()

        left_stack.addWidget(self.preview_panel, 5)
        left_stack.addWidget(self.controls_panel, 0)
        left_stack.addWidget(self.log_panel, 3)

        # --- BARRA DE PROGRESSO ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent; /* Fundo transparente (mesma cor do app) */
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 4px;
            }
        """)
        left_stack.addWidget(self.progress_bar, 0)

        # --- Seletor de Pasta ---
        grp_out = QWidget()
        ly_out = QHBoxLayout(grp_out)
        ly_out.setContentsMargins(0, 0, 0, 0)
        ly_out.setSpacing(5)

        ly_out.addWidget(QLabel("Saída:"))
        
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setPlaceholderText("Padrão: ./output/nome_do_modelo")
        ly_out.addWidget(self.txt_output_path)

        self.btn_sel_out = QPushButton("...")
        self.btn_sel_out.setFixedWidth(40)
        self.btn_sel_out.setToolTip("Selecionar pasta de destino")
        self.btn_sel_out.clicked.connect(self._select_output_folder)
        ly_out.addWidget(self.btn_sel_out)

        self.btn_config_name = QPushButton("⚙️")
        self.btn_config_name.setFixedWidth(40)
        self.btn_config_name.setToolTip("Configurar padrão de nome dos arquivos")
        self.btn_config_name.clicked.connect(self._open_naming_dialog)
        ly_out.addWidget(self.btn_config_name)

        left_stack.addWidget(grp_out, 0)

        self.btn_generate_cards = QPushButton("Gerar cartões")
        self.btn_generate_cards.setMinimumHeight(44)
        self.btn_generate_cards.clicked.connect(self._generate_cards_async)
        left_stack.addWidget(self.btn_generate_cards, 0)

        # --- Painel DIREITO ---
        self.table_panel = TablePanel()
        splitter.addWidget(self.table_panel)

        splitter.setSizes([620, 820])
        splitter.setCollapsible(0, False)

        self.cached_model_data = None
        
        self._reload_models_from_disk()
        
        self.active_model_name = self.preview_panel.cbo_models.currentText()
        self._on_model_changed(self.active_model_name)

        self.preview_panel.cbo_models.currentTextChanged.connect(self._on_model_changed)
        self.table_panel.table.itemSelectionChanged.connect(self._on_table_selection)

        # --- Conexões dos Botões de Controle ---
        self.controls_panel.btn_add_model.clicked.connect(self._on_add_model)
        self.controls_panel.btn_duplicate_model.clicked.connect(self._on_duplicate_model)
        self.controls_panel.btn_remove_model.clicked.connect(self._on_remove_model)
        self.controls_panel.btn_rename_model.clicked.connect(self._on_rename_model) # [NOVO]
        self.controls_panel.btn_config_model.clicked.connect(self._open_model_dialog)

        self.settings = QSettings("Gerador de Cartões em Lote - GCL", "MainApp")
        last_output = self.settings.value("last_output_dir", "")
        if last_output:
            self.txt_output_path.setText(str(last_output))

    # --- [NOVO] Lógica de Renomear ---
    def _on_rename_model(self):
        # [FIX] Fonte da verdade é a UI
        old_name = self.preview_panel.cbo_models.currentText()
        
        if not old_name:
            QMessageBox.warning(self, "Atenção", "Selecione um modelo para renomear.")
            return

        # 1. Pede o novo nome
        new_name, ok = QInputDialog.getText(self, "Renomear Modelo", "Novo nome:", text=old_name)
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        if new_name == old_name:
            return

        # 2. Prepara caminhos
        old_slug = slugify_model_name(old_name)
        new_slug = slugify_model_name(new_name)
        
        old_dir = Path("models") / old_slug
        new_dir = Path("models") / new_slug

        if new_dir.exists():
            QMessageBox.warning(self, "Erro", f"Já existe um modelo com o slug '{new_slug}'.")
            return

        try:
            # 3. Renomeia a pasta
            old_dir.rename(new_dir)
            
            # 4. Atualiza o JSON interno (senão o nome antigo continua aparecendo na lista)
            json_path = new_dir / "template_v3.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                data["name"] = new_name
                
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            
            self.log_panel.append(f"Modelo renomeado: '{old_name}' -> '{new_name}'")
            
            # 5. Recarrega interface
            self._reload_models_from_disk(select_name=new_name)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao renomear: {e}")

    # --- Métodos Existentes (Duplicar, Adicionar, etc) ---
    def _on_duplicate_model(self):
        # [FIX] Lê diretamente da UI para garantir que não estamos usando um cache obsoleto
        original_name = self.preview_panel.cbo_models.currentText()
        
        if not original_name:
            QMessageBox.warning(self, "Atenção", "Selecione um modelo para duplicar.")
            return

        original_slug = slugify_model_name(original_name)
        original_dir = Path("models") / original_slug

        if not original_dir.exists():
            self.log_panel.append("ERRO: Pasta do modelo original não encontrada.")
            return

        counter = 1
        while True:
            suffix = " (Cópia)" if counter == 1 else f" (Cópia {counter})"
            new_name = f"{original_name}{suffix}"
            new_slug = slugify_model_name(new_name)
            new_dir = Path("models") / new_slug
            
            if not new_dir.exists():
                break
            counter += 1

        try:
            shutil.copytree(original_dir, new_dir)
            
            json_path = new_dir / "template_v3.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["name"] = new_name
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

            self.log_panel.append(f"Modelo duplicado: '{new_name}'")
            self._reload_models_from_disk(select_name=new_name)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao duplicar modelo:\n{e}")
            if new_dir.exists():
                shutil.rmtree(new_dir, ignore_errors=True)

    def _open_naming_dialog(self):
        # [FIX] Fonte da verdade é a UI
        current_model_name = self.preview_panel.cbo_models.currentText()
        if not current_model_name:
            QMessageBox.warning(self, "Atenção", "Selecione um modelo primeiro.")
            return
            
        # Garante que active_model_name esteja sincronizado caso precise dele depois
        self.active_model_name = current_model_name

        # 1. Recupera Variáveis
        cols = self.table_panel.table.columnCount()
        vars_available = [self.table_panel.table.horizontalHeaderItem(c).text() for c in range(cols)]
        
        slug = slugify_model_name(self.active_model_name)
        
        # 2. Recupera Dados do Modelo (Dimensões e Config Atual)
        current_imposition = None
        model_size = (1000, 1000) # Default seguro

        if self.cached_model_data:
            sz = self.cached_model_data.get("canvas_size", {})
            model_size = (sz.get("w", 1000), sz.get("h", 1000))
            current_imposition = self.cached_model_data.get("imposition_settings") # Lê config salva

        # 3. Abre Dialog
        dlg = NamingDialog(self, slug, vars_available, self.current_filename_suffix, 
                           model_size_px=model_size, 
                           current_imposition=current_imposition)
        
        if dlg.exec():
            new_suffix = dlg.get_pattern()
            new_imposition = dlg.get_imposition_settings() # Pega novos settings
            
            self.current_filename_suffix = new_suffix
            
            # 4. Salvar tudo no JSON do modelo
            json_path = Path("models") / slug / "template_v3.json"
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    data["output_suffix"] = new_suffix
                    data["imposition_settings"] = new_imposition # Salva a nova seção
                    
                    # Atualiza o cache em memória também
                    if self.cached_model_data:
                        self.cached_model_data["output_suffix"] = new_suffix
                        self.cached_model_data["imposition_settings"] = new_imposition

                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    print(f"Erro ao salvar config: {e}")

            # Feedback no log
            msg_imp = " [Imposição A4 ATIVADA]" if new_imposition["enabled"] else ""
            if self.current_filename_suffix:
                self.log_panel.append(f"Configuração salva: {slug}_{self.current_filename_suffix}.png{msg_imp}")
            else:
                self.log_panel.append(f"Configuração salva: Sequencial automático{msg_imp}")

    def _generate_cards_async(self):
        rows_plain, rows_rich = self._scrape_table_data()
        if not rows_plain:
            self.log_panel.append("AVISO: A tabela está vazia. Nada a gerar.")
            return

        # [FIX] Obtém o nome real da UI no momento do clique
        current_name = self.preview_panel.cbo_models.currentText()
        if not current_name:
            self.log_panel.append("ERRO: Nenhum modelo selecionado.")
            return
            
        slug = slugify_model_name(current_name)
        template_path = Path("models") / slug / "template_v3.json"

        if not template_path.exists():
            self.log_panel.append(f"ERRO: Modelo '{self.active_model_name}' não encontrado.")
            return

        with open(template_path, "r", encoding="utf-8") as f:
            tpl_data = json.load(f)
            model_dir = template_path.parent
            if tpl_data.get("background_path") and not Path(tpl_data["background_path"]).is_absolute():
                tpl_data["background_path"] = str(model_dir / tpl_data["background_path"])
            for sig in tpl_data.get("signatures", []):
                if not Path(sig["path"]).is_absolute():
                    sig["path"] = str(model_dir / sig["path"])

        renderer = NativeRenderer(tpl_data)

        custom_path = self.txt_output_path.text().strip()
        if custom_path:
            base_dir = Path(custom_path)
            self.settings.setValue("last_output_dir", custom_path)
        else:
            base_dir = Path("output") / slug

        # [NOVO] Cria subpasta: Lote_AA.MM.DD_HH.MM.SS
        timestamp = datetime.now().strftime("%y.%m.%d_%H.%M.%S")
        folder_name = f"Lote_{timestamp}"
        
        output_dir = base_dir / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_panel.append(f"📂 Salvando em: {folder_name}")

        self.btn_generate_cards.setEnabled(False)
        self.btn_generate_cards.setText("Gerando... (Aguarde)")
        self.progress_bar.setValue(0)
        self.log_panel.append(f"--- Iniciando lote de {len(rows_plain)} cartões ---")

        if self.current_filename_suffix:
            full_pattern = f"{slug}_{self.current_filename_suffix}"
        else:
            full_pattern = slug

        # Recupera config de imposição (se existir)
        imposition_cfg = self.cached_model_data.get("imposition_settings", None)

        self.manager = RenderManager(
            renderer, 
            rows_plain, 
            rows_rich, 
            output_dir, 
            full_pattern,
            imposition_settings=imposition_cfg
        )
        
        self.manager.progress_updated.connect(self.progress_bar.setValue)
        self.manager.log_updated.connect(self.log_panel.append)
        self.manager.error_occurred.connect(lambda msg: self.log_panel.append(f"[ERRO] {msg}"))
        self.manager.finished_process.connect(self._on_generation_finished)
        self.manager.finished_process.connect(self._handle_printing_queue)
        
        self.manager.start()

    def _on_generation_finished(self):
        self.btn_generate_cards.setEnabled(True)
        self.btn_generate_cards.setText("Gerar cartões")
        self.log_panel.append("=== Processo Multi-Thread Finalizado ===")

    def _on_model_changed(self, name: str):
        self.preview_panel.set_preview_text(f"Prévia do modelo selecionado:\n{name}")
        self.log_panel.append(f"Modelo ativo: {name}")
        self.active_model_name = name
        self.current_filename_suffix = ""

        if not name: return

        slug = slugify_model_name(name)
        json_path = Path("models") / slug / "template_v3.json"

        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # [NOVO] Recupera o padrão de nome salvo
                    self.current_filename_suffix = data.get("output_suffix", "")
                    if self.current_filename_suffix:
                         # Feedback visual discreto no log opcional
                         pass 
                    
                    model_dir = json_path.parent
                    if data.get("background_path") and not Path(data["background_path"]).is_absolute():
                        data["background_path"] = str(model_dir / data["background_path"])
                    for sig in data.get("signatures", []):
                        if not Path(sig["path"]).is_absolute():
                            sig["path"] = str(model_dir / sig["path"])

                    placeholders = data.get("placeholders", [])
                    
                    self._update_table_columns(placeholders)
                    self.log_panel.append(f"Colunas carregadas: {placeholders}")
                    
                    self.cached_model_data = data
                    
                    try:
                        renderer = NativeRenderer(data)
                        preview_pix = renderer.render_to_pixmap(row_rich=None)
                        self.preview_panel.set_preview_pixmap(preview_pix)
                    except Exception as e:
                        self.log_panel.append(f"Erro ao gerar preview: {e}")
                        self.preview_panel.set_preview_text("Erro ao gerar preview do modelo")
            except Exception as e:
                self.log_panel.append(f"Erro ao ler colunas do modelo: {e}")
        else:
            self.log_panel.append("Aviso: template_v3.json não encontrado.")

    def _on_editor_saved(self, model_name, placeholders):
        self.log_panel.append(f"Modelo '{model_name}' salvo. Atualizando lista...")
        self._reload_models_from_disk(select_name=model_name)
    
    def _update_table_columns(self, placeholders):
        self.table_panel.table.clearContents()
        self.table_panel.table.setRowCount(0)
        self.table_panel.table.setColumnCount(0)
        
        if not placeholders: return
            
        self.table_panel.table.setColumnCount(len(placeholders))
        self.table_panel.table.setHorizontalHeaderLabels(placeholders)
        self.table_panel.table.setRowCount(1)

    def _open_model_dialog(self):
        # [FIX] Fonte da verdade é a UI
        current_model_name = self.preview_panel.cbo_models.currentText()
        
        if not current_model_name:
            QMessageBox.warning(self, "Atenção", "Selecione um modelo na lista antes de configurar.")
            return
            
        # Sincroniza a variável de cache apenas para garantir
        self.active_model_name = current_model_name

        self.editor_window = EditorWindow(self)
        self.editor_window.modelSaved.connect(self._on_editor_saved)

        slug = slugify_model_name(current_model_name)
        json_path = Path("models") / slug / "template_v3.json"

        if json_path.exists():
            self.editor_window.load_from_json(str(json_path))
        
        self.editor_window.show()

    def _reload_models_from_disk(self, select_name: str | None = None):
        self.preview_panel.cbo_models.blockSignals(True)
        self.preview_panel.cbo_models.clear()

        models_dir = Path("models")
        models_dir.mkdir(parents=True, exist_ok=True)

        found = []
        for folder in sorted(models_dir.iterdir()):
            if not folder.is_dir(): continue
            json_path = folder / "template_v3.json"
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text(encoding="utf-8"))
                    name = data.get("name", folder.name)
                    found.append(name)
                except Exception:
                    continue

        for name in found:
            self.preview_panel.cbo_models.addItem(name)

        self.preview_panel.cbo_models.blockSignals(False)

        self.preview_panel.cbo_models.blockSignals(False) # Destrava sinais

        # Lógica de Seleção Robusta
        target_index = 0 # Padrão: primeiro item
        
        if select_name:
            idx = self.preview_panel.cbo_models.findText(select_name)
            if idx >= 0:
                target_index = idx

        if self.preview_panel.cbo_models.count() > 0:
            self.preview_panel.cbo_models.setCurrentIndex(target_index)
            
            # [FIX CRÍTICO] Força a atualização manual.
            # Às vezes o 'setCurrentIndex' não dispara o sinal se o índice numérico
            # não mudou (ex: era 0, limpou, encheu, virou 0 de novo).
            # Chamamos explicitamente para garantir que o Preview e o 'active_model_name' atualizem.
            current_text = self.preview_panel.cbo_models.itemText(target_index)
            self._on_model_changed(current_text)
        else:
            # Lista vazia? Limpa o preview
            self._on_model_changed("")

    def _on_add_model(self):
        self.editor_window = EditorWindow(self)
        self.editor_window.modelSaved.connect(self._on_editor_saved)
        self.editor_window.show()

    def _on_remove_model(self):
        import shutil
        model_name = (self.preview_panel.cbo_models.currentText() or "").strip()
        if not model_name: return

        slug = slugify_model_name(model_name)
        model_dir = Path("models") / slug

        if not model_dir.exists(): return

        resp = QMessageBox.question(self, "Confirmar exclusão", f"Excluir '{model_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes: return

        try:
            shutil.rmtree(model_dir)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao excluir: {e}")
            return

        self.log_panel.append(f"Modelo excluído: {model_name}")
        self._reload_models_from_disk()

    def _get_row_data_rich(self, row_idx):
        table = self.table_panel.table
        cols = table.columnCount()
        headers = [table.horizontalHeaderItem(c).text() for c in range(cols)]
        
        row_data = {}
        for c in range(cols):
            key = headers[c]
            item = table.item(row_idx, c)
            val = ""
            if item:
                val = item.data(Qt.ItemDataRole.UserRole)
                if not val: val = item.text()
            row_data[key] = val
        return row_data

    def _on_table_selection(self):
        if not self.cached_model_data: return
        row = self.table_panel.table.currentRow()
        if row < 0: return

        try:
            row_rich = self._get_row_data_rich(row)
            renderer = NativeRenderer(self.cached_model_data)
            pix = renderer.render_to_pixmap(row_rich=row_rich)
            self.preview_panel.set_preview_pixmap(pix)
        except Exception as e:
            print(f"Erro no Live Preview: {e}")
    
    def _scrape_table_data(self):
        table = self.table_panel.table
        rows = table.rowCount()
        cols = table.columnCount()
        headers = [table.horizontalHeaderItem(c).text() for c in range(cols)]
        data_plain, data_rich = [], []

        for r in range(rows):
            row_p, row_r = {}, {}
            is_empty = True
            for c in range(cols):
                key = headers[c]
                item = table.item(r, c)
                val_plain = item.text().strip() if item else ""
                val_rich = item.data(Qt.ItemDataRole.UserRole) if item else ""
                if not val_rich: val_rich = val_plain
                
                if val_plain: is_empty = False
                row_p[key] = val_plain
                row_r[key] = val_rich

            if not is_empty:
                data_plain.append(row_p)
                data_rich.append(row_r)
        return data_plain, data_rich
    
    def _select_output_folder(self):
        start_dir = self.txt_output_path.text() or ""
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Saída", start_dir)
        if folder:
            self.txt_output_path.setText(folder)
            self.settings.setValue("last_output_dir", folder)

    def _handle_printing_queue(self):
        """
        Chamado quando o processo termina. 
        Verifica se o usuário pediu para imprimir e abre o diálogo.
        """
        # 1. Verifica se a opção de imprimir estava marcada no JSON/Config
        if not self.cached_model_data: return
        
        imp_settings = self.cached_model_data.get("imposition_settings", {})
        should_print = imp_settings.get("print_after_generation", False)
        
        if not should_print:
            return

        # 2. Verifica se existem arquivos para imprimir
        files_to_print = getattr(self.manager, "generated_files", [])
        if not files_to_print:
            self.log_panel.append("⚠️ Nenhum arquivo gerado para impressão.")
            return

        # 3. Configura a Impressora (Diálogo do Sistema)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        
        # [CORREÇÃO] Auto-detectar orientação baseada na primeira folha gerada
        if files_to_print:
            first_img_path = self.manager.output_dir / files_to_print[0]
            if first_img_path.exists():
                img_check = QImage(str(first_img_path))
                if not img_check.isNull():
                    if img_check.width() > img_check.height():
                        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
                    else:
                        printer.setPageOrientation(QPageLayout.Orientation.Portrait)

        # [CRÍTICO] Força o modo "Full Page" para permitir impressão 1:1 (Sem Escala)
        # Isso diz ao Qt para considerar as coordenadas do papel inteiro, inclusive as bordas não imprimíveis.
        printer.setFullPage(True)

        dialog = QPrintDialog(printer, self)
        
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            self.log_panel.append("🖨️ Impressão cancelada pelo usuário.")
            return

        # 4. Loop de Impressão (Stream do Disco para o Spooler)
        self.log_panel.append(f"🖨️ Enviando {len(files_to_print)} páginas para a impressora...")
        
        painter = QPainter()
        if not painter.begin(printer):
            self.log_panel.append("❌ Erro ao iniciar comunicação com a impressora.")
            return

        try:
            output_dir = self.manager.output_dir
            
            for i, filename in enumerate(files_to_print):
                # Se não for a primeira página, ejeta a folha anterior
                if i > 0:
                    printer.newPage()
                
                # Carrega do disco
                full_path = output_dir / filename
                if not full_path.exists():
                    self.log_panel.append(f"❌ Arquivo não encontrado: {filename}")
                    continue
                
                img = QImage(str(full_path))
                if img.isNull():
                    self.log_panel.append(f"❌ Falha ao ler imagem: {filename}")
                    continue

                # [CORREÇÃO ESCALA] Desenha usando o paperRect (Papel Físico) e não pageRect (Área Imprimível).
                # Isso garante que 1mm na imagem seja 1mm no papel, cortando as margens físicas se necessário,
                # mas sem distorcer ou encolher o conteúdo central.
                paper_rect = printer.paperRect(QPrinter.Unit.DevicePixel)
                painter.drawImage(paper_rect, img)
                
            self.log_panel.append("✅ Envio para impressão concluído!")
            
        except Exception as e:
            self.log_panel.append(f"❌ Erro durante impressão: {e}")
        finally:
            painter.end()