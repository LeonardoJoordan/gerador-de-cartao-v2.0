# core/svg_scanner.py

from __future__ import annotations

import base64
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

# ==============================================================================
# FASE 1: ESTRUTURAS DE DADOS (Blueprint: Passo 1)
# ==============================================================================

@dataclass
class ScannedObject:
    """Entidade base para qualquer elemento visual do SVG."""
    element_id: str
    x: float
    y: float
    w: float
    h: float
    z_index: int  # Ordem de empilhamento (0=fundo, N=topo)

@dataclass
class ScannedText(ScannedObject):
    """Clone digital do elemento <text>."""
    text: str
    font_family: str
    font_size: float
    font_weight: str  # 'bold' ou 'normal'
    font_style: str   # 'italic' ou 'normal'
    fill: str         # cor hex ou rgba
    align: str        # 'left', 'center', 'right' (mapeado de text-anchor)

@dataclass
class ScannedRect(ScannedObject):
    """Container de layout (apenas geometria)."""
    pass

@dataclass
class ScannedImage(ScannedObject):
    """Referência a uma imagem física extraída."""
    src_relative_path: str  # ex: 'assets/fundo.png'

@dataclass
class ScanResult:
    """O inventário completo do modelo."""
    texts: List[ScannedText] = field(default_factory=list)
    rects: List[ScannedRect] = field(default_factory=list)
    images: List[ScannedImage] = field(default_factory=list)

# ==============================================================================
# FASE 2: MECÂNICA FINA / HELPERS (Blueprint: Passo 2 e 3)
# ==============================================================================

def _parse_pixels(value: str | None, default: float = 0.0) -> float:
    """Converte strings como '10px', '12pt', '10' para pixels float."""
    if not value:
        return default
    
    val = value.lower().strip()
    if val.endswith("px"):
        return float(val.replace("px", ""))
    elif val.endswith("pt"):
        # 1pt = 1.333px (96dpi / 72dpi)
        return float(val.replace("pt", "")) * 1.3333
    elif val.endswith("mm"):
        # 1mm = 3.7795px
        return float(val.replace("mm", "")) * 3.7795
    elif val.replace(".", "", 1).isdigit():
        return float(val)
    
    return default

def _parse_styles(elem: ET.Element) -> Dict[str, str]:
    """
    Extrai estilos mesclando atributos diretos e CSS inline (style='...').
    Precedência: Atributo Direto > CSS Inline.
    """
    styles = {}
    
    # 1. Lê atributo style="..." e popula dicionário inicial
    style_str = elem.attrib.get("style", "")
    if style_str:
        # Regex simples para chave:valor;
        items = [s.strip().split(":") for s in style_str.split(";") if ":" in s]
        for k, v in items:
            styles[k.strip()] = v.strip()

    # 2. Lê atributos diretos (SVG presentation attributes) e sobrescreve
    # Lista de atributos de interesse
    direct_attrs = [
        "font-family", "font-size", "font-weight", "font-style", 
        "fill", "text-anchor", "x", "y", "width", "height"
    ]
    for attr in direct_attrs:
        if elem.get(attr):
            styles[attr] = elem.get(attr)

    return styles

def _extract_image_file(elem: ET.Element, assets_dir: Path, img_id: str) -> str:
    """
    Salva o conteúdo da imagem (Base64 ou Copy) em assets_dir.
    Retorna o caminho relativo (ex: 'assets/img_id.png').
    """
    href = elem.get("{http://www.w3.org/1999/xlink}href") or elem.get("href")
    if not href:
        return ""

    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Caso 1: Base64 embedado
    if href.startswith("data:image"):
        # Ex: data:image/png;base64,iVBORw0KGgo...
        try:
            header, encoded = href.split(",", 1)
            # detecta extensão simples
            ext = "png"
            if "image/jpeg" in header: ext = "jpg"
            if "image/svg" in header: ext = "svg"
            
            file_name = f"{img_id}.{ext}"
            file_path = assets_dir / file_name
            
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(encoded))
                
            return f"assets/{file_name}"
        except Exception as e:
            print(f"Erro ao extrair Base64 da imagem {img_id}: {e}")
            return ""

    # Caso 2: Link externo (Arquivo local)
    # Assumimos que o href é um caminho relativo ou absoluto na máquina do usuário
    # Se for URL web (http), ignoramos no MVP.
    if not href.startswith("http"):
        try:
            src_path = Path(href)
            # Se o caminho for relativo, tenta achar (mas aqui não temos o path do SVG original fácil)
            # Assumimos que o SVG scanner roda num contexto onde href faz sentido ou é absoluto.
            # (Melhoria futura: passar svg_path parent para resolver relativos)
            
            if src_path.exists():
                ext = src_path.suffix or ".png"
                file_name = f"{img_id}{ext}"
                dst_path = assets_dir / file_name
                shutil.copy(src_path, dst_path)
                return f"assets/{file_name}"
        except Exception as e:
            print(f"Erro ao copiar imagem {img_id}: {e}")
            
    return ""

