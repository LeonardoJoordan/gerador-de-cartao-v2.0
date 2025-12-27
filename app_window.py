from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                                QSplitter, QPushButton, QApplication, QMessageBox,
                                  QAbstractItemView, QLineEdit, QLabel, QFileDialog)
from PySide6.QtCore import Qt

from ui.preview_panel import PreviewPanel
from ui.controls_panel import ControlsPanel
from ui.log_panel import LogPanel
from ui.table_panel import TablePanel
from core.renderer_v3 import NativeRenderer
from ui.editor.editor_window import EditorWindow
from core.naming import build_output_filename
import json
from core.template_v2 import slugify_model_name

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Cartão em Lote v3.0")
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
        self._reload_models_from_disk()

        self.controls_panel = ControlsPanel()
        self.log_panel = LogPanel()

        left_stack.addWidget(self.preview_panel, 5)
        left_stack.addWidget(self.controls_panel, 0)
        left_stack.addWidget(self.log_panel, 3)

        # --- Seletor de Pasta de Saída ---
        grp_out = QWidget()
        ly_out = QHBoxLayout(grp_out)
        ly_out.setContentsMargins(0, 0, 0, 0)

        ly_out.addWidget(QLabel("Saída:"))
        
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setPlaceholderText("Padrão: ./output/nome_do_modelo")
        # self.txt_output_path.setReadOnly(True) # Descomente se quiser impedir digitação manual
        ly_out.addWidget(self.txt_output_path)

        self.btn_sel_out = QPushButton("...")
        self.btn_sel_out.setFixedWidth(40)
        self.btn_sel_out.setToolTip("Selecionar pasta de destino")
        self.btn_sel_out.clicked.connect(self._select_output_folder)
        ly_out.addWidget(self.btn_sel_out)

        left_stack.addWidget(grp_out, 0)

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

        self.active_model_name = self.preview_panel.cbo_models.currentText()
        self._on_model_changed(self.active_model_name)

        # quando trocar o modelo no combo, atualiza estado
        self.preview_panel.cbo_models.currentTextChanged.connect(self._on_model_changed)

        # botões novos
        self.controls_panel.btn_add_model.clicked.connect(self._on_add_model)
        self.controls_panel.btn_remove_model.clicked.connect(self._on_remove_model)
        self.controls_panel.btn_config_model.clicked.connect(self._open_model_dialog)

    def _generate_cards_placeholder(self):
        # 1. Coleta dados frescos da tabela
        rows_plain, rows_rich = self._scrape_table_data()
        
        if not rows_plain:
            self.log_panel.append("AVISO: A tabela está vazia. Nada a gerar.")
            return

        # 2. Verifica modelo e caminhos
        from core.template_v2 import slugify_model_name
        from core.naming import build_output_filename
        from core.renderer_v3 import NativeRenderer
        import json
        from pathlib import Path

        slug = slugify_model_name(self.active_model_name)
        template_path = Path("models") / slug / "template_v3.json"

        if not template_path.exists():
            self.log_panel.append(f"ERRO: O modelo '{self.active_model_name}' não foi configurado no Editor V3.")
            return

        with open(template_path, "r", encoding="utf-8") as f:
            tpl_data = json.load(f)

        # [FIX] Resolve caminhos relativos para absolutos antes de renderizar
        model_dir = template_path.parent
        if tpl_data.get("background_path") and not Path(tpl_data["background_path"]).is_absolute():
            tpl_data["background_path"] = str(model_dir / tpl_data["background_path"])
        
        for sig in tpl_data.get("signatures", []):
            if not Path(sig["path"]).is_absolute():
                sig["path"] = str(model_dir / sig["path"])

        # 3. Prepara o motor e diretório de saída
        renderer = NativeRenderer(tpl_data)
        
        # Define diretório de saída (Personalizado ou Padrão)
        custom_path = self.txt_output_path.text().strip()
        if custom_path:
            output_dir = Path(custom_path)
        else:
            output_dir = Path("output") / slug
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        used_names = set()
        self.log_panel.append(f"Iniciando renderização de {len(rows_plain)} cartões...")

        # 4. Loop de geração
        for i, row in enumerate(rows_plain):
            # Define nome do arquivo (ex: cartao_Joao.png)
            filename = build_output_filename(self.current_output_pattern, row, used_names)
            out_path = output_dir / f"{filename}.png"
            
            # Renderiza nativamente usando os dados extraídos
            renderer.render_row(row, rows_rich[i], out_path)
            self.log_panel.append(f"[OK] Gerado: {out_path.name}")

        self.log_panel.append(f"=== Processo concluído! Arquivos em: {output_dir} ===")


    def _on_model_changed(self, name: str):
        self.preview_panel.set_preview_text(f"Prévia do modelo selecionado:\n{name}")
        self.log_panel.append(f"Modelo ativo: {name}")
        self.active_model_name = name

        # Carrega colunas dinamicamente do JSON V3
        if not name: return

        slug = slugify_model_name(name)
        json_path = Path("models") / slug / "template_v3.json"

        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # [FIX] Resolve assets relativos para o preview
                    model_dir = json_path.parent
                    if data.get("background_path") and not Path(data["background_path"]).is_absolute():
                        data["background_path"] = str(model_dir / data["background_path"])
                    for sig in data.get("signatures", []):
                        if not Path(sig["path"]).is_absolute():
                            sig["path"] = str(model_dir / sig["path"])

                    placeholders = data.get("placeholders", [])
                    
                    # Atualiza a tabela (headers)
                    self._update_table_columns(placeholders)
                    self.log_panel.append(f"Colunas carregadas: {placeholders}")
                    try:
                        renderer = NativeRenderer(data)
                        # Gera o pixmap em memória (com placeholders preenchidos ex: {nome})
                        preview_pix = renderer.render_to_pixmap(row_rich=None)
                        self.preview_panel.set_preview_pixmap(preview_pix)
                        self.log_panel.append("Preview gerado com sucesso (incluindo camadas de texto)")
                    except Exception as e:
                        import traceback
                        self.log_panel.append(f"Erro ao gerar preview: {e}")
                        self.log_panel.append(f"Traceback: {traceback.format_exc()}")
                        # Fallback: não mostra nada (mantém preview vazio ou com mensagem de erro)
                        self.preview_panel.set_preview_text("Erro ao gerar preview do modelo")
            except Exception as e:
                self.log_panel.append(f"Erro ao ler colunas do modelo: {e}")
        else:
            self.log_panel.append("Aviso: template_v3.json não encontrado para este modelo.")

    def _on_editor_saved(self, model_name, placeholders):
        """Chamado quando o Editor salva um modelo. Recarrega a lista e seleciona o salvo."""
        self.log_panel.append(f"Modelo '{model_name}' salvo. Atualizando lista...")
        # Recarrega do disco e força a seleção do novo modelo
        # A mudança de seleção disparará _on_model_changed, que atualizará a tabela/preview
        self._reload_models_from_disk(select_name=model_name)
    
    def _update_table_columns(self, placeholders):
        """Atualiza os cabeçalhos da tabela baseada nos placeholders do modelo."""
        # 1. Limpa tudo (zera colunas e linhas)
        self.table_panel.table.clearContents()
        self.table_panel.table.setRowCount(0)
        self.table_panel.table.setColumnCount(0)
        
        if not placeholders:
            return
            
        # 2. Cria as colunas novas
        self.table_panel.table.setColumnCount(len(placeholders))
        self.table_panel.table.setHorizontalHeaderLabels(placeholders)
        
        # 3. Garante pelo menos uma linha vazia para o usuário começar a digitar
        self.table_panel.table.setRowCount(1)
        
        self.log_panel.append(f"Tabela configurada: {len(placeholders)} colunas ({', '.join(placeholders)})")

    def _open_model_dialog(self):
        if not self.active_model_name:
            QMessageBox.warning(self, "Atenção", "Selecione um modelo na lista antes de configurar.")
            return

        self.editor_window = EditorWindow(self)
        # Conecta ao novo callback que lida com o reload
        self.editor_window.modelSaved.connect(self._on_editor_saved)

        from core.template_v2 import slugify_model_name
        slug = slugify_model_name(self.active_model_name)
        json_path = Path("models") / slug / "template_v3.json"

        if json_path.exists():
            self.log_panel.append(f"A carregar ficheiro: {json_path}")
            self.editor_window.load_from_json(str(json_path))
        else:
            self.log_panel.append("Nenhum ficheiro V3 encontrado. A iniciar modelo novo.")
        
        self.editor_window.show()

    def _reload_models_from_disk(self, select_name: str | None = None):
        """Recarrega o ComboBox com base em models/*/template_v3.json"""
        from pathlib import Path
        import json

        self.preview_panel.cbo_models.blockSignals(True)
        self.preview_panel.cbo_models.clear()

        models_dir = Path("models")
        models_dir.mkdir(parents=True, exist_ok=True)

        found = []
        for folder in sorted(models_dir.iterdir()):
            if not folder.is_dir():
                continue
            json_path = folder / "template_v3.json"
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text(encoding="utf-8"))
                    name = data.get("name", folder.name)
                    found.append(name)
                except Exception:
                    # se um json estiver corrompido, só ignora
                    continue

        for name in found:
            self.preview_panel.cbo_models.addItem(name)

        self.preview_panel.cbo_models.blockSignals(False)

        # selecionar algo após reload
        if select_name:
            idx = self.preview_panel.cbo_models.findText(select_name)
            if idx >= 0:
                self.preview_panel.cbo_models.setCurrentIndex(idx)
                return

        # se não passou select_name, seleciona o primeiro automaticamente
        if self.preview_panel.cbo_models.count() > 0:
            self.preview_panel.cbo_models.setCurrentIndex(0)


    def _on_add_model(self):
        """Adicionar modelo = abrir editor em branco."""
        self.editor_window = EditorWindow(self)
        # Conecta ao novo callback que lida com o reload
        self.editor_window.modelSaved.connect(self._on_editor_saved)
        self.editor_window.show()


    def _on_remove_model(self):
        """Remove do disco o modelo ativo/selecionado no combo."""
        from pathlib import Path
        import shutil
        from PySide6.QtWidgets import QMessageBox
        from core.template_v2 import slugify_model_name

        model_name = (self.preview_panel.cbo_models.currentText() or "").strip()
        if not model_name:
            QMessageBox.warning(self, "Atenção", "Nenhum modelo selecionado para remover.")
            return

        slug = slugify_model_name(model_name)
        model_dir = Path("models") / slug

        if not model_dir.exists():
            QMessageBox.warning(self, "Erro", f"Pasta do modelo não encontrada:\n{model_dir}")
            return

        resp = QMessageBox.question(
            self,
            "Confirmar exclusão",
            f"Tem certeza que deseja excluir o modelo:\n\n{model_name}\n\nIsso apagará a pasta:\n{model_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        try:
            shutil.rmtree(model_dir)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao excluir o modelo:\n{e}")
            return

        self.log_panel.append(f"Modelo excluído: {model_name}")
        self._reload_models_from_disk()

    def _scrape_table_data(self):
        """Varre a QTableWidget e monta as listas de dados para o renderizador."""
        table = self.table_panel.table
        rows = table.rowCount()
        cols = table.columnCount()
        
        headers = [table.horizontalHeaderItem(c).text() for c in range(cols)]
        
        data_plain = []
        data_rich = []

        # Pula a linha 0 se ela estiver vazia/inutilizável, mas no nosso caso
        # assumimos que todas as linhas visíveis são dados.
        for r in range(rows):
            row_p = {}
            row_r = {}
            is_empty = True
            
            for c in range(cols):
                key = headers[c]
                item = table.item(r, c)
                
                # Se item for None, assume vazio
                val_plain = item.text().strip() if item else ""
                
                # Tenta pegar o HTML rico (salvo no UserRole pelo paste), senão usa o texto puro
                val_rich = item.data(Qt.ItemDataRole.UserRole) if item else ""
                if not val_rich:
                    val_rich = val_plain
                
                if val_plain:
                    is_empty = False
                    
                row_p[key] = val_plain
                # O renderizador espera chaves sem {}, mas o template usa {}.
                # Vamos garantir compatibilidade salvando com a chave limpa
                # (O renderer_v3 já trata isso, mas é bom garantir).
                row_r[key] = val_rich

            # Só adiciona se a linha tiver algum conteúdo
            if not is_empty:
                data_plain.append(row_p)
                data_rich.append(row_r)
                
        return data_plain, data_rich
    
    def _select_output_folder(self):
        """Abre diálogo para selecionar pasta de saída."""
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Saída")
        if folder:
            self.txt_output_path.setText(folder)