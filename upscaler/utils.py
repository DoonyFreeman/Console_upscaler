from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def collect_images(path: Path) -> list[Path]:
    p = Path(path)
    if p.is_file():
        if is_image(p):
            return [p]
        return []
    if p.is_dir():
        return sorted(f for f in p.iterdir() if f.is_file() and is_image(f))
    return []


def make_output_path(input_path: Path, output: str | None, scale: int, fmt: str | None) -> Path:
    inp = Path(input_path)
    if output:
        return Path(output)

    ext = f".{fmt}" if fmt else inp.suffix
    stem = inp.stem
    return inp.parent / f"{stem}_{scale}x{ext}"


def get_image_info(path: Path) -> tuple[int, int, str]:
    from PIL import Image

    with Image.open(path) as img:
        w, h = img.size
        mode = img.mode
    return w, h, mode
