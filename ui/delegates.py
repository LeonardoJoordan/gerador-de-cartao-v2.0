# ui/delegates.py
import re
from PySide6.QtWidgets import (QStyledItemDelegate, QStyle, QApplication, 
                               QTextEdit)
from PySide6.QtGui import (QTextDocument, QPalette, QTextCursor, QFont)
from PySide6.QtCore import Qt

# [IMPORTANTE] Usamos a mesma lógica de limpeza do Clipboard para garantir consistência
from core.rich_clipboard import sanitize_inline_html

class RichTextEditor(QTextEdit):
    """
    Editor flutuante para Rich Text.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(True)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            if key == Qt.Key.Key_B:
                self._toggle_weight()
                return
            elif key == Qt.Key.Key_I:
                self._toggle_italic()
                return
            elif key == Qt.Key.Key_U:
                self._toggle_underline()
                return
        super().keyPressEvent(event)

    def _toggle_weight(self):
        fmt = self.currentCharFormat()
        new_weight = QFont.Weight.Normal if fmt.fontWeight() > QFont.Weight.Normal else QFont.Weight.Bold
        fmt.setFontWeight(new_weight)
        self.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self):
        fmt = self.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.mergeCurrentCharFormat(fmt)

    def _toggle_underline(self):
        fmt = self.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.mergeCurrentCharFormat(fmt)


class HTMLDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = option
        self.initStyleOption(options, index)
        style = options.widget.style() if options.widget else QApplication.style()
        
        rich_text = index.data(Qt.ItemDataRole.UserRole)
        
        if not rich_text:
            super().paint(painter, options, index)
            return

        painter.save()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, options, painter, options.widget)

        doc = QTextDocument()
        doc.setHtml(rich_text)
        doc.setTextWidth(options.rect.width())
        doc.setDocumentMargin(2)

        if options.state & QStyle.StateFlag.State_Selected:
            text_color = options.palette.color(QPalette.ColorGroup.Normal, QPalette.ColorRole.HighlightedText).name()
        else:
            text_color = options.palette.color(QPalette.ColorGroup.Normal, QPalette.ColorRole.Text).name()
            
        doc.setDefaultStyleSheet(f"body {{ color: {text_color}; }}")

        content_height = doc.size().height()
        y_offset = max(0, (options.rect.height() - content_height) / 2)
        
        painter.translate(options.rect.left(), options.rect.top() + y_offset)
        painter.setClipRect(0, 0, options.rect.width(), options.rect.height())
        doc.drawContents(painter)
        painter.restore()

    def createEditor(self, parent, option, index):
        editor = RichTextEditor(parent)
        return editor

    def setEditorData(self, editor, index):
        html = index.data(Qt.ItemDataRole.UserRole)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if html:
            editor.setHtml(html)
        else:
            editor.setText(text)
        editor.moveCursor(QTextCursor.MoveOperation.End)

    def setModelData(self, editor, model, index):
        # 1. Pega o HTML bruto do editor (que vem cheio de CSS no cabeçalho)
        raw_html = editor.toHtml()
        
        # 2. [CORREÇÃO CRÍTICA] Remove blocos INTEIROS de <head>, <style> e <script>.
        # O flag re.DOTALL faz o ponto (.) pegar também as quebras de linha.
        # Sem isso, ele remove a tag <style>, mas deixa o código CSS vazando no texto.
        html_content_only = re.sub(
            r'<(head|style|script)[^>]*>.*?</\1>', 
            '', 
            raw_html, 
            flags=re.IGNORECASE | re.DOTALL
        )
        
        # 3. Agora que tiramos o "lixo" do cabeçalho, passamos o corpo pelo
        # sanitizador para limpar fontes e tamanhos inline, mantendo negrito/itálico.
        clean_html = sanitize_inline_html(html_content_only)

        # 4. Texto puro para a camada de visualização simples
        plain = editor.toPlainText()
        
        # Salva
        model.setData(index, clean_html.strip(), Qt.ItemDataRole.UserRole)
        model.setData(index, plain, Qt.ItemDataRole.DisplayRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)