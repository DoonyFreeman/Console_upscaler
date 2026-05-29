# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для сборки Upscaler.app (macOS).

Модели Real-ESRGAN/GFPGAN НЕ упаковываются — скачиваются при первом запуске
в ~/.upscaler/models/. Это держит размер приложения минимальным.
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

# Пакеты с динамическими импортами и data-файлами — собираем целиком.
# PySide6 (Qt) подхватывается встроенным хуком PyInstaller автоматически.
for pkg in ("basicsr", "realesrgan", "gfpgan", "facexlib",
            "torchvision", "cv2", "skimage", "scipy"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# torch имеет встроенный хук, но подстрахуемся сабмодулями
hiddenimports += collect_submodules("torch")
hiddenimports += [
    "upscaler", "upscaler.gui", "upscaler.engine", "upscaler.utils",
]

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter.test", "PyQt5", "PySide2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Upscaler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # без окна терминала (--windowed)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Upscaler",
)

app = BUNDLE(
    coll,
    name="Upscaler.app",
    icon="assets/icon.icns",
    bundle_identifier="com.upscaler.app",
    info_plist={
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "CFBundleDisplayName": "Upscaler",
        "CFBundleName": "Upscaler",
        "CFBundleShortVersionString": "1.0.0",
    },
)
