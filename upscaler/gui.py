"""Графический интерфейс Upscaler на customtkinter.

Современный аккуратный дизайн без градиентов, с перетаскиванием файлов,
миниатюрами и стильными контролами. Требует Tcl/Tk < 9.0 (customtkinter и
tkinterdnd2 несовместимы с Tk 9.0).
"""
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageOps

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_IMPORTED = True
except Exception:
    _DND_IMPORTED = False

from upscaler.utils import collect_images, get_image_info, make_output_path

# ----------------------------- палитра (light, dark) -----------------------
BG        = ("#ECECEE", "#161618")
CARD      = ("#FFFFFF", "#1F1F22")
SUNKEN    = ("#F5F5F7", "#202023")
BORDER    = ("#E3E3E7", "#2E2E32")
TEXT      = ("#1C1C1E", "#F2F2F7")
MUTED     = ("#8A8A8E", "#98989D")
ACCENT    = "#3B82F6"
ACCENT_HV = "#2F6FE0"
ACCENT_SOFT = ("#E8F0FE", "#1B2A47")
OK        = "#22C55E"
ERR       = "#EF4444"
GHOST_HV  = ("#EDEDF0", "#2A2A2E")

FORMATS = ["Как оригинал", "JPEG", "PNG", "WebP"]
FORMAT_MAP = {"Как оригинал": None, "JPEG": "jpg", "PNG": "png", "WebP": "webp"}
QUALITIES = ["95%", "85%", "100%"]

FONT = "SF Pro Display"
FONT_TX = "SF Pro Text"


def _make_root():
    """Создаёт корневое окно с поддержкой drag-and-drop, если она доступна."""
    if _DND_IMPORTED:
        try:
            class _Root(ctk.CTk, TkinterDnD.DnDWrapper):
                def __init__(self, *a, **k):
                    super().__init__(*a, **k)
                    self.TkdndVersion = TkinterDnD._require(self)
            root = _Root()
            return root, True
        except Exception:
            pass
    return ctk.CTk(), False


