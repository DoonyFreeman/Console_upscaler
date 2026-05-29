"""Точка входа для PyInstaller-сборки графического приложения.

При UPSCALER_SELFTEST=<output_dir> вместо GUI запускается автотест:
импортирует движок и апскейлит сгенерированное изображение. Нужно, чтобы
проверить, что torch/basicsr/realesrgan корректно работают внутри бандла.
"""
import os
import sys


def _selftest(out_dir: str) -> int:
    from pathlib import Path
    from PIL import Image
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = out / "selftest_in.png"
    Image.new("RGB", (128, 96), (60, 90, 150)).save(src)

    from upscaler.engine import UpscaleEngine
    from upscaler.utils import make_output_path

    engine = UpscaleEngine(scale=2, face_enhance=False, tile=512)
    dst = make_output_path(src, None, 2, "png")
    ow, oh = engine.upscale(src, dst, quality=95)
    print(f"SELFTEST_OK device={engine.device} out={ow}x{oh} file={dst.exists()}")
    return 0


def main():
    selftest_dir = os.environ.get("UPSCALER_SELFTEST")
    if selftest_dir:
        try:
            sys.exit(_selftest(selftest_dir))
        except Exception as e:
            import traceback
            print("SELFTEST_FAIL:", e)
            traceback.print_exc()
            sys.exit(1)

    from upscaler.gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
