# core/model_v2.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import re


PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


@dataclass
class ModelBox:
    """
    Representa uma BOX (um elemento de texto do SVG).
    - id: id do elemento no SVG (fonte de verdade)
    - template_text: texto base (pode conter {placeholders})
    - editable: se True, permite existir uma coluna com o id da box (override total)
    - align: left/center/right/justify
    - indent_px: recuo 1ª linha (usado normalmente em justify)
    - line_height: altura de linha (CSS)
    """
    id: str
    template_text: str

    # Configurações do modelo (defaults por enquanto)
    editable: bool = False
    align: str = "left"
    indent_px: int = 0
    line_height: float = 1.15

    def placeholders(self) -> Set[str]:
        """Placeholders presentes no template_text, sem chaves."""
        return set(PLACEHOLDER_RE.findall(self.template_text))

    def placeholder_columns(self) -> Set[str]:
        """Placeholders presentes no template_text, com chaves: {'{nome}', '{data}'}"""
        return {f"{{{p}}}" for p in self.placeholders()}


@dataclass
class ModelV2:
    """
    Modelo interno consolidado.
    - boxes_by_id: lookup rápido por id
    - all_placeholders: união de placeholders de todas as boxes
    """
    boxes_by_id: Dict[str, ModelBox] = field(default_factory=dict)
    all_placeholders: Set[str] = field(default_factory=set)

    def boxes_in_order(self) -> List[ModelBox]:
        """Ordem estável (por id). Depois podemos mudar para ordem do SVG."""
        return [self.boxes_by_id[k] for k in sorted(self.boxes_by_id.keys())]

    def editable_columns(self) -> List[str]:
        """
        Colunas editáveis por ID (override total da box).
        Ex.: 'mensagem', 'data' (se você marcar editable=True)
        """
        return [b.id for b in self.boxes_in_order() if b.editable]

    def placeholder_columns(self) -> List[str]:
        """
        Colunas de placeholders no formato '{nome}', '{data}'.
        """
        return sorted({f"{{{p}}}" for p in self.all_placeholders})

    def resolve_box_text(self, box: ModelBox, row_plain: dict, row_rich: dict) -> str:
        """
        Regra de precedência (cravada):
        1) Se box.editable=True e a coluna do ID existir e tiver conteúdo -> override total
        2) Senão usa template_text e substitui placeholders {x} por row_rich['{x}'] (ou vazio)
        """
        # 1) override total por ID
        if box.editable:
            override_plain = (row_plain.get(box.id) or "").strip()
            if override_plain:
                # Se tiver rich nesse ID, usa; senão usa plain
                override_rich = (row_rich.get(box.id) or "").strip()
                return override_rich if override_rich else override_plain

        # 2) substituição de placeholders dentro do template_text
        def repl(m):
            key = m.group(1)            # sem chaves: nome
            col = f"{{{key}}}"          # com chaves: {nome}
            # 1) prioriza colunas com chaves (futuro)
            val = (row_rich.get(col) or "").strip()
            if val:
                return val

            # 2) aceita colunas sem chaves (estado atual do projeto)
            val = (row_rich.get(key) or "").strip()
            if val:
                return val

            # 3) fallback no plain (se o rich estiver vazio)
            val = (row_plain.get(col) or "").strip()
            if val:
                return val

            val = (row_plain.get(key) or "").strip()
            if val:
                return val

            return ""

        return PLACEHOLDER_RE.sub(repl, box.template_text)


def build_model_from_scan(scan_result) -> ModelV2:
    """
    Converte o ScanResult (core/svg_scanner.py) para ModelV2 interno.
    Defaults:
    - editable: False (por padrão)
    - align: left (por padrão)
    - indent_px: 0
    - line_height: 1.15
    """
    model = ModelV2()

    for sb in scan_result.boxes:
        box = ModelBox(
            id=sb.element_id,
            template_text=sb.template_text,
        )

        model.boxes_by_id[box.id] = box
        model.all_placeholders.update(box.placeholders())

    return model
