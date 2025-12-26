from PySide6.QtGui import QPainter, QImage, QPixmap, QTextDocument
from PySide6.QtCore import Qt, QRectF
import re
from pathlib import Path

class NativeRenderer:
    def __init__(self, template_data: dict):
        self.tpl = template_data

    def render_to_pixmap(self, row_rich: dict = None) -> QPixmap:
        """Gera um QPixmap do cartão (para preview em memória)."""
        w = self.tpl["canvas_size"]["w"]
        h = self.tpl["canvas_size"]["h"]
        
        image = QImage(w, h, QImage.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        try:
            # Se não passar dados, cria dados 'dummy' usando os próprios placeholders
            # Ex: Se tiver {nome}, o texto será "{nome}"
            if row_rich is None:
                placeholders = self.tpl.get("placeholders", [])
                row_rich = {p: f"{{{p}}}" for p in placeholders}

            self._paint_card(painter, row_rich)
        finally:
            painter.end()
        
        return QPixmap.fromImage(image)

    def render_row(self, row_plain: dict, row_rich: dict, out_path: Path):
        """Renderiza e salva em disco."""
        w = self.tpl["canvas_size"]["w"]
        h = self.tpl["canvas_size"]["h"]
        
        image = QImage(w, h, QImage.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        try:
            self._paint_card(painter, row_rich)
        finally:
            painter.end()

        image.save(str(out_path), "PNG")

    def _paint_card(self, painter: QPainter, row_rich: dict):
        """Desenha as camadas do cartão."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 1. CAMADA FUNDO
        if self.tpl.get("background_path"):
            bg = QPixmap(self.tpl["background_path"])
            if not bg.isNull():
                painter.drawPixmap(0, 0, bg)

        # 2. CAMADA TEXTO
        for box in self.tpl.get("boxes", []):
            # --- Lógica de Renderização Condicional ---
            # 1. Encontra quais variáveis ({nome}, {data}) esta caixa está pedindo
            needed_vars = re.findall(r"\{([a-zA-Z0-9_]+)\}", box["html"])
            
            should_skip = False
            for var in needed_vars:
                # 2. Busca o valor na linha de dados
                val = row_rich.get(var, "")
                
                # 3. Limpa tags HTML simples para verificar se é só espaço vazio
                # (Isso evita que um '<b> </b>' seja considerado conteúdo)
                clean_val = re.sub(r"<[^>]+>", "", str(val)).strip()
                
                # 4. Se a variável for vazia, condena a caixa inteira à invisibilidade
                if not clean_val:
                    should_skip = True
                    break
            
            if should_skip:
                continue # Pula para a próxima caixa, ignorando esta
            try:
                html_resolved = self.resolve_html(box["html"], row_rich)
                self._draw_html_box(painter, box, html_resolved)
            except Exception as e:
                print(f"[WARN] Erro ao desenhar caixa de texto: {e}")
                continue

        # 3. CAMADA ASSINATURA
        for sig in self.tpl.get("signatures", []):
            if Path(sig["path"]).exists():
                pix = QPixmap(sig["path"])
                scaled = pix.scaled(sig["width"], sig["height"], 
                                   Qt.AspectRatioMode.KeepAspectRatio, 
                                   Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(sig["x"], sig["y"], scaled)

    def resolve_html(self, html: str, row_rich: dict) -> str:
        def repl(match):
            key = match.group(1)
            # Se o dado não existir, retorna vazio (ou o próprio placeholder se quiser debugar)
            return str(row_rich.get(key, ""))
        return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, html)

    def _draw_html_box(self, painter, box_data, html_text):
        painter.save()
        
        doc = QTextDocument()
        doc.setDocumentMargin(0) # Remove margens padrão
        doc.setDefaultStyleSheet("body { color: black; }")
        doc.setHtml(html_text)

        # [FIX] Força o alinhamento horizontal baseado no JSON
        align_str = box_data.get("align", "left")
        opts = doc.defaultTextOption()
        
        if align_str == "center":
            opts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        elif align_str == "right":
            opts.setAlignment(Qt.AlignmentFlag.AlignRight)
        elif align_str == "justify":
            opts.setAlignment(Qt.AlignmentFlag.AlignJustify)
        else:
            opts.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
        doc.setDefaultTextOption(opts)
        
        w = box_data.get("w", 300)
        h = box_data.get("h", 100)
        doc.setTextWidth(w)
        
        # Ajuste Vertical
        content_h = doc.size().height()
        y_offset = 0
        if box_data.get("vertical_align") == "center":
            y_offset = max(0, (h - content_h) / 2)
        elif box_data.get("vertical_align") == "bottom":
            y_offset = max(0, h - content_h)

        # Posicionamento e Clip
        painter.translate(box_data.get("x", 0), box_data.get("y", 0))
        painter.setClipRect(0, 0, w, h)
        painter.translate(0, y_offset)
        
        doc.drawContents(painter)
        
        painter.restore()
