import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from upscaler.utils import collect_images, make_output_path, get_image_info

console = Console()


def _format_size(path: Path) -> str:
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@click.command()
@click.argument("input_path", type=click.Path(exists=True), required=False, default=None)
@click.option("-s", "--scale", type=click.Choice(["2", "4"]), default="4", help="Upscale factor (2x or 4x)")
@click.option("-o", "--output", type=str, default=None, help="Output path (file or directory)")
@click.option("--face", is_flag=True, help="Enable face enhancement (GFPGAN)")
@click.option("--format", "fmt", type=click.Choice(["jpg", "png", "webp"]), default=None, help="Output format")
@click.option("--quality", type=int, default=95, help="JPEG/WebP quality (1-100)")
@click.option("--tile", type=int, default=512, help="Tile size for processing (lower = less memory)")
def main(input_path: str | None, scale: str, output: str | None, face: bool, fmt: str | None, quality: int, tile: int):
    """Upscale photos using Real-ESRGAN neural network.

    \b
    Run without arguments for interactive mode:
      upscale

    \b
    Or use directly:
      upscale photo.jpg                  # 4x upscale, saves as photo_4x.jpg
      upscale photo.jpg -s 2             # 2x upscale
      upscale photo.jpg -o result.png    # custom output
      upscale ./photos/                  # batch processing
      upscale photo.jpg --face           # with face enhancement
    """
    if input_path is None:
        from upscaler.interactive import run_interactive
        run_interactive()
        return

    scale_int = int(scale)
    images = collect_images(Path(input_path))

    if not images:
        console.print("[red]No supported images found.[/red]")
        console.print("Supported formats: jpg, jpeg, png, webp, tiff, bmp")
        sys.exit(1)

    console.print(Panel.fit(
        f"[bold cyan]Upscaler[/bold cyan] v1.0 — Real-ESRGAN {scale_int}x",
        border_style="cyan",
    ))

    console.print("[dim]Loading model...[/dim]")
    start = time.time()

    from upscaler.engine import UpscaleEngine
    engine = UpscaleEngine(scale=scale_int, face_enhance=face, tile=tile, console=console)
    load_time = time.time() - start

    console.print(f"[green]Model loaded[/green] [dim]({load_time:.1f}s, device: {engine.device})[/dim]\n")

    is_batch = len(images) > 1
    output_dir = Path(output) if output and is_batch else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    results = Table(show_header=True, header_style="bold", box=box.ROUNDED, border_style="dim")
    results.add_column("File", style="cyan")
    results.add_column("Input", justify="right")
    results.add_column("Output", justify="right")
    results.add_column("Size", justify="right")
    results.add_column("Time", justify="right")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style="green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Upscaling...", total=len(images))

        for img_path in images:
            progress.update(task, description=f"[cyan]{img_path.name}[/cyan]")

            if output_dir:
                out_ext = f".{fmt}" if fmt else img_path.suffix
                out_path = output_dir / f"{img_path.stem}_{scale_int}x{out_ext}"
            else:
                out_path = make_output_path(img_path, output if not is_batch else None, scale_int, fmt)

            in_w, in_h, _ = get_image_info(img_path)
            t0 = time.time()

            try:
                out_w, out_h = engine.upscale(img_path, out_path, quality=quality)
                elapsed = time.time() - t0

                results.add_row(
                    img_path.name,
                    f"{in_w}x{in_h}",
                    f"{out_w}x{out_h}",
                    _format_size(out_path),
                    f"{elapsed:.1f}s",
                )
            except Exception as e:
                results.add_row(img_path.name, f"{in_w}x{in_h}", "[red]FAILED[/red]", "", str(e))

            progress.advance(task)

    console.print()
    console.print(results)
    total_time = time.time() - start
    console.print(f"\n[green]Done![/green] [dim]{len(images)} image(s) in {total_time:.1f}s[/dim]")


if __name__ == "__main__":
    main()
