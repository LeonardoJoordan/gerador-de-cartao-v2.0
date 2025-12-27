from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QApplication
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt

from core.rich_clipboard import parse_clipboard_html_table, parse_tsv


class RichTableWidget(QTableWidget):
    """
    QTableWidget que intercepta Ctrl+V.
    - Se clipboard tiver HTML (Sheets): preserva <b>/<i>/<u>/<br> em Qt.UserRole
    - Se não tiver: cola TSV simples
    """
    RICH_ROLE = Qt.ItemDataRole.UserRole  # onde guardamos o HTML "rico"

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_from_clipboard()
            return
        super().keyPressEvent(event)

    def _paste_from_clipboard(self):
        md = QApplication.clipboard().mimeData()
        if not md:
            return

        # 1. Parse dos dados (TSV é a fonte da verdade estrutural)
        text_raw = md.text() if md.hasText() else ""
        grid_struct = parse_tsv(text_raw)
        
        # Parse do HTML para estilo (negrito/itálico)
        grid_style = []
        if md.hasHtml():
            try:
                grid_style = parse_clipboard_html_table(md.html())
            except Exception:
                grid_style = []

        if not grid_struct:
            return

        # 2. Identifica onde o usuário clicou (Célula e Coluna Visual)
        curr = self.currentIndex()
        if not curr.isValid():
            start_row = 0
            start_col_logical = 0
        else:
            start_row = curr.row()
            start_col_logical = curr.column()

        # Obtém o cabeçalho para traduzir Visual <-> Lógico
        header = self.horizontalHeader()
        start_visual_col = header.visualIndex(start_col_logical)

        # 3. Expande linhas se necessário
        required_rows = start_row + len(grid_struct)
        if required_rows > self.rowCount():
            self.setRowCount(required_rows)

        # 4. Loop de Colagem Inteligente
        for r, row_data in enumerate(grid_struct):
            # Linha real na tabela
            dest_row = start_row + r
            
            # Linha de estilo correspondente (se houver)
            style_row = grid_style[r] if r < len(grid_style) else []

            for c, cell_plain in enumerate(row_data):
                # A mágica: Calculamos a coluna VISUAL de destino
                target_visual_col = start_visual_col + c
                
                # Se exceder o número de colunas visíveis, paramos de colar nesta linha
                if target_visual_col >= self.columnCount():
                    break
                
                # Traduzimos de volta para o índice LÓGICO (onde o dado fica guardado)
                dest_col_logical = header.logicalIndex(target_visual_col)

                item = self.item(dest_row, dest_col_logical)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(dest_row, dest_col_logical, item)

                # Aplica Texto
                txt_val = cell_plain.plain
                item.setText(txt_val)

                # Aplica Estilo (se disponível na posição correta)
                if c < len(style_row):
                    rich_val = style_row[c].rich_html
                    item.setData(self.RICH_ROLE, rich_val)
                else:
                    item.setData(self.RICH_ROLE, txt_val)


class TablePanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Tabela de dados")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        self.table = RichTableWidget(0, 0)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionsMovable(True)
        layout.addWidget(self.table, 1)
