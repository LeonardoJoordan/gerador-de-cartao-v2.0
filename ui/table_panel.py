# ui/table_panel.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget, 
                               QTableWidgetItem, QApplication, QMenu)
from PySide6.QtGui import QKeySequence, QFontMetrics, QAction
from PySide6.QtCore import Qt, QTimer

from core.rich_clipboard import parse_clipboard_html_table, parse_tsv
# [NOVO] Importamos o delegate que acabamos de corrigir
from .delegates import HTMLDelegate


class RichTableWidget(QTableWidget):
    """
    QTableWidget turbinado:
    1. Intercepta Ctrl+V (cola HTML do Excel/Sheets).
    2. Usa HTMLDelegate para renderizar negrito/itálico.
    3. Permite formatação rápida via Menu ou Atalhos (Ctrl+B/I/U).
    """
    RICH_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # [NOVO] Conecta o motor visual HTML
        self.setItemDelegate(HTMLDelegate(self))

    def contextMenuEvent(self, event):
        """Menu de contexto (botão direito) com opções de formatação."""
        menu = QMenu(self)
        
        act_bold = QAction("Negrito (Ctrl+B)", self)
        act_bold.triggered.connect(lambda: self._toggle_format("b"))
        
        act_italic = QAction("Itálico (Ctrl+I)", self)
        act_italic.triggered.connect(lambda: self._toggle_format("i"))
        
        act_underline = QAction("Sublinhado (Ctrl+U)", self)
        act_underline.triggered.connect(lambda: self._toggle_format("u"))

        act_clear = QAction("Limpar Formatação", self)
        act_clear.triggered.connect(self._clear_formatting)

        menu.addActions([act_bold, act_italic, act_underline])
        menu.addSeparator()
        menu.addAction(act_clear)
        
        menu.exec(event.globalPos())

    def keyPressEvent(self, event):
        # 1. Atalhos de Formatação (Ctrl+B/I/U) na célula selecionada (sem abrir editor)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            if key == Qt.Key.Key_B:
                self._toggle_format("b")
                return
            elif key == Qt.Key.Key_I:
                self._toggle_format("i")
                return
            elif key == Qt.Key.Key_U:
                self._toggle_format("u")
                return
        
        # 2. Colar (Ctrl+V)
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_from_clipboard()
            return

        # 3. Deletar
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._handle_delete()
            return

        super().keyPressEvent(event)

    def _handle_delete(self):
        """Lógica de delete (linhas inteiras ou células)."""
        sel_rows = self.selectionModel().selectedRows()
        if sel_rows:
            rows_to_del = sorted([idx.row() for idx in sel_rows], reverse=True)
            for r in rows_to_del:
                self.removeRow(r)
            if self.rowCount() == 0:
                self.insertRow(0)
        else:
            for item in self.selectedItems():
                item.setText("")
                item.setData(self.RICH_ROLE, None)

    def _toggle_format(self, tag: str):
        """
        Aplica formatação na CÉLULA INTEIRA.
        Útil para formatar rápido sem ter que abrir o editor de texto.
        """
        items = self.selectedItems()
        if not items:
            return

        start_tag = f"<{tag}>"
        end_tag = f"</{tag}>"

        for item in items:
            current_html = item.data(self.RICH_ROLE)
            # Se não tem HTML, usa o texto puro como base
            if not current_html:
                current_html = item.text()

            check = current_html.strip()

            # Lógica Toggle simples: Se já está envelopado, remove. Senão, adiciona.
            # Nota: Isso é binário (tudo ou nada). Para parcial, use o duplo clique (Delegate).
            if check.startswith(start_tag) and check.endswith(end_tag):
                new_html = check[len(start_tag):-len(end_tag)]
            else:
                new_html = f"{start_tag}{check}{end_tag}"

            item.setData(self.RICH_ROLE, new_html)
        
        # Força o Qt a redesenhar as células agora que mudamos os dados
        self.viewport().update()

    def _clear_formatting(self):
        """Remove todo HTML, deixando apenas texto puro."""
        for item in self.selectedItems():
            text = item.text()
            item.setData(self.RICH_ROLE, None)
            item.setText(text) # Garante sincronia

    # --- Lógica de Paste / AutoFit (Mantida original) ---

    def _text_width_px(self, text: str) -> int:
        fm = QFontMetrics(self.font())
        lines = (text or "").splitlines() or [""]
        return max(fm.horizontalAdvance(line) for line in lines)

    def _autofit_columns_after_paste(self, cols_logical: set[int], row_start: int, row_end: int, padding_px: int = 20):
        header = self.horizontalHeader()
        for col in cols_logical:
            header_item = self.horizontalHeaderItem(col)
            best = self._text_width_px(header_item.text() if header_item else "")
            for r in range(row_start, row_end + 1):
                it = self.item(r, col)
                if it is None: continue
                w = self._text_width_px(it.text())
                if w > best: best = w
            desired = best + padding_px
            if desired > self.columnWidth(col):
                self.setColumnWidth(col, desired)

    def _paste_from_clipboard(self):
        md = QApplication.clipboard().mimeData()
        if not md: return

        text_raw = md.text() if md.hasText() else ""
        grid_struct = parse_tsv(text_raw)
        
        grid_style = []
        if md.hasHtml():
            try:
                grid_style = parse_clipboard_html_table(md.html())
            except Exception:
                grid_style = []

        if not grid_struct: return

        curr = self.currentIndex()
        if not curr.isValid():
            start_row = 0
            start_col_logical = 0
        else:
            start_row = curr.row()
            start_col_logical = curr.column()

        header = self.horizontalHeader()
        start_visual_col = header.visualIndex(start_col_logical)
        required_rows = start_row + len(grid_struct)
        if required_rows > self.rowCount():
            self.setRowCount(required_rows)

        affected_cols_logical = set()
        row_end = start_row + len(grid_struct) - 1

        for r, row_data in enumerate(grid_struct):
            dest_row = start_row + r
            style_row = grid_style[r] if r < len(grid_style) else []

            for c, cell_plain in enumerate(row_data):
                target_visual_col = start_visual_col + c
                if target_visual_col >= self.columnCount():
                    break
                dest_col_logical = header.logicalIndex(target_visual_col)
                item = self.item(dest_row, dest_col_logical)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(dest_row, dest_col_logical, item)

                txt_val = cell_plain.plain
                item.setText(txt_val)

                # Aplica estilo se existir
                if c < len(style_row):
                    rich_val = style_row[c].rich_html
                    item.setData(self.RICH_ROLE, rich_val)
                else:
                    item.setData(self.RICH_ROLE, txt_val)

                affected_cols_logical.add(dest_col_logical)

        if affected_cols_logical:
            QTimer.singleShot(0, lambda: self._autofit_columns_after_paste(
                affected_cols_logical, start_row, row_end, padding_px=20
            ))


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