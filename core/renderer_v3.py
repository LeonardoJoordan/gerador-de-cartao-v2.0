from PySide6.QtGui import QPainter, QImage, QPixmap, QTextDocument
from PySide6.QtCore import Qt, QRectF
import re
from pathlib import Path

class NativeRenderer:
    def __init__(self, template_data: dict):
        self.tpl = template_data

    def render_row(self, row_plain: dict, row_rich: dict, out_path: Path):
        """Renderiza uma única linha (cartão) em disco."""
        w = self.tpl["canvas_size"]["w"]
        h = self.tpl["canvas_size"]["h"]
        
        # Cria a imagem de alta qualidade
        image = QImage(w, h, QImage.Format_ARGB32)
        image.fill(Qt.GlobalColor.white) # Base sólida

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 1. CAMADA FUNDO
        if self.tpl.get("background_path"):
            bg = QPixmap(self.tpl["background_path"])
            if not bg.isNull():
                painter.drawPixmap(0, 0, bg)

        # 2. CAMADA TEXTO (DesignerBoxes)
        for box in self.tpl.get("boxes", []):
            # Resolve placeholders usando os dados da linha
            html_resolved = self.resolve_html(box["html"], row_rich)
            self._draw_html_box(painter, box, html_resolved)

        # 3. CAMADA ASSINATURA (Por cima de tudo)
        for sig in self.tpl.get("signatures", []):
            if Path(sig["path"]).exists():
                pix = QPixmap(sig["path"])
                scaled = pix.scaled(sig["width"], sig["height"], 
                                   Qt.AspectRatioMode.KeepAspectRatio, 
                                   Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(sig["x"], sig["y"], scaled)

        painter.end()
        image.save(str(out_path), "PNG")

    def resolve_html(self, html: str, row_rich: dict) -> str:
        """Substitui {placeholder} pelo conteúdo rico da tabela."""
        def repl(match):
            key = match.group(1)
            # Busca na linha da tabela; fallback para vazio se não encontrar
            return str(row_rich.get(key, ""))
            
        return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, html)

    def _draw_html_box(self, painter, box_data, html_text):
        """Renderiza o HTML da caixa preservando formatação."""
        painter.save()
        
        doc = QTextDocument()
        doc.setHtml(html_text)
        doc.setTextWidth(box_data["w"])
        
        # O QTextDocument por padrão não tem alinhamento vertical centralizado.
        # Se for "center", precisamos calcular o offset Y manualmente.
        y_offset = 0
        if box_data.get("vertical_align") == "center":
            content_h = doc.size().height()
            y_offset = max(0, (box_data["h"] - content_h) / 2)
        elif box_data.get("vertical_align") == "bottom":
            content_h = doc.size().height()
            y_offset = max(0, box_data["h"] - content_h)

        painter.translate(box_data["x"], box_data["y"] + y_offset)
        
        # Define a área de clip para não vazar da caixa
        clip_rect = QRectF(0, -y_offset, box_data["w"], box_data["h"])
        doc.drawContents(painter, clip_rect)
        
        painter.restore()