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

        if md and md.hasHtml():
            grid = parse_clipboard_html_table(md.html())
        else:
            grid = parse_tsv(md.text() if md else "")

        if not grid:
            return

        start = self.currentIndex()
        start_row = start.row() if start.isValid() else 0
        start_col = start.column() if start.isValid() else 0

        for r, row in enumerate(grid):
            for c, cell in enumerate(row):
                rr = start_row + r
                cc = start_col + c
                if rr >= self.rowCount() or cc >= self.columnCount():
                    continue

                item = self.item(rr, cc)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(rr, cc, item)

                # Visível: texto simples
                item.setText(cell.plain)
                # Interno: HTML "rico"
                item.setData(self.RICH_ROLE, cell.rich_html)


class TablePanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Tabela de dados")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        self.table = RichTableWidget(8, 4)
        self.table.setHorizontalHeaderLabels(["nome", "mensagem", "data", "comandante"])
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        # exemplo
        self.table.setItem(0, 0, QTableWidgetItem("João Carlos SILVA Pereira"))
        self.table.setItem(0, 1, QTableWidgetItem("Mensagem de exemplo...\nCom quebra de linha."))
        self.table.setItem(0, 2, QTableWidgetItem("12 DE DEZEMBRO DE 2025"))
        self.table.setItem(0, 3, QTableWidgetItem("Cel Fulano de Tal"))