def _map_anchor_to_align(anchor: str) -> str:
    if anchor == "middle": return "center"
    if anchor == "end": return "right"
    return "left"

# ==============================================================================
# FASE 3: MONTAGEM / SCANNER PRINCIPAL (Blueprint: Passo 4)
# ==============================================================================

def scan_svg(svg_path: Path, output_model_dir: Path | None = None) -> ScanResult:
    """
    Varre o SVG e extrai geometria, texto e imagens.
    Se output_model_dir for fornecido, extrai imagens para output_model_dir/assets/.
    """
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG não encontrado: {svg_path}")

    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Namespace SVG padrão é comum atrapalhar o find/findall
    # Vamos ignorar o namespace removendo-o das tags ou usando wildcard
    # Estratégia wildcard: iterar em tudo e checar tag.endswith('text')

    result = ScanResult()
    
    # Se não foi passado diretório de saída, não salva assets (ou salva temporário)
    # Mas pela arquitetura, o scanner deve ser chamado com o dir do modelo.
    assets_dir = (output_model_dir / "assets") if output_model_dir else None

    # Z-index counter
    z = 0

    # Itera sobre todos os elementos na ordem do documento (depth-first)
    for elem in root.iter():
        tag = elem.tag.lower()
        # remove namespace {http://...}tag -> tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]

        element_id = elem.get("id")
        if not element_id:
            continue

        # --- PROCESSA TEXT ---
        if tag == "text":
            styles = _parse_styles(elem)
            
            # Geometria
            x = _parse_pixels(styles.get("x", "0"))
            y = _parse_pixels(styles.get("y", "0"))
            # Text não tem w/h nativo confiável sem renderizar, assumimos 0 ou bbox se viesse do Inkscape
            # No MVP: 0. O usuário ajusta a quebra de linha na UI.
            
            # Texto Completo (incluindo tspan)
            text_parts = []
            if elem.text: text_parts.append(elem.text)
            for child in elem:
                if child.text: text_parts.append(child.text)
                if child.tail: text_parts.append(child.tail)
            full_text = "".join(text_parts).strip()

            # PATCH: Remove ID duplicado no início (correção do bug visual)
            if element_id and full_text.startswith(element_id):
                cleaned = full_text[len(element_id):].strip()
                if cleaned:
                    full_text = cleaned

            if not full_text:
                continue

            # Mapeamento de Estilos
            obj = ScannedText(
                element_id=element_id,
                x=x, y=y, w=0, h=0, z_index=z,
                text=full_text,
                font_family=styles.get("font-family", "DejaVu Sans"),
                font_size=_parse_pixels(styles.get("font-size", "32")),
                font_weight=styles.get("font-weight", "normal"),
                font_style=styles.get("font-style", "normal"),
                fill=styles.get("fill", "#000000"),
                align=_map_anchor_to_align(styles.get("text-anchor", "start"))
            )
            result.texts.append(obj)
            z += 1

        # --- PROCESSA RECT (Layout) ---
        elif tag == "rect":
            styles = _parse_styles(elem)
            
            x = _parse_pixels(styles.get("x", "0"))
            y = _parse_pixels(styles.get("y", "0"))
            w = _parse_pixels(styles.get("width", "0"))
            h = _parse_pixels(styles.get("height", "0"))

            if w > 0 and h > 0:
                obj = ScannedRect(
                    element_id=element_id,
                    x=x, y=y, w=w, h=h, z_index=z
                )
                result.rects.append(obj)
                z += 1

        # --- PROCESSA IMAGE ---
        elif tag == "image":
            if not assets_dir:
                # Se não tem onde salvar, ignoramos imagens
                continue
                
            styles = _parse_styles(elem)
            x = _parse_pixels(styles.get("x", "0"))
            y = _parse_pixels(styles.get("y", "0"))
            w = _parse_pixels(styles.get("width", "0"))
            h = _parse_pixels(styles.get("height", "0"))
            
            rel_path = _extract_image_file(elem, assets_dir, element_id)
            
            if rel_path:
                obj = ScannedImage(
                    element_id=element_id,
                    x=x, y=y, w=w, h=h, z_index=z,
                    src_relative_path=rel_path
                )
                result.images.append(obj)
                z += 1

    return result