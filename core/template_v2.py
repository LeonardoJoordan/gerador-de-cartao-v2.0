import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import unicodedata


class TemplateError(Exception):
    pass


def slugify_model_name(name: str) -> str:
    """
    Converte "Cartão Aniversário" -> "cartao_aniversario"
    - remove acentos (normalização unicode)
    - troca espaços/hífens por "_"
    - mantém só [a-z0-9_]
    """
    s = (name or "").strip().lower()

    # Remove acentos: "cartão" -> "cartao"
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    # troca espaços e hífens por underscore
    s = re.sub(r"[\s\-]+", "_", s)

    # remove tudo que não for [a-z0-9_]
    s = re.sub(r"[^a-z0-9_]+", "", s)

    return s or "modelo"


@dataclass(frozen=True)
class TemplateV2:
    name: str
    dpi: int
    size_px: Dict[str, int]
    background: str
    boxes: List[Dict[str, Any]]

    @property
    def width(self) -> int:
        return int(self.size_px["w"])

    @property
    def height(self) -> int:
        return int(self.size_px["h"])


def load_template_for_model(model_name: str, project_root: Path | None = None) -> tuple[TemplateV2, Path]:
    """
    Procura em: <root>/models/<slug>/template_v2.json
    Retorna: (template, caminho_da_pasta_do_modelo)
    """
    root = project_root or Path.cwd()
    slug = slugify_model_name(model_name)
    model_dir = root / "models" / slug
    template_path = model_dir / "template_v2.json"

    if not template_path.exists():
        raise TemplateError(f"Template não encontrado: {template_path}")

    try:
        data = json.loads(template_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise TemplateError(f"Falha ao ler JSON do template: {e}")

    # validações mínimas
    for key in ("name", "dpi", "size_px", "boxes"):
        if key not in data:
            raise TemplateError(f"Campo obrigatório ausente no template: '{key}'")

    if "w" not in data["size_px"] or "h" not in data["size_px"]:
        raise TemplateError("size_px precisa ter 'w' e 'h'")

    if not isinstance(data["boxes"], list) or len(data["boxes"]) == 0:
        raise TemplateError("boxes precisa ser uma lista não vazia")

    background = data.get("background", "background.png")

    tpl = TemplateV2(
        name=str(data["name"]),
        dpi=int(data["dpi"]),
        size_px={"w": int(data["size_px"]["w"]), "h": int(data["size_px"]["h"])},
        background=str(background),
        boxes=list(data["boxes"]),
    )
    return tpl, model_dir
