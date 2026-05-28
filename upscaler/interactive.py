import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.text import Text
from rich import box

from upscaler.utils import collect_images, get_image_info, SUPPORTED_EXTENSIONS

console = Console()

LOGO = """
 ╦ ╦╔═╗╔═╗╔═╗╔═╗╦  ╔═╗╦═╗
 ║ ║╠═╝╚═╗║  ╠═╣║  ║╣ ╠╦╝
 ╚═╝╩  ╚═╝╚═╝╩ ╩╩═╝╚═╝╩╚═"""


def _clean_path(raw: str) -> str:
    p = raw.strip().strip("'\"")
    if p.startswith("~"):
        p = os.path.expanduser(p)
    return p


def _ask_choice(question: str, options: list[tuple[str, str]], default: int = 1) -> str:
    console.print()
    console.print(f"[bold cyan]{question}[/bold cyan]")
    console.print()

    for i, (key, label) in enumerate(options, 1):
        marker = "[bold green]›[/bold green]" if i == default else " "
        console.print(f"  {marker} [bold]{i}[/bold]  {label}")

    console.print()
    while True:
        choice = Prompt.ask(
            "  Ваш выбор",
            default=str(default),
        )
        try:
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        except ValueError:
            pass
        console.print(f"  [red]Введите число от 1 до {len(options)}[/red]")


def _ask_path() -> Path:
    console.print()
    console.print("[bold cyan]Укажите путь к файлу или папке с изображениями[/bold cyan]")
    console.print("[dim]  Можно перетащить файл/папку прямо в терминал[/dim]")
    console.print()

    while True:
        raw = Prompt.ask("  Путь")
        path = Path(_clean_path(raw))

        if not path.exists():
            console.print(f"  [red]Файл не найден: {path}[/red]")
            continue

        images = collect_images(path)
        if not images:
            exts = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            console.print(f"  [red]Изображения не найдены. Поддерживаются: {exts}[/red]")
            continue

        if len(images) == 1:
            w, h, _ = get_image_info(images[0])
            console.print(f"  [green]✓[/green] {images[0].name} — {w}×{h}")
        else:
            console.print(f"  [green]✓[/green] Найдено изображений: {len(images)}")
            for img in images[:5]:
                w, h, _ = get_image_info(img)
                console.print(f"    [dim]{img.name} — {w}×{h}[/dim]")
            if len(images) > 5:
                console.print(f"    [dim]...и ещё {len(images) - 5}[/dim]")

        return path


def _ask_output(input_path: Path, images: list[Path], scale: int, fmt: str) -> str | None:
    console.print()

    if len(images) == 1:
        inp = images[0]
        ext = f".{fmt}" if fmt != "original" else inp.suffix
        default_name = f"{inp.stem}_{scale}x{ext}"
        default_path = str(inp.parent / default_name)

        console.print(f"[bold cyan]Куда сохранить результат?[/bold cyan]")
        console.print(f"[dim]  По умолчанию: {default_path}[/dim]")
        console.print()

        raw = Prompt.ask("  Путь вывода", default="")
        if not raw.strip():
            return None
        return _clean_path(raw)
    else:
        default_dir = str(input_path) + "_upscaled"
        console.print(f"[bold cyan]Папка для сохранения результатов[/bold cyan]")
        console.print(f"[dim]  По умолчанию: {default_dir}[/dim]")
        console.print()

        raw = Prompt.ask("  Папка вывода", default="")
        if not raw.strip():
            return default_dir
        return _clean_path(raw)


def _show_summary(images: list[Path], scale: int, fmt: str, face: bool, output: str | None, quality: int):
    console.print()

    table = Table(
        title="[bold]Параметры обработки[/bold]",
        box=box.ROUNDED,
        show_header=False,
        title_style="cyan",
        border_style="dim",
        padding=(0, 2),
    )
    table.add_column("Параметр", style="bold")
    table.add_column("Значение", style="green")

    if len(images) == 1:
        w, h, _ = get_image_info(images[0])
        table.add_row("Файл", images[0].name)
        table.add_row("Разрешение", f"{w}×{h} → {w*scale}×{h*scale}")
    else:
        table.add_row("Файлов", str(len(images)))

    table.add_row("Увеличение", f"{scale}x (Real-ESRGAN)")
    table.add_row("Формат", fmt if fmt != "original" else "как исходный")
    table.add_row("Качество", f"{quality}%")
    table.add_row("Улучшение лиц", "да (GFPGAN)" if face else "нет")

    if output:
        table.add_row("Сохранение", output)
    else:
        table.add_row("Сохранение", "рядом с оригиналом")

    console.print(table)
    console.print()


