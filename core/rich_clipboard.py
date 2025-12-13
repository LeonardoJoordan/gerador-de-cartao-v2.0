# core/rich_clipboard.py
from __future__ import annotations

import re
from html.parser import HTMLParser
from dataclasses import dataclass
from typing import List, Tuple


ALLOWED_TAGS = {"b", "i", "u", "br"}


def _clean_spaces(s: str) -> str:
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def _clean_spaces_keep_edges(s: str) -> str:
    """
    Limpa espaços internos (colapsa múltiplos), mas NÃO dá strip().
    Isso evita grudar palavras quando o HTML vem dividido em spans.
    """
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s

def sanitize_inline_html(html: str) -> str:
    """
    Sanitiza um trecho de HTML "inline" vindo do clipboard.
    Objetivo: manter apenas <b>, <i>, <u>, <br> (e converter estilos comuns do Sheets).
    """
    # normaliza tags semanticamente equivalentes
    html = re.sub(r"</?\s*strong\s*>", lambda m: "<b>" if m.group(0)[1] != "/" else "</b>", html, flags=re.I)
    html = re.sub(r"</?\s*em\s*>", lambda m: "<i>" if m.group(0)[1] != "/" else "</i>", html, flags=re.I)

    class _InlineSanitizer(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.out: List[str] = []
            self.stack: List[str] = []

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()

            # Quebra de linha
            if tag == "br":
                self.out.append("<br>")
                return

            # Sheets costuma usar <span style="..."> para underline/bold/italic
            if tag == "span":
                style = ""
                for k, v in attrs:
                    if (k or "").lower() == "style":
                        style = (v or "").lower()
                        break

                # Detecta estilos relevantes
                open_tags = []
                if "text-decoration: underline" in style or "text-decoration:underline" in style:
                    open_tags.append("u")
                if "font-style: italic" in style or "font-style:italic" in style:
                    open_tags.append("i")
                # Sheets pode usar font-weight:700 ou bold
                if "font-weight: bold" in style or "font-weight:bold" in style or "font-weight:700" in style:
                    open_tags.append("b")

                # Abre na ordem b/i/u (não é obrigatório, mas deixa consistente)
                for t in ["b", "i", "u"]:
                    if t in open_tags:
                        self.out.append(f"<{t}>")
                        self.stack.append(t)
                # ignora o <span> em si
                return

            # Tags diretas permitidas
            if tag in ("b", "i", "u"):
                self.out.append(f"<{tag}>")
                self.stack.append(tag)
                return

            # Qualquer outra tag: ignorar
            return

        def handle_endtag(self, tag):
            tag = tag.lower()

            # Fecha tags diretas
            if tag in ("b", "i", "u"):
                if self.stack and self.stack[-1] == tag:
                    self.out.append(f"</{tag}>")
                    self.stack.pop()
                else:
                    # tenta fechar se estiver em algum lugar da pilha
                    if tag in self.stack:
                        while self.stack:
                            t = self.stack.pop()
                            self.out.append(f"</{t}>")
                            if t == tag:
                                break
                return

            # span: fecha todos que abrimos por estilo
            if tag == "span":
                while self.stack:
                    t = self.stack.pop()
                    self.out.append(f"</{t}>")
                return

        def handle_data(self, data):
            if not data:
                return
            self.out.append(_clean_spaces_keep_edges(data))

        def get_html(self) -> str:
            # Fecha o que sobrou aberto
            while self.stack:
                t = self.stack.pop()
                self.out.append(f"</{t}>")

            # Remove sequências vazias e ajusta espaços ao redor de tags
            s = "".join(self.out)
            s = re.sub(r"\s*<br>\s*", "<br>", s)
            s = s.strip()

            # Evita HTML vazio
            return s

    p = _InlineSanitizer()
    p.feed(html or "")
    return p.get_html()


@dataclass
class CellValue:
    plain: str
    rich_html: str


class _HtmlTableParser(HTMLParser):
    """
    Parser bem específico para HTML do clipboard (tabela).
    Extrai conteúdo HTML bruto de cada <td>/<th>.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_td = False
        self.in_tr = False
        self.current_cell_chunks: List[str] = []
        self.current_row: List[str] = []
        self.grid: List[List[str]] = []

        self._tag_stack: List[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_tr:
            self.in_td = True
            self.current_cell_chunks = []
            self._tag_stack = []
        elif self.in_td:
            # Preserva marcação relevante: b/i/u/br e span (para estilos do Sheets)
            if tag in ("b", "i", "u", "br", "span", "strong", "em"):
                if tag == "br":
                    self.current_cell_chunks.append("<br>")
                else:
                    # reconstruir attrs só do style em span
                    if tag == "span":
                        style = ""
                        for k, v in attrs:
                            if (k or "").lower() == "style":
                                style = v or ""
                                break
                        if style:
                            self.current_cell_chunks.append(f'<span style="{style}">')
                        else:
                            self.current_cell_chunks.append("<span>")
                    else:
                        self.current_cell_chunks.append(f"<{tag}>")
                        self._tag_stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "tr":
            if self.in_tr:
                if self.current_row:
                    self.grid.append(self.current_row)
            self.in_tr = False
        elif tag in ("td", "th"):
            if self.in_td:
                self.current_row.append("".join(self.current_cell_chunks))
            self.in_td = False
        elif self.in_td:
            if tag in ("b", "i", "u", "strong", "em"):
                self.current_cell_chunks.append(f"</{tag}>")
            elif tag == "span":
                self.current_cell_chunks.append("</span>")

    def handle_data(self, data):
        if self.in_td and data:
            self.current_cell_chunks.append(data)


def parse_clipboard_html_table(html: str) -> List[List[CellValue]]:
    """
    Recebe HTML do clipboard e retorna grid de CellValue {plain, rich_html}.
    """
    parser = _HtmlTableParser()
    parser.feed(html or "")

    out: List[List[CellValue]] = []
    for row in parser.grid:
        out_row: List[CellValue] = []
        for cell_html in row:
            rich = sanitize_inline_html(cell_html)
            # plain: remove tags permitidas para exibição
            plain = rich.replace("<br>", "\n")
            plain = re.sub(r"<[^>]+>", "", plain)
            plain = _clean_spaces(plain)
            out_row.append(CellValue(plain=plain, rich_html=rich))
        out.append(out_row)
    return out


def parse_tsv(text: str) -> List[List[CellValue]]:
    """
    TSV simples: cada célula vira plain e rich_html iguais (sem tags).
    """
    rows = (text or "").splitlines()
    grid: List[List[CellValue]] = []
    for r in rows:
        cols = r.split("\t")
        grid.append([CellValue(plain=_clean_spaces(c), rich_html=_clean_spaces(c)) for c in cols])
    return grid
