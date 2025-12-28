from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QApplication
from PySide6.QtGui import QKeySequence, QFontMetrics
from PySide6.QtCore import Qt, QTimer

from core.rich_clipboard import parse_clipboard_html_table, parse_tsv
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
from .delegates import HTMLDelegate


class RichTableWidget(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ativa o renderizador HTML personalizado
        self.setItemDelegate(HTMLDelegate(self))
    """
    QTableWidget que intercepta Ctrl+V.
    - Se clipboard tiver HTML (Sheets): preserva <b>/<i>/<u>/<br> em Qt.UserRole
    - Se não tiver: cola TSV simples
    """
    RICH_ROLE = Qt.ItemDataRole.UserRole  # onde guardamos o HTML "rico"

    def keyPressEvent(self, event):
        # --- ATALHOS DE FORMATAÇÃO ---
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
        # 1. Colar (Ctrl+V)
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_from_clipboard()
            return

        # 2. Deletar (Delete ou Backspace)
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # Verifica se há linhas inteiras selecionadas
            # (Geralmente selecionadas clicando no cabeçalho vertical)
            sel_rows = self.selectionModel().selectedRows()
            
            if sel_rows:
                # Se tem linhas inteiras selecionadas, remove as linhas
                # Removemos de trás para frente para não bagunçar os índices
                rows_to_del = sorted([idx.row() for idx in sel_rows], reverse=True)
                for r in rows_to_del:
                    self.removeRow(r)
                
                # [SEGURANÇA] Se apagou todas as linhas, cria uma nova em branco
                # para que o usuário tenha onde clicar/colar
                if self.rowCount() == 0:
                    self.insertRow(0)
            else:
                # Se não tem linhas inteiras, apenas limpa o conteúdo das células selecionadas
                for item in self.selectedItems():
                    item.setText("")
                    item.setData(self.RICH_ROLE, None) # Limpa também o HTML oculto
            
            return

        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Cria menu de contexto com opções de formatação."""
        menu = QMenu(self)
        
        # Ações
        act_bold = QAction("Negrito (Ctrl+B)", self)
        act_bold.triggered.connect(lambda: self._toggle_format("b"))
        
        act_italic = QAction("Itálico (Ctrl+I)", self)
        act_italic.triggered.connect(lambda: self._toggle_format("i"))
        
        act_underline = QAction("Sublinhado (Ctrl+U)", self)
        act_underline.triggered.connect(lambda: self._toggle_format("u"))

        # Remove formatação (limpa tags mantendo texto)
        act_clear = QAction("Limpar Formatação", self)
        act_clear.triggered.connect(self._clear_formatting)

        menu.addActions([act_bold, act_italic, act_underline])
        menu.addSeparator()
        menu.addAction(act_clear)
        
        menu.exec(event.globalPos())

    def _toggle_format(self, tag: str):
        """Aplica ou remove uma tag HTML (b, i, u) nas células selecionadas."""
        items = self.selectedItems()
        if not items:
            return

        start_tag = f"<{tag}>"
        end_tag = f"</{tag}>"

        for item in items:
            # Pega o HTML atual (UserRole) ou o texto puro se não houver HTML
            current_html = item.data(self.RICH_ROLE)
            if not current_html:
                current_html = item.text()

            # Normaliza para verificação
            check = current_html.strip()

            # Lógica Toggle "Celular":
            # Se a célula INTEIRA já estiver envelopada na tag, remove.
            # Caso contrário (parcialmente ou nada), envelopa tudo.
            if check.startswith(start_tag) and check.endswith(end_tag):
                # Remove as tags das pontas
                new_html = check[len(start_tag):-len(end_tag)]
            else:
                # Adiciona as tags
                new_html = f"{start_tag}{check}{end_tag}"

            item.setData(self.RICH_ROLE, new_html)
        
        # Força repintura
        self.viewport().update()

    def _clear_formatting(self):
        """Reseta a célula para texto puro."""
        for item in self.selectedItems():
            text = item.text() # Texto puro original
            item.setData(self.RICH_ROLE, None) # Remove HTML
            item.setText(text) # Garante sincronia

    def _text_width_px(self, text: str) -> int:
        """Mede largura (px) do texto considerando a fonte atual do widget."""
        fm = QFontMetrics(self.font())
        # o texto pode vir com quebras de linha (Sheets/TSV). Usa a maior linha.
        lines = (text or "").splitlines() or [""]
        return max(fm.horizontalAdvance(line) for line in lines)

    def _autofit_columns_after_paste(self, cols_logical: set[int], row_start: int, row_end: int, padding_px: int = 20):
        """
        Ajusta largura só das colunas afetadas, baseado no maior conteúdo
        colado (e também no texto do header), com padding extra.
        """
        header = self.horizontalHeader()

        for col in cols_logical:
            # Começa pelo texto do header (se existir)
            header_item = self.horizontalHeaderItem(col)
            best = self._text_width_px(header_item.text() if header_item else "")

            # Mede apenas o intervalo de linhas coladas (bem mais leve)
            for r in range(row_start, row_end + 1):
                it = self.item(r, col)
                if it is None:
                    continue
                w = self._text_width_px(it.text())
                if w > best:
                    best = w

            desired = best + padding_px

            # Pequena folga extra se a coluna tiver ícone/indicador etc (opcional)
            # desired += 6

            # Só aumenta (não encolhe) para evitar “piscadas”
            if desired > self.columnWidth(col):
                self.setColumnWidth(col, desired)


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

        # >>> NOVO: rastrear o que foi afetado
        affected_cols_logical = set()
        row_end = start_row + len(grid_struct) - 1

        # 4. Loop de Colagem Inteligente
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

                if c < len(style_row):
                    rich_val = style_row[c].rich_html
                    item.setData(self.RICH_ROLE, rich_val)
                else:
                    item.setData(self.RICH_ROLE, txt_val)

                # >>> NOVO
                affected_cols_logical.add(dest_col_logical)

        # >>> NOVO: auto-fit depois da colagem (padding 20px = 10px cada lado)
        if affected_cols_logical:
            QTimer.singleShot(
                0,
                lambda: self._autofit_columns_after_paste(
                    affected_cols_logical, start_row, row_end, padding_px=20
                )
            )



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