def run_interactive():
    console.print(Panel(
        Text(LOGO, style="bold cyan", justify="center"),
        subtitle="[dim]Real-ESRGAN Photo Enhancer[/dim]",
        border_style="cyan",
        padding=(0, 2),
    ))

    # 1. Mode
    mode = _ask_choice("Что хотите сделать?", [
        ("upscale", "🔍  Увеличить разрешение фото"),
        ("upscale_face", "👤  Увеличить + улучшить лица"),
        ("batch", "📁  Пакетная обработка папки"),
    ])

    face = mode == "upscale_face"

    # 2. Scale
    scale_str = _ask_choice("Во сколько раз увеличить?", [
        ("4", "4x — максимальное качество (рекомендуется)"),
        ("2", "2x — быстрее, подходит для небольшого увеличения"),
    ])
    scale = int(scale_str)

    # 3. Input path
    input_path = _ask_path()
    images = collect_images(input_path)

    # 4. Format
    fmt = _ask_choice("Формат выходного файла?", [
        ("original", "Как у исходника"),
        ("jpg", "JPEG — меньший размер"),
        ("png", "PNG — без потерь"),
        ("webp", "WebP — современный, компактный"),
    ])

    # 5. Quality (for lossy formats)
    quality = 95
    if fmt in ("jpg", "webp") or (fmt == "original" and images[0].suffix.lower() in (".jpg", ".jpeg", ".webp")):
        quality_str = _ask_choice("Качество сжатия?", [
            ("95", "95% — высокое (рекомендуется)"),
            ("85", "85% — хороший баланс размер/качество"),
            ("100", "100% — максимальное"),
        ])
        quality = int(quality_str)

    # 6. Output
    output = _ask_output(input_path, images, scale, fmt)

    # 7. Summary + confirm
    _show_summary(images, scale, fmt, face, output, quality)

    if not Confirm.ask("  [bold]Запустить обработку?[/bold]", default=True):
        console.print("\n[dim]Отменено.[/dim]")
        return

    # 8. Run
    console.print()
    _run_upscale(images, input_path, scale, face, fmt, output, quality)


def _run_upscale(images: list[Path], input_path: Path, scale: int, face: bool, fmt: str, output: str | None, quality: int):
    import time
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from upscaler.utils import make_output_path

    console.print("[dim]Загрузка модели...[/dim]")
    start = time.time()

    from upscaler.engine import UpscaleEngine
    engine = UpscaleEngine(scale=scale, face_enhance=face, tile=512, console=console)
    load_time = time.time() - start
    console.print(f"[green]Модель загружена[/green] [dim]({load_time:.1f}с, устройство: {engine.device})[/dim]\n")

    is_batch = len(images) > 1
    output_dir = Path(output) if output and is_batch else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    results = Table(show_header=True, header_style="bold", box=box.ROUNDED, border_style="dim")
    results.add_column("Файл", style="cyan")
    results.add_column("Было", justify="right")
    results.add_column("Стало", justify="right", style="green")
    results.add_column("Размер", justify="right")
    results.add_column("Время", justify="right")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style="green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Обработка...", total=len(images))

        for img_path in images:
            progress.update(task, description=f"[cyan]{img_path.name}[/cyan]")

            if output_dir:
                ext = f".{fmt}" if fmt != "original" else img_path.suffix
                out_path = output_dir / f"{img_path.stem}_{scale}x{ext}"
            else:
                out_fmt = fmt if fmt != "original" else None
                out_path = make_output_path(img_path, output if not is_batch else None, scale, out_fmt)

            in_w, in_h, _ = get_image_info(img_path)
            t0 = time.time()

            try:
                out_w, out_h = engine.upscale(img_path, out_path, quality=quality)
                elapsed = time.time() - t0
                size = out_path.stat().st_size
                for unit in ("B", "KB", "MB", "GB"):
                    if size < 1024:
                        size_str = f"{size:.1f} {unit}"
                        break
                    size /= 1024

                results.add_row(
                    img_path.name,
                    f"{in_w}×{in_h}",
                    f"{out_w}×{out_h}",
                    size_str,
                    f"{elapsed:.1f}с",
                )
            except Exception as e:
                results.add_row(img_path.name, f"{in_w}×{in_h}", "[red]ОШИБКА[/red]", "", str(e))

            progress.advance(task)

    console.print()
    console.print(results)
    total_time = time.time() - start
    console.print(f"\n[bold green]Готово![/bold green] [dim]{len(images)} файл(ов) за {total_time:.1f}с[/dim]")

    if not is_batch and len(images) == 1:
        out_fmt = fmt if fmt != "original" else None
        final = make_output_path(images[0], output, scale, out_fmt)
        console.print(f"[dim]Результат: {final}[/dim]\n")
