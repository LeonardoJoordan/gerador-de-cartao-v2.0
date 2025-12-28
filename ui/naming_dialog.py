# ui/naming_dialog.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QHBoxLayout, QFrame, QGridLayout, 
                               QDialogButtonBox, QCheckBox, QGroupBox, QDoubleSpinBox)
from PySide6.QtCore import Qt

class NamingDialog(QDialog):
    def __init__(self, parent, model_slug: str, available_vars: list[str], 
                 current_pattern: str = "", model_size_px: tuple[int, int] = (1000, 1000),
                 current_imposition: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Saída e Impressão")
        self.resize(500, 450) # Aumentei a altura para caber a nova seção
        
        self.model_slug = model_slug
        self.result_pattern = current_pattern
        self.model_w, self.model_h = model_size_px
        self.ratio = self.model_w / self.model_h if self.model_h > 0 else 1.0
        
        # Dados de retorno (Imposição)
        self.imposition_settings = current_imposition or {
            "enabled": False, 
            "target_w_mm": 0, 
            "target_h_mm": 0
        }

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- SEÇÃO 1: NOME DO ARQUIVO ---
        layout.addWidget(QLabel("<b>1. Padrão de Nomenclatura:</b>"))

        # Container horizontal simples
        ly_preview = QHBoxLayout()
        ly_preview.setSpacing(5)
        
        lbl_prefix = QLabel(f"{self.model_slug}_")
        lbl_prefix.setStyleSheet("font-weight: bold; font-size: 14px;") 
        
        self.txt_pattern = QLineEdit()
        self.txt_pattern.setPlaceholderText("padrão (sequencial)")
        self.txt_pattern.setText(current_pattern)
        self.txt_pattern.setMinimumHeight(34) 
        
        lbl_ext = QLabel(".png")
        lbl_ext.setStyleSheet("font-size: 14px; opacity: 0.7;") 

        ly_preview.addWidget(lbl_prefix)
        ly_preview.addWidget(self.txt_pattern)
        ly_preview.addWidget(lbl_ext)
        
        layout.addLayout(ly_preview)

        # Botões de Variáveis
        layout.addWidget(QLabel("Variáveis disponíveis:"))
        grid_vars = QGridLayout()
        grid_vars.setSpacing(8)
        col, row = 0, 0
        
        if not available_vars:
            layout.addWidget(QLabel("<i>(Nenhuma coluna encontrada)</i>"))
        else:
            for var in available_vars:
                btn = QPushButton(f"{{{var}}}")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setMinimumHeight(30)
                btn.clicked.connect(lambda checked, v=var: self._insert_variable(v))
                grid_vars.addWidget(btn, row, col)
                col += 1
                if col > 3: 
                    col = 0
                    row += 1
            layout.addLayout(grid_vars)

        # Separador visual
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # --- SEÇÃO 2: IMPRESSÃO / IMPOSIÇÃO ---
        layout.addWidget(QLabel("<b>2. Impressão (Imposição A4):</b>"))
        
        self.chk_imposition = QCheckBox("Habilitar montagem em folha A4 (PDF/PNG)")
        self.chk_imposition.setChecked(self.imposition_settings.get("enabled", False))
        self.chk_imposition.toggled.connect(self._toggle_imposition_ui)
        layout.addWidget(self.chk_imposition)

        self.grp_imposition = QGroupBox("Configurar Dimensões do Cartão (mm)")
        self.grp_imposition.setEnabled(False)
        ly_imp = QGridLayout(self.grp_imposition)
        
        # Inputs Numéricos
        self.spin_w_mm = QDoubleSpinBox()
        self.spin_w_mm.setRange(10, 500)
        self.spin_w_mm.setSuffix(" mm")
        self.spin_w_mm.setDecimals(1)
        
        self.spin_h_mm = QDoubleSpinBox()
        self.spin_h_mm.setRange(10, 500)
        self.spin_h_mm.setSuffix(" mm")
        self.spin_h_mm.setDecimals(1)

        # Carrega valores salvos ou calcula padrão (ex: 100mm de largura base)
        saved_w = self.imposition_settings.get("target_w_mm", 0)
        if saved_w > 0:
            self.spin_w_mm.setValue(saved_w)
            self.spin_h_mm.setValue(saved_w / self.ratio)
        else:
            self.spin_w_mm.setValue(100.0) # Valor inicial dummy
            self.spin_h_mm.setValue(100.0 / self.ratio)

        # Conexão de Proporção (Aspect Ratio Lock)
        self.spin_w_mm.valueChanged.connect(self._on_width_changed)
        self.spin_h_mm.valueChanged.connect(self._on_height_changed)

        ly_imp.addWidget(QLabel("Largura:"), 0, 0)
        ly_imp.addWidget(self.spin_w_mm, 0, 1)
        ly_imp.addWidget(QLabel("Altura:"), 1, 0)
        ly_imp.addWidget(self.spin_h_mm, 1, 1)
        
        ly_imp.addWidget(QLabel("<small style='color: gray'>O sistema manterá a proporção do modelo original.</small>"), 2, 0, 1, 2)

        layout.addWidget(self.grp_imposition)
        self._toggle_imposition_ui(self.chk_imposition.isChecked())

        layout.addStretch()

        # Botões OK/Cancelar
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _toggle_imposition_ui(self, checked):
        self.grp_imposition.setEnabled(checked)

    def _on_width_changed(self, new_w):
        """Calcula altura baseado na largura mantendo aspect ratio."""
        self.spin_h_mm.blockSignals(True)
        self.spin_h_mm.setValue(new_w / self.ratio)
        self.spin_h_mm.blockSignals(False)

    def _on_height_changed(self, new_h):
        """Calcula largura baseado na altura mantendo aspect ratio."""
        self.spin_w_mm.blockSignals(True)
        self.spin_w_mm.setValue(new_h * self.ratio)
        self.spin_w_mm.blockSignals(False)

    def _insert_variable(self, var_name):
        """Insere o texto {var} onde o cursor estiver."""
        # Insere e foca no input para continuar digitando
        self.txt_pattern.insert(f"{{{var_name}}}")
        self.txt_pattern.setFocus()

    def _on_accept(self):
        self.result_pattern = self.txt_pattern.text().strip()
        self.accept()

    def get_pattern(self):
        return self.result_pattern
    
    def get_imposition_settings(self):
        """Retorna o dict configurado."""
        return {
            "enabled": self.chk_imposition.isChecked(),
            "target_w_mm": self.spin_w_mm.value(),
            "target_h_mm": self.spin_h_mm.value()
        }