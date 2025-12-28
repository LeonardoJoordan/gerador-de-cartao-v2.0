# ui/naming_dialog.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QHBoxLayout, QFrame, QGridLayout, 
                               QDialogButtonBox)
from PySide6.QtCore import Qt

class NamingDialog(QDialog):
    def __init__(self, parent, model_slug: str, available_vars: list[str], current_pattern: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Configurar Nome do Arquivo")
        self.resize(500, 250) # Reduzi um pouco a altura para ficar mais compacto
        
        self.model_slug = model_slug
        self.result_pattern = current_pattern

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Explicação Visual
        lbl_info = QLabel("Defina o padrão de nomenclatura:")
        # Removemos estilos forçados, deixamos o tema decidir a cor
        layout.addWidget(lbl_info)

        # 2. Área de Construção do Nome
        # Visual: [PREFIXO FIXO] + [CAMPO EDITÁVEL] + [.png]
        
        # Container horizontal simples, sem fundo branco forçado
        ly_preview = QHBoxLayout()
        ly_preview.setSpacing(5)
        
        lbl_prefix = QLabel(f"{self.model_slug}_")
        lbl_prefix.setStyleSheet("font-weight: bold; font-size: 14px;") # Mantém negrito, tira cor fixa
        
        self.txt_pattern = QLineEdit()
        self.txt_pattern.setPlaceholderText("padrão (sequencial)")
        self.txt_pattern.setText(current_pattern)
        # Altura mínima para ficar igual ao da tela principal
        self.txt_pattern.setMinimumHeight(34) 
        
        lbl_ext = QLabel(".png")
        lbl_ext.setStyleSheet("font-size: 14px; opacity: 0.7;") 

        ly_preview.addWidget(lbl_prefix)
        ly_preview.addWidget(self.txt_pattern)
        ly_preview.addWidget(lbl_ext)
        
        layout.addLayout(ly_preview)

        # Separador visual discreto
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 3. Botões de Variáveis (Atalhos)
        layout.addWidget(QLabel("Variáveis disponíveis (clique para inserir):"))
        
        grid_vars = QGridLayout()
        grid_vars.setSpacing(8)
        col = 0
        row = 0
        
        if not available_vars:
            layout.addWidget(QLabel("<i>(Nenhuma coluna encontrada na tabela)</i>"))
        else:
            for var in available_vars:
                # O botão insere "{var}" no texto
                btn = QPushButton(f"{{{var}}}")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"Insere a coluna {var} no nome")
                btn.setMinimumHeight(30)
                
                # [CORREÇÃO DO BUG ANTERIOR MANTIDA]
                # lambda checked, v=var: ... ignora o False do checked
                btn.clicked.connect(lambda checked, v=var: self._insert_variable(v))
                
                grid_vars.addWidget(btn, row, col)
                col += 1
                if col > 3: # 4 colunas por linha
                    col = 0
                    row += 1
            
            layout.addLayout(grid_vars)
        
        layout.addStretch()

        # 4. Botões OK/Cancelar
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

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