class UpscalerApp:
    def __init__(self):
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.root, self.dnd_enabled = _make_root()
        self.root.title("Upscaler")
        self.root.geometry("640x820")
        self.root.minsize(600, 760)
        self.root.configure(fg_color=BG)

        self.files: list[Path] = []
        self.row_widgets: dict[str, ctk.CTkLabel] = {}
        self._thumbs: list = []                 # удержание ссылок на CTkImage
        self.last_output_dir: Path | None = None
        self.event_queue: queue.Queue = queue.Queue()
        self.processing = False

        self._build_ui()
        self.root.after(100, self._poll_events)

    # --------------------------------------------------------------- UI
    def _build_ui(self):
        root = ctk.CTkFrame(self.root, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=22, pady=20)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(5, weight=1)

        # ---- Заголовок
        head = ctk.CTkFrame(root, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Upscaler", text_color=TEXT,
                     font=ctk.CTkFont(FONT, 28, "bold")).grid(row=0, column=0, sticky="w")
        badge = ctk.CTkLabel(head, text="  Real-ESRGAN  ", text_color=ACCENT,
                             font=ctk.CTkFont(FONT_TX, 11, "bold"),
                             fg_color=ACCENT_SOFT, corner_radius=8, height=24)
        badge.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(root, text="Увеличение разрешения фото с восстановлением чёткости",
                     text_color=MUTED, font=ctk.CTkFont(FONT_TX, 13)).grid(
            row=1, column=0, sticky="w", pady=(2, 16))

        # ---- Зона перетаскивания
        self.drop = ctk.CTkFrame(root, fg_color=SUNKEN, border_width=2,
                                 border_color=BORDER, corner_radius=18, height=150)
        self.drop.grid(row=2, column=0, sticky="ew")
        self.drop.grid_propagate(False)
        self.drop.grid_columnconfigure(0, weight=1)
        self.drop.grid_rowconfigure(0, weight=1)
        self.drop.grid_rowconfigure(3, weight=1)

        chip = ctk.CTkLabel(self.drop, text="↑", text_color=ACCENT,
                            font=ctk.CTkFont(FONT, 26, "bold"),
                            fg_color=ACCENT_SOFT, corner_radius=24,
                            width=52, height=52)
        chip.grid(row=1, column=0, pady=(0, 6))
        main_txt = "Перетащите фото или папку сюда" if self.dnd_enabled \
            else "Нажмите, чтобы выбрать фото или папку"
        self.drop_title = ctk.CTkLabel(self.drop, text=main_txt, text_color=TEXT,
                                       font=ctk.CTkFont(FONT_TX, 14, "bold"))
        self.drop_title.grid(row=2, column=0)
        sub = "или нажмите, чтобы выбрать" if self.dnd_enabled else \
            "JPG · PNG · WebP · TIFF · BMP"
        ctk.CTkLabel(self.drop, text=sub, text_color=MUTED,
                     font=ctk.CTkFont(FONT_TX, 12)).grid(row=3, column=0, sticky="n")

        for w in (self.drop, chip, self.drop_title):
            w.bind("<Button-1>", lambda e: self._choose_files())
            w.configure(cursor="pointinghand")
        if self.dnd_enabled:
            self._register_dnd()

        # ---- Кнопки выбора
        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        actions.grid_columnconfigure(2, weight=1)
        self._secondary(actions, "Выбрать файлы", self._choose_files).grid(row=0, column=0)
        self._secondary(actions, "Выбрать папку", self._choose_folder).grid(row=0, column=1, padx=(8, 0))
        self._ghost(actions, "Очистить", self._clear_files).grid(row=0, column=3, sticky="e")

        # ---- Настройки
        card = ctk.CTkFrame(root, fg_color=CARD, border_width=1,
                            border_color=BORDER, corner_radius=16)
        card.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        card.grid_columnconfigure(1, weight=1)

        self._row_label(card, 0, "Увеличение")
        self.scale_var = ctk.StringVar(value="4x")
        seg = ctk.CTkSegmentedButton(card, values=["2x", "4x"], variable=self.scale_var,
                                     command=lambda _: self._render_rows(),
                                     fg_color=SUNKEN, selected_color=ACCENT,
                                     selected_hover_color=ACCENT_HV,
                                     unselected_color=SUNKEN, text_color=TEXT,
                                     font=ctk.CTkFont(FONT_TX, 13, "bold"),
                                     corner_radius=9, height=32, width=120)
        seg.grid(row=0, column=1, sticky="e", padx=16, pady=(16, 8))

        self._row_label(card, 1, "Формат")
        self.format_var = ctk.StringVar(value=FORMATS[0])
        self._option(card, self.format_var, FORMATS).grid(row=1, column=1, sticky="e", padx=16, pady=8)

        self._row_label(card, 2, "Качество")
        self.quality_var = ctk.StringVar(value=QUALITIES[0])
        self._option(card, self.quality_var, QUALITIES).grid(row=2, column=1, sticky="e", padx=16, pady=8)

        self._row_label(card, 3, "Улучшать лица")
        self.face_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(card, text="", variable=self.face_var, progress_color=ACCENT,
                      width=46).grid(row=3, column=1, sticky="e", padx=18, pady=(8, 16))

        # ---- Список файлов
        self.list = ctk.CTkScrollableFrame(root, fg_color=CARD, border_width=1,
                                           border_color=BORDER, corner_radius=16,
                                           label_text="")
        self.list.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        self.list.grid_columnconfigure(0, weight=1)

        # ---- Прогресс + статус
        self.progress = ctk.CTkProgressBar(root, height=8, corner_radius=4,
                                           progress_color=ACCENT, fg_color=BORDER)
        self.progress.set(0)
        self.progress.grid(row=6, column=0, sticky="ew", pady=(16, 8))
        self.status = ctk.CTkLabel(root, text="Готов к работе", text_color=MUTED,
                                   font=ctk.CTkFont(FONT_TX, 12))
        self.status.grid(row=7, column=0, sticky="w")

        # ---- Кнопка запуска
        self.run_btn = ctk.CTkButton(root, text="Увеличить", command=self._start,
                                     fg_color=ACCENT, hover_color=ACCENT_HV,
                                     text_color="#FFFFFF", corner_radius=12, height=48,
                                     font=ctk.CTkFont(FONT, 15, "bold"))
        self.run_btn.grid(row=8, column=0, sticky="ew", pady=(12, 0))

        self.open_btn = ctk.CTkButton(root, text="Открыть папку с результатом",
                                      command=self._open_output, height=40, corner_radius=10,
                                      fg_color="transparent", hover_color=GHOST_HV,
                                      text_color=ACCENT, border_width=1, border_color=BORDER,
                                      font=ctk.CTkFont(FONT_TX, 13, "bold"))
        self.open_btn.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        self.open_btn.grid_remove()

        self._render_rows()

    # ---- мелкие конструкторы виджетов
    def _secondary(self, parent, text, cmd):
        return ctk.CTkButton(parent, text=text, command=cmd, height=34, corner_radius=10,
                             fg_color=CARD, hover_color=GHOST_HV, text_color=TEXT,
                             border_width=1, border_color=BORDER,
                             font=ctk.CTkFont(FONT_TX, 13))

    def _ghost(self, parent, text, cmd):
        return ctk.CTkButton(parent, text=text, command=cmd, height=34, corner_radius=10,
                             fg_color="transparent", hover_color=GHOST_HV, text_color=MUTED,
                             font=ctk.CTkFont(FONT_TX, 13))

    def _option(self, parent, var, values):
        return ctk.CTkOptionMenu(parent, variable=var, values=values, width=150, height=32,
                                 corner_radius=9, fg_color=SUNKEN, button_color=SUNKEN,
                                 button_hover_color=GHOST_HV, text_color=TEXT,
                                 font=ctk.CTkFont(FONT_TX, 13),
                                 dropdown_fg_color=CARD, dropdown_text_color=TEXT,
                                 dropdown_hover_color=ACCENT_SOFT)

    def _row_label(self, parent, row, text):
        ctk.CTkLabel(parent, text=text, text_color=TEXT,
                     font=ctk.CTkFont(FONT_TX, 13)).grid(
            row=row, column=0, sticky="w", padx=16, pady=8)

    # ---------------------------------------------------------- drag&drop
    def _register_dnd(self):
        for w in (self.drop,):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)
            w.dnd_bind("<<DropEnter>>", lambda e: self._drop_hover(True))
            w.dnd_bind("<<DropLeave>>", lambda e: self._drop_hover(False))

    def _drop_hover(self, active: bool):
        self.drop.configure(border_color=ACCENT if active else BORDER,
                            fg_color=ACCENT_SOFT if active else SUNKEN)

    def _on_drop(self, event):
        self._drop_hover(False)
        if self.processing:
            return
        raw = self.root.tk.splitlist(event.data)
        self._add_paths([Path(p) for p in raw])

    # ------------------------------------------------------------- файлы
    def _choose_files(self):
        if self.processing:
            return
        paths = filedialog.askopenfilenames(
            title="Выберите изображения",
            filetypes=[("Изображения", "*.jpg *.jpeg *.png *.webp *.tiff *.tif *.bmp")])
        if paths:
            self._add_paths([Path(p) for p in paths])

    def _choose_folder(self):
        if self.processing:
            return
        folder = filedialog.askdirectory(title="Выберите папку с изображениями")
        if folder:
            self._add_paths([Path(folder)])

    def _clear_files(self):
        if self.processing:
            return
        self.files = []
        self._render_rows()

    def _add_paths(self, paths):
        collected = []
        for p in paths:
            collected.extend(collect_images(p))
        seen = {str(f) for f in self.files}
        for f in collected:
            if str(f) not in seen:
                seen.add(str(f))
                self.files.append(f)
        self._render_rows()

    def _thumb(self, path: Path):
        try:
            img = Image.open(path).convert("RGB")
            img = ImageOps.fit(img, (40, 40), Image.LANCZOS)
            ct = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 40))
            self._thumbs.append(ct)
            return ct
        except Exception:
            return None

    def _render_rows(self):
        for child in self.list.winfo_children():
            child.destroy()
        self.row_widgets.clear()
        self._thumbs.clear()

        if not self.files:
            ctk.CTkLabel(self.list, text="Файлы не выбраны", text_color=MUTED,
                         font=ctk.CTkFont(FONT_TX, 12)).pack(pady=22)
            self.status.configure(text="Готов к работе", text_color=MUTED)
            return

        scale = int(self.scale_var.get().replace("x", ""))
        for f in self.files:
            try:
                w, h, _ = get_image_info(f)
                info = f"{w}×{h}  →  {w*scale}×{h*scale}"
            except Exception:
                info = "—"

            row = ctk.CTkFrame(self.list, fg_color=SUNKEN, corner_radius=10)
            row.pack(fill="x", padx=6, pady=4)
            row.grid_columnconfigure(1, weight=1)

            thumb = self._thumb(f)
            ctk.CTkLabel(row, text="", image=thumb, width=40, height=40).grid(
                row=0, column=0, rowspan=2, padx=10, pady=8)
            ctk.CTkLabel(row, text=f.name, text_color=TEXT, anchor="w",
                         font=ctk.CTkFont(FONT_TX, 13, "bold")).grid(
                row=0, column=1, sticky="w", pady=(8, 0))
            ctk.CTkLabel(row, text=info, text_color=MUTED, anchor="w",
                         font=ctk.CTkFont(FONT_TX, 11)).grid(
                row=1, column=1, sticky="w", pady=(0, 8))
            status = ctk.CTkLabel(row, text="", text_color=MUTED, width=90,
                                  font=ctk.CTkFont(FONT_TX, 12, "bold"))
            status.grid(row=0, column=2, rowspan=2, padx=12)
            self.row_widgets[str(f)] = status

        self.status.configure(text=f"Выбрано файлов: {len(self.files)}", text_color=MUTED)

    # ------------------------------------------------------- обработка
    def _start(self):
        if self.processing:
            return
        if not self.files:
            self.status.configure(text="Сначала выберите изображения", text_color=ERR)
            return
        self.processing = True
        self.open_btn.grid_remove()
        self.run_btn.configure(state="disabled", text="Обработка…")
        self.progress.set(0)
        for lbl in self.row_widgets.values():
            lbl.configure(text="", text_color=MUTED)

        scale = int(self.scale_var.get().replace("x", ""))
        fmt = FORMAT_MAP[self.format_var.get()]
        quality = int(self.quality_var.get().replace("%", ""))
        face = self.face_var.get()
        files = list(self.files)
        threading.Thread(target=self._worker,
                         args=(files, scale, fmt, quality, face), daemon=True).start()

    def _worker(self, files, scale, fmt, quality, face):
        q = self.event_queue
        try:
            q.put(("status", "Загрузка модели…"))
            from upscaler.engine import UpscaleEngine
            engine = UpscaleEngine(scale=scale, face_enhance=face, tile=512)
            q.put(("status", f"Модель загружена · {engine.device}"))

            total = len(files)
            last_dir = None
            for i, f in enumerate(files):
                q.put(("current", (str(f), Path(f).name)))
                out = make_output_path(f, None, scale, fmt)
                last_dir = out.parent
                try:
                    ow, oh = engine.upscale(f, out, quality=quality)
                    q.put(("done", (str(f), f"✓ {ow}×{oh}")))
                except Exception as e:
                    q.put(("fail", (str(f), "✗ ошибка")))
                    q.put(("status", f"Ошибка на {Path(f).name}: {e}"))
                q.put(("progress", (i + 1) / total))
            q.put(("finished", (total, str(last_dir) if last_dir else "")))
        except Exception as e:
            q.put(("error", f"{e}\n{traceback.format_exc()}"))

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.event_queue.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle(self, kind, payload):
        if kind == "status":
            self.status.configure(text=payload, text_color=MUTED)
        elif kind == "current":
            key, name = payload
            self.status.configure(text=f"Обработка: {name}", text_color=MUTED)
            if key in self.row_widgets:
                self.row_widgets[key].configure(text="…", text_color=MUTED)
        elif kind == "progress":
            self.progress.set(payload)
        elif kind == "done":
            key, text = payload
            if key in self.row_widgets:
                self.row_widgets[key].configure(text=text, text_color=OK)
        elif kind == "fail":
            key, text = payload
            if key in self.row_widgets:
                self.row_widgets[key].configure(text=text, text_color=ERR)
        elif kind == "finished":
            total, last_dir = payload
            self.processing = False
            self.run_btn.configure(state="normal", text="Увеличить")
            self.progress.set(1)
            self.status.configure(text=f"Готово! Обработано: {total}", text_color=OK)
            if last_dir:
                self.last_output_dir = Path(last_dir)
                self.open_btn.grid()
        elif kind == "error":
            self.processing = False
            self.run_btn.configure(state="normal", text="Увеличить")
            self.status.configure(text=f"Ошибка: {payload.splitlines()[0]}", text_color=ERR)

    def _open_output(self):
        if self.last_output_dir and self.last_output_dir.exists():
            try:
                subprocess.run(["open", str(self.last_output_dir)], check=False)
            except Exception:
                pass

    def run(self):
        self.root.mainloop()


def main():
    UpscalerApp().run()


if __name__ == "__main__":
    main()
