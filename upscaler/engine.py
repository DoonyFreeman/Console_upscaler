import os
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

try:
    from torchvision.transforms.functional_tensor import rgb_to_grayscale  # noqa: F401
except ModuleNotFoundError:
    import torchvision.transforms.functional
    import importlib
    sys.modules["torchvision.transforms.functional_tensor"] = torchvision.transforms.functional

from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

MODEL_DIR = Path.home() / ".upscaler" / "models"

MODELS = {
    "x4plus": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "filename": "RealESRGAN_x4plus.pth",
        "scale": 4,
        "num_block": 23,
        "num_feat": 64,
        "num_grow_ch": 32,
    },
    "x2plus": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "filename": "RealESRGAN_x2plus.pth",
        "scale": 2,
        "num_block": 23,
        "num_feat": 64,
        "num_grow_ch": 32,
    },
}


def _get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _download_model(model_name: str, console=None) -> Path:
    info = MODELS[model_name]
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / info["filename"]

    if model_path.exists():
        return model_path

    if console:
        console.print(f"[yellow]Downloading model {info['filename']}...[/yellow]")

    from urllib.request import urlopen
    import shutil

    response = urlopen(info["url"])
    total_size = int(response.headers.get("Content-Length", 0))

    if console and total_size > 0:
        from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

        with Progress(BarColumn(), DownloadColumn(), TransferSpeedColumn(), console=console) as progress:
            task = progress.add_task("download", total=total_size)
            with open(str(model_path), "wb") as f:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))
    else:
        with open(str(model_path), "wb") as f:
            shutil.copyfileobj(response, f)

    if console:
        console.print("[green]Model downloaded.[/green]")

    return model_path


def _build_model(model_name: str) -> RRDBNet:
    info = MODELS[model_name]
    return RRDBNet(
        num_in_ch=3,
        num_out_ch=3,
        num_feat=info["num_feat"],
        num_block=info["num_block"],
        num_grow_ch=info["num_grow_ch"],
        scale=info["scale"],
    )


class UpscaleEngine:
    def __init__(self, scale: int = 4, face_enhance: bool = False, tile: int = 512, console=None):
        self.target_scale = scale
        self.face_enhance = face_enhance
        self.tile = tile
        self.console = console
        self.device = _get_device()

        if scale <= 2:
            model_name = "x2plus"
        else:
            model_name = "x4plus"

        self.model_info = MODELS[model_name]
        model_path = _download_model(model_name, console)
        net = _build_model(model_name)

        half = self.device != "cpu"

        self.upsampler = RealESRGANer(
            scale=self.model_info["scale"],
            model_path=str(model_path),
            model=net,
            tile=tile,
            tile_pad=10,
            pre_pad=0,
            half=half,
            device=self.device,
        )

        self.face_enhancer = None
        if face_enhance:
            self._init_face_enhancer()

    def _init_face_enhancer(self):
        try:
            from gfpgan import GFPGANer

            self.face_enhancer = GFPGANer(
                model_path="https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth",
                upscale=self.target_scale,
                arch="clean",
                channel_multiplier=2,
                bg_upsampler=self.upsampler,
            )
        except Exception as e:
            if self.console:
                self.console.print(f"[yellow]Face enhancement unavailable: {e}[/yellow]")

    def upscale(self, input_path: Path, output_path: Path, quality: int = 95) -> tuple[int, int]:
        img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Cannot read image: {input_path}")

        h, w = img.shape[:2]

        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            if self.face_enhancer is not None:
                _, _, output = self.face_enhancer.enhance(
                    img, has_aligned=False, only_center_face=False, paste_back=True
                )
            else:
                output, _ = self.upsampler.enhance(img, outscale=self.target_scale)
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout

        out_h, out_w = output.shape[:2]

        ext = output_path.suffix.lower()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if ext in (".jpg", ".jpeg"):
            cv2.imwrite(str(output_path), output, [cv2.IMWRITE_JPEG_QUALITY, quality])
        elif ext == ".webp":
            cv2.imwrite(str(output_path), output, [cv2.IMWRITE_WEBP_QUALITY, quality])
        elif ext == ".png":
            cv2.imwrite(str(output_path), output, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        else:
            cv2.imwrite(str(output_path), output)

        return out_w, out_h
