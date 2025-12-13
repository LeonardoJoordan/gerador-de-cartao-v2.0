# core/svg_scanner.py

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set
import re
import xml.etree.ElementTree as ET


PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


class ScannedBox:
    def __init__(self, *, element_id: str, template_text: str):
        self.element_id = element_id
        self.template_text = template_text

    def __repr__(self):
        return f"ScannedBox(id='{self.element_id}', text='{self.template_text}')"


class ScanResult:
    def __init__(self):
        self.boxes: List[ScannedBox] = []
        self.placeholders: Set[str] = set()


def scan_svg(svg_path: Path) -> ScanResult:
    """
    Lê um SVG e detecta:
    - Elementos de texto com ID (boxes)
    - Placeholders no formato {nome}

    Retorna um ScanResult com:
    - boxes (id + template_text)
    - placeholders (set)
    """
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG não encontrado: {svg_path}")

    tree = ET.parse(svg_path)
    root = tree.getroot()

    ns = {
        "svg": "http://www.w3.org/2000/svg"
    }

    result = ScanResult()

    # Percorre todos os elementos <text>
    for elem in root.findall(".//svg:text", ns):
        element_id = elem.attrib.get("id")
        if not element_id:
            continue  # ignoramos textos sem id

        # Extrai texto completo (incluindo tspans)
        text_parts: List[str] = []

        if elem.text:
            text_parts.append(elem.text)

        for child in elem:
            if child.text:
                text_parts.append(child.text)
            if child.tail:
                text_parts.append(child.tail)

        template_text = "".join(text_parts).strip()

        if not template_text:
            continue

        box = ScannedBox(
            element_id=element_id,
            template_text=template_text
        )
        result.boxes.append(box)

        # Detecta placeholders no texto
        for match in PLACEHOLDER_RE.findall(template_text):
            result.placeholders.add(match)

    return result
