from pathlib import Path
from PIL import Image


def compose_png_over_background(
    *,
    background_path: Path,
    overlay_path: Path,
    out_path: Path,
) -> None:
    """
    Junta background (RGB/RGBA) + overlay (RGBA) usando alpha-composite e salva o PNG final.
    """
    background_path = Path(background_path)
    overlay_path = Path(overlay_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not background_path.exists():
        raise FileNotFoundError(f"Background não encontrado: {background_path}")

    if not overlay_path.exists():
        raise FileNotFoundError(f"Overlay não encontrado: {overlay_path}")

    bg = Image.open(background_path).convert("RGBA")
    ov = Image.open(overlay_path).convert("RGBA")

    if bg.size != ov.size:
        raise ValueError(
            f"Tamanhos diferentes: bg={bg.size} vs overlay={ov.size}. "
            f"Eles precisam ter o MESMO tamanho em pixels."
        )

    final_img = Image.alpha_composite(bg, ov)
    final_img.save(out_path, format="PNG")
