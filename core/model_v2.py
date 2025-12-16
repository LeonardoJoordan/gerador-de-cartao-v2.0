# core/model_v2.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any
import re

# Importamos as estruturas do scanner para tipagem
from core.svg_scanner import ScanResult, ScannedImage

PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


@dataclass
class ModelBox:
    """
    Representa uma BOX consolidada (Geometria + Estilo).
    """
    id: str
    template_text: str

    # Geometria
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0

    # Tipografia / Estilo
    align: str = "left"
    font: str = "DejaVu Sans"
    size: float = 32.0
    color: str = "#000000"
    bold: bool = False
    italic: bool = False
    
    # Configurações lógicas
    editable: bool = False
    indent_px: int = 0
    line_height: float = 1.15

    def placeholders(self) -> Set[str]:
        """Placeholders presentes no template_text, sem chaves."""
        return set(PLACEHOLDER_RE.findall(self.template_text))

    def placeholder_columns(self) -> Set[str]:
        """Placeholders com chaves: {'{nome}', '{data}'}"""
        return {f"{{{p}}}" for p in self.placeholders()}


@dataclass
class ModelV2:
    """
    Modelo interno consolidado.
    - boxes_by_id: lookup rápido por id
    - images: lista de imagens estáticas (fundo, assinatura)
    - all_placeholders: união de placeholders de todas as boxes
    """
    boxes_by_id: Dict[str, ModelBox] = field(default_factory=dict)
    images: List[ScannedImage] = field(default_factory=list)
    all_placeholders: Set[str] = field(default_factory=set)

    def boxes_in_order(self) -> List[ModelBox]:
        """
        Retorna boxes ordenadas. 
        Idealmente deveríamos usar o z_index do scanner, mas por enquanto ordenamos por ID ou ordem de inserção.
        """
        # Python 3.7+ mantém ordem de inserção no dict, então se inserimos na ordem do scan, está ok.
        return list(self.boxes_by_id.values())

    def editable_columns(self) -> List[str]:
        return [b.id for b in self.boxes_in_order() if b.editable]

    def placeholder_columns(self) -> List[str]:
        return sorted({f"{{{p}}}" for p in self.all_placeholders})

    def resolve_box_text(self, box: ModelBox, row_plain: dict, row_rich: dict) -> str:
        """
        Resolve o texto final da box mesclando template + dados da linha.
        """
        # 1) override total por ID (se editável e presente na coluna)
        if box.editable:
            override_plain = (row_plain.get(box.id) or "").strip()
            if override_plain:
                override_rich = (row_rich.get(box.id) or "").strip()
                return override_rich if override_rich else override_plain

        # 2) substituição de placeholders dentro do template_text
        def repl(m):
            key = m.group(1)            # sem chaves: nome
            col = f"{{{key}}}"          # com chaves: {nome}
            
            # Prioridade: Rich Text > Plain Text
            val = (row_rich.get(col) or "").strip()
            if not val:
                val = (row_rich.get(key) or "").strip()
            if not val:
                val = (row_plain.get(col) or "").strip()
            if not val:
                val = (row_plain.get(key) or "").strip()
            
            return val

        return PLACEHOLDER_RE.sub(repl, box.template_text)


def build_model_from_scan(scan: ScanResult) -> ModelV2:
    """
    Funde os dados do Scanner (Rects + Texts + Images) em um ModelV2 coeso.
    """
    model = ModelV2()

    # 1. Fase Layout: Cria boxes a partir dos Retângulos (Definem a "Arena")
    for r in scan.rects:
        # Retângulo define geometria, mas não tem texto nem estilo por padrão
        box = ModelBox(
            id=r.element_id,
            template_text="", # Rect não tem texto
            x=r.x, 
            y=r.y, 
            w=r.w, 
            h=r.h
        )
        model.boxes_by_id[r.element_id] = box

    # 2. Fase Conteúdo: Processa Textos (Definem o "Jogador")
    for t in scan.texts:
        if t.element_id in model.boxes_by_id:
            # MERGE: O ID já existe (veio de um rect).
            # Aproveitamos a geometria do Rect e injetamos o estilo/texto do Text.
            box = model.boxes_by_id[t.element_id]
            box.template_text = t.text
            box.font = t.font_family
            box.size = t.font_size
            box.color = t.fill
            box.bold = (t.font_weight == "bold")
            box.italic = (t.font_style == "italic")
            box.align = t.align
            # Nota: Não sobrescrevemos x,y,w,h do rect, pois o rect manda no layout.
        else:
            # CREATE: O ID é novo (texto solto sem rect correspondente).
            # Usamos a geometria do próprio texto.
            box = ModelBox(
                id=t.element_id,
                template_text=t.text,
                x=t.x,
                y=t.y,
                w=t.w, # Será 0, engine deve lidar
                h=t.h,
                font=t.font_family,
                size=t.font_size,
                color=t.fill,
                bold=(t.font_weight == "bold"),
                italic=(t.font_style == "italic"),
                align=t.align
            )
            model.boxes_by_id[t.element_id] = box

        # Coleta placeholders
        model.all_placeholders.update(model.boxes_by_id[t.element_id].placeholders())

    # 3. Fase Assets: Copia imagens
    # Por enquanto, apenas armazenamos a referência.
    model.images = scan.images[:]

    return model