# core/typography_engine.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from typing import List
import re

from playwright.sync_api import sync_playwright


class TypographyEngine:
    """
    Engine headless (Chromium via Playwright) para renderizar overlay PNG transparente.
    - Inicia o browser 1 vez
    - Reusa para múltiplos renders
    """

    def __init__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._ctx = self._browser.new_context()

    def close(self):
        try:
            self._ctx.close()
        except Exception:
            pass
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass

    @staticmethod
    def _build_html_canvas(w: int, h: int, box: Dict[str, Any], html_text: str) -> str:
        """
        Monta um HTML mínimo com 1 caixa posicionada absolutamente.
        background transparente + screenshot omit_background=True.
        """
        # defaults seguros
        x = int(box.get("x", 0))
        y = int(box.get("y", 0))
        bw = int(box.get("w", w))
        bh = int(box.get("h", h))
        align = str(box.get("align", "left")).lower()
        font = str(box.get("font", "DejaVu Sans"))
        size = int(box.get("size", 32))
        color = str(box.get("color", "#FFFFFF"))

        # alinhar horizontal
        if align not in ("left", "center", "right", "justify"):
            align = "left"

        # Para o MVP: caixa "nome" centralizada vertical+horizontal com flex.
        # (Depois a gente trata justify e multiline com mais rigor.)
        css = f"""
        html, body {{
            margin: 0;
            padding: 0;
            width: {w}px;
            height: {h}px;
            background: transparent;
        }}
        .canvas {{
            position: relative;
            width: {w}px;
            height: {h}px;
            background: transparent;
            overflow: hidden;
        }}
        .box {{
            position: absolute;
            left: {x}px;
            top: {y}px;
            width: {bw}px;
            height: {bh}px;

            font-family: "{font}";
            font-size: {size}px;
            color: {color};

            line-height: 1.15;
            white-space: pre-wrap;
            word-break: break-word;

            f"box-sizing:border-box;"
            f"border: 2px dashed rgba(255,0,0,0.80);"

            text-align: {align};

            display: flex;
            align-items: center;       /* vertical center */
            justify-content: center;   /* horizontal center (MVP) */
        }}
        
        .box-content {{
            width: 100%;
        }}
        """

        # OBS: html_text já vem “sanitizado” no nosso fluxo (só <b><i><u><br>)
        return f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8" />
          <style>{css}</style>
        </head>
        <body>
          <div class="canvas">
            <div class="box"><div class="box-content">{html_text}</div></div>
          </div>
        </body>
        </html>
        """

    def render_overlay_one_box(self, *, width: int, height: int, box: Dict[str, Any], html_text: str, out_path: Path):
        """
        Renderiza um overlay PNG (transparente) com 1 box.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)

        html = self._build_html_canvas(width, height, box, html_text)

        page = self._ctx.new_page()
        try:
            page.set_viewport_size({"width": int(width), "height": int(height)})
            page.set_content(html, wait_until="load")

            page.screenshot(
                path=str(out_path),
                full_page=True,
                omit_background=True
            )
        finally:
            page.close()

    def render_overlay_multi_boxes(
        self,
        *,
        width: int,
        height: int,
        boxes: List[Dict[str, Any]],
        out_path: Path
    ):
        """
        Renderiza um overlay PNG transparente com várias boxes.
        Cada item de `boxes` deve conter:
        - id, x, y, w, h, align, font, size, color, line_height, indent_px, html_text
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def safe_class(s: str) -> str:
            s = (s or "").strip().lower()
            s = re.sub(r"[^a-z0-9_\-]+", "_", s)
            return s or "box"

        # CSS base
        css = f"""
        html, body {{
            margin: 0;
            padding: 0;
            width: {int(width)}px;
            height: {int(height)}px;
            background: transparent;
        }}
        .canvas {{
            position: relative;
            width: {int(width)}px;
            height: {int(height)}px;
            background: transparent;
            overflow: hidden;
        }}
        .box {{
            position: absolute;
            overflow: hidden;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        """

        # HTML das boxes
        boxes_html = []
        for b in boxes:
            box_id = str(b.get("id", "box"))
            cls = safe_class(box_id)

            x = int(b.get("x", 0))
            y = int(b.get("y", 0))
            w = int(b.get("w", width))
            h = int(b.get("h", height))

            align = str(b.get("align", "left")).lower()
            if align not in ("left", "center", "right", "justify"):
                align = "left"

            font = str(b.get("font", "DejaVu Sans"))
            size = int(b.get("size", 32))
            raw_color = b.get("color", "#FFFFFF")

            # Normaliza color para CSS válido
            if isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3:
                r = int(raw_color[0])
                g = int(raw_color[1])
                bb = int(raw_color[2])
                a = float(raw_color[3]) if len(raw_color) >= 4 else 1.0
                # se vier 0-255, converte para 0-1
                if a > 1.0:
                    a = a / 255.0
                color = f"rgba({r},{g},{bb},{a})"
            else:
                color = str(raw_color).strip()
                # se vier "255,255,255" tenta converter
                if "," in color and color.replace(",", "").replace(" ", "").isdigit():
                    parts = [p.strip() for p in color.split(",")]
                    if len(parts) >= 3:
                        r, g, bb = (int(parts[0]), int(parts[1]), int(parts[2]))
                        color = f"rgb({r},{g},{bb})"
                # fallback final
                if not color:
                    color = "#FFFFFF"

            line_height = float(b.get("line_height", 1.15))
            indent_px = int(b.get("indent_px", 0))

            html_text = str(b.get("html_text", ""))

            # comportamento de layout:
            # - caixas não-justify: centralizar verticalmente e alinhar horizontalmente via flex
            # - caixa justify: texto flui de cima, com indent
            if align == "justify":
                display_css = "display:block;"
                padding_css = "padding: 0;"
                justify_css = "text-align: justify;"
            else:
                # flex para facilitar centralização vertical
                display_css = "display:flex; align-items:center;"
                if align == "center":
                    justify_css = "justify-content:center; text-align:center;"
                elif align == "right":
                    justify_css = "justify-content:flex-end; text-align:right;"
                else:
                    justify_css = "justify-content:flex-start; text-align:left;"
                padding_css = "padding: 0;"

            indent_css = f"text-indent: {indent_px}px;" if indent_px > 0 and align == "justify" else ""

            style = (
                f"left:{x}px; top:{y}px; width:{w}px; height:{h}px;"
                f"font-family:\"{font}\"; font-size:{size}px; color:{color};"
                f"line-height:{line_height};"
                f"{display_css}{padding_css}{justify_css}{indent_css}"
                f"outline: 2px dashed rgba(255,0,0,0.80);"
                f"outline-offset: -1px;"
            )

            boxes_html.append(
                f"""
                <div class="box {cls}" style="{style}">
                <div style="width:100%;">{html_text}</div>
                </div>
                """
            )

        html = f"""
        <!doctype html>
        <html>
        <head>
        <meta charset="utf-8" />
        <style>{css}</style>
        </head>
        <body>
        <div class="canvas">
            {''.join(boxes_html)}
        </div>
        </body>
        </html>
        """

        page = self._ctx.new_page()
        try:
            page.set_viewport_size({"width": int(width), "height": int(height)})
            page.set_content(html, wait_until="load")
            page.screenshot(path=str(out_path), full_page=True, omit_background=True)
        finally:
            page.close()

