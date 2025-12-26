from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QPushButton, QApplication
from PySide6.QtCore import Qt

from ui.preview_panel import PreviewPanel
from ui.controls_panel import ControlsPanel
from ui.log_panel import LogPanel
from ui.table_panel import TablePanel

from ui.editor.editor_window import EditorWindow
from load_model.dialog_model_manager import ModelManagerDialog

from core.naming import build_output_filename


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
        self.log_panel.append("Iniciando geração de cartões (Fluxo V3 - QPainter)...")
        # Por enquanto, apenas valida se há dados na tabela
        rows = self.table_panel.table.rowCount()
        if rows == 0:
            self.log_panel.append("Erro: Tabela vazia.")
            return
        self.log_panel.append(f"Pronto para processar {rows} registros via Editor Visual.")


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
