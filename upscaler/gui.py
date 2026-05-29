"""Графический интерфейс Upscaler на нативном tkinter/ttk (тема clam).

Нативный ttk рисуется надёжно на macOS (в отличие от customtkinter, который
на этой связке Python/Tk даёт пустое окно). Тема clam полностью стилизуется —
делаем аккуратный плоский дизайн с акцентом, миниатюрами и drag-and-drop.
"""
import queue
import subprocess
import threading
import traceback
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, filedialog, ttk
import tkinter as tk

from PIL import Image, ImageOps, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_IMPORTED = True
except Exception:
    _DND_IMPORTED = False

from upscaler.utils import collect_images, get_image_info, make_output_path

# --------------------------------- палитра (светлая, плоская) --------------
WIN     = "#EDEFF3"
CARD    = "#FFFFFF"
ROW     = "#F5F6F8"
BORDER  = "#DCE0E6"
TEXT    = "#1B1F24"
MUTED   = "#6B7280"
ACCENT  = "#2F6FED"
ACCENT_HV = "#2559C4"
DROP_BG = "#F4F7FD"
OK      = "#157F3B"
ERR     = "#CF222E"

FONT = "SF Pro Display"
FONT_TX = "SF Pro Text"

FORMATS = ["Как оригинал", "JPEG", "PNG", "WebP"]
FORMAT_MAP = {"Как оригинал": None, "JPEG": "jpg", "PNG": "png", "WebP": "webp"}
QUALITIES = ["95%", "85%", "100%"]


def _make_root():
    if _DND_IMPORTED:
        try:
            root = TkinterDnD.Tk()
            return root, True
        except Exception:
            pass
    return Tk(), False


class UpscalerApp:
    def __init__(self):
        self.root, self.dnd_enabled = _make_root()
        self.root.title("Upscaler")
        self.root.geometry("640x800")
        self.root.minsize(600, 740)
        self.root.configure(bg=WIN)

        self._init_style()

        self.files: list[Path] = []
        self.row_ids: dict[str, str] = {}
        self._thumbs: dict[str, ImageTk.PhotoImage] = {}
        self.last_output_dir: Path | None = None
        self.event_queue: queue.Queue = queue.Queue()
        self.processing = False

        self._build_ui()
        self.root.after(100, self._poll_events)

    # ------------------------------------------------------------- стиль
    def _init_style(self):
        st = ttk.Style()
        st.theme_use("clam")

        st.configure(".", background=WIN, foreground=TEXT, font=(FONT_TX, 13))
        st.configure("Win.TFrame", background=WIN)
        st.configure("Card.TFrame", background=CARD)
        st.configure("Row.TFrame", background=ROW)

        st.configure("Title.TLabel", background=WIN, foreground=TEXT, font=(FONT, 26, "bold"))
        st.configure("Sub.TLabel", background=WIN, foreground=MUTED, font=(FONT_TX, 13))
        st.configure("Card.TLabel", background=CARD, foreground=TEXT, font=(FONT_TX, 13))
        st.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=(FONT_TX, 12))
        st.configure("Status.TLabel", background=WIN, foreground=MUTED, font=(FONT_TX, 12))

        # Акцентная кнопка
        st.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF",
                     font=(FONT, 15, "bold"), borderwidth=0, focuscolor=ACCENT,
                     padding=(16, 12))
        st.map("Accent.TButton",
               background=[("pressed", ACCENT_HV), ("active", ACCENT_HV), ("disabled", "#A9C2F4")],
               foreground=[("disabled", "#EAF0FC")])

        # Вторичная кнопка
        st.configure("Secondary.TButton", background=CARD, foreground=TEXT,
                     font=(FONT_TX, 13), borderwidth=1, padding=(12, 8), relief="solid")
        st.map("Secondary.TButton",
               background=[("active", "#EEF1F5")], bordercolor=[("!disabled", BORDER)])

        # Призрачная кнопка
        st.configure("Ghost.TButton", background=WIN, foreground=MUTED,
                     font=(FONT_TX, 13), borderwidth=0, padding=(10, 8))
        st.map("Ghost.TButton", background=[("active", "#E3E6EB")])

        # Переключатель масштаба (Toolbutton)
        st.configure("Seg.Toolbutton", background=CARD, foreground=TEXT,
                     font=(FONT_TX, 13, "bold"), borderwidth=1, padding=(18, 6), relief="solid")
        st.map("Seg.Toolbutton",
               background=[("selected", ACCENT), ("active", "#EEF1F5")],
               foreground=[("selected", "#FFFFFF")],
               bordercolor=[("!disabled", BORDER)])

        st.configure("TCheckbutton", background=CARD, foreground=TEXT, font=(FONT_TX, 13))
        st.map("TCheckbutton", background=[("active", CARD)])

        st.configure("TCombobox", fieldbackground=ROW, background=ROW,
                     foreground=TEXT, arrowcolor=TEXT, borderwidth=0, padding=6)
        st.map("TCombobox", fieldbackground=[("readonly", ROW)])

        st.configure("Accent.Horizontal.TProgressbar",
                     troughcolor=BORDER, background=ACCENT, borderwidth=0, thickness=8)

        # Список файлов
        st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                     borderwidth=0, rowheight=52, font=(FONT_TX, 12))
        st.configure("Treeview.Heading", background=CARD, foreground=MUTED,
                     font=(FONT_TX, 11), borderwidth=0, relief="flat")
        st.map("Treeview", background=[("selected", "#E8F0FE")],
               foreground=[("selected", TEXT)])

    # ------------------------------------------------------------- разметка
    def _build_ui(self):
        m = ttk.Frame(self.root, style="Win.TFrame", padding=22)
        m.pack(fill="both", expand=True)
        m.columnconfigure(0, weight=1)
        m.rowconfigure(5, weight=1)

        # заголовок
        head = ttk.Frame(m, style="Win.TFrame")
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Upscaler", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        badge = tk.Label(head, text=" Real-ESRGAN ", bg="#E6EEFE", fg=ACCENT,
                         font=(FONT_TX, 11, "bold"), padx=6, pady=3)
        badge.grid(row=0, column=1, sticky="e")
        ttk.Label(m, text="Увеличение разрешения фото с восстановлением чёткости",
                  style="Sub.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 16))

        # зона перетаскивания
        self.drop = tk.Frame(m, bg=DROP_BG, highlightbackground=BORDER,
                             highlightthickness=2, height=148)
        self.drop.grid(row=2, column=0, sticky="ew")
        self.drop.grid_propagate(False)
        self.drop.columnconfigure(0, weight=1)
        self.drop.rowconfigure(0, weight=1)
        self.drop.rowconfigure(3, weight=1)

        chip = tk.Label(self.drop, text="↑", bg="#E1ECFE", fg=ACCENT,
                        font=(FONT, 22, "bold"), width=3, height=1)
        chip.grid(row=1, column=0, pady=(0, 4))
        title = "Перетащите фото или папку сюда" if self.dnd_enabled \
            else "Нажмите, чтобы выбрать фото или папку"
        self.drop_title = tk.Label(self.drop, text=title, bg=DROP_BG, fg=TEXT,
                                   font=(FONT_TX, 14, "bold"))
        self.drop_title.grid(row=2, column=0)
        sub = "или нажмите, чтобы выбрать" if self.dnd_enabled else "JPG · PNG · WebP · TIFF · BMP"
        tk.Label(self.drop, text=sub, bg=DROP_BG, fg=MUTED,
                 font=(FONT_TX, 12)).grid(row=3, column=0, sticky="n")

        for w in (self.drop, chip, self.drop_title):
            w.bind("<Button-1>", lambda e: self._choose_files())
        if self.dnd_enabled:
            self._register_dnd()

        # кнопки выбора
        acts = ttk.Frame(m, style="Win.TFrame")
        acts.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        acts.columnconfigure(2, weight=1)
        ttk.Button(acts, text="Выбрать файлы", style="Secondary.TButton",
                   command=self._choose_files, takefocus=False).grid(row=0, column=0)
        ttk.Button(acts, text="Выбрать папку", style="Secondary.TButton",
                   command=self._choose_folder, takefocus=False).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(acts, text="Очистить", style="Ghost.TButton",
                   command=self._clear_files, takefocus=False).grid(row=0, column=3, sticky="e")

        # настройки
        card = tk.Frame(m, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        card.columnconfigure(1, weight=1)
        pad = dict(padx=16, pady=9)

        tk.Label(card, text="Увеличение", bg=CARD, fg=TEXT, font=(FONT_TX, 13)).grid(
            row=0, column=0, sticky="w", **pad)
        seg = ttk.Frame(card, style="Card.TFrame")
        seg.grid(row=0, column=1, sticky="e", padx=16, pady=9)
        self.scale_var = StringVar(value="4x")
        for i, val in enumerate(("2x", "4x")):
            ttk.Radiobutton(seg, text=val, value=val, variable=self.scale_var,
                            style="Seg.Toolbutton", takefocus=False,
                            command=self._render_rows).grid(row=0, column=i)

        tk.Label(card, text="Формат", bg=CARD, fg=TEXT, font=(FONT_TX, 13)).grid(
            row=1, column=0, sticky="w", **pad)
        self.format_var = StringVar(value=FORMATS[0])
        ttk.Combobox(card, textvariable=self.format_var, values=FORMATS, state="readonly",
                     width=16).grid(row=1, column=1, sticky="e", **pad)

        tk.Label(card, text="Качество", bg=CARD, fg=TEXT, font=(FONT_TX, 13)).grid(
            row=2, column=0, sticky="w", **pad)
        self.quality_var = StringVar(value=QUALITIES[0])
        ttk.Combobox(card, textvariable=self.quality_var, values=QUALITIES, state="readonly",
                     width=16).grid(row=2, column=1, sticky="e", **pad)

        tk.Label(card, text="Улучшать лица", bg=CARD, fg=TEXT, font=(FONT_TX, 13)).grid(
            row=3, column=0, sticky="w", **pad)
        self.face_var = BooleanVar(value=False)
        ttk.Checkbutton(card, text="GFPGAN", variable=self.face_var,
                        takefocus=False).grid(row=3, column=1, sticky="e", **pad)

        # список файлов
        wrap = tk.Frame(m, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        wrap.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, columns=("info", "status"), show="tree headings",
                                 selectmode="none")
        self.tree.heading("#0", text="  Файл")
        self.tree.heading("info", text="Размер")
        self.tree.heading("status", text="")
        self.tree.column("#0", width=280, anchor="w")
        self.tree.column("info", width=190, anchor="w")
        self.tree.column("status", width=90, anchor="e")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("ok", foreground=OK)
        self.tree.tag_configure("err", foreground=ERR)
        self.tree.tag_configure("wait", foreground=MUTED)

        # прогресс + статус
        self.progress = ttk.Progressbar(m, style="Accent.Horizontal.TProgressbar",
                                        mode="determinate", maximum=1.0)
        self.progress.grid(row=6, column=0, sticky="ew", pady=(16, 8))
        self.status_var = StringVar(value="Готов к работе")
        ttk.Label(m, textvariable=self.status_var, style="Status.TLabel").grid(
            row=7, column=0, sticky="w")

        # кнопки запуска
        self.run_btn = ttk.Button(m, text="Увеличить", style="Accent.TButton",
                                  command=self._start, takefocus=False)
        self.run_btn.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        self.open_btn = ttk.Button(m, text="Открыть папку с результатом",
                                   style="Secondary.TButton", command=self._open_output,
                                   takefocus=False)
        self.open_btn.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        self.open_btn.grid_remove()

        self._render_rows()

    # --------------------------------------------------------- drag&drop
    def _register_dnd(self):
        self.drop.drop_target_register(DND_FILES)
        self.drop.dnd_bind("<<Drop>>", self._on_drop)
        self.drop.dnd_bind("<<DropEnter>>", lambda e: self._hover(True))
        self.drop.dnd_bind("<<DropLeave>>", lambda e: self._hover(False))

    def _hover(self, active):
        self.drop.configure(highlightbackground=ACCENT if active else BORDER,
                            highlightthickness=2)

    def _on_drop(self, event):
        self._hover(False)
        if self.processing:
            return
        self._add_paths([Path(p) for p in self.root.tk.splitlist(event.data)])

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
            img = ImageOps.fit(img, (38, 38), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._thumbs[str(path)] = photo
            return photo
        except Exception:
            return None

    def _render_rows(self):
        self.tree.delete(*self.tree.get_children())
        self.row_ids.clear()
        self._thumbs.clear()

        if not self.files:
            self.status_var.set("Готов к работе")
            return

        scale = int(self.scale_var.get().replace("x", ""))
        for f in self.files:
            try:
                w, h, _ = get_image_info(f)
                info = f"{w}×{h} → {w*scale}×{h*scale}"
            except Exception:
                info = "—"
            thumb = self._thumb(f)
            rid = self.tree.insert("", "end", text="  " + f.name, image=thumb,
                                   values=(info, ""), tags=("wait",))
            self.row_ids[str(f)] = rid
        self.status_var.set(f"Выбрано файлов: {len(self.files)}")

    # ------------------------------------------------------- обработка
    def _start(self):
        if self.processing:
            return
        if not self.files:
            self.status_var.set("Сначала выберите изображения")
            return
        self.processing = True
        self.open_btn.grid_remove()
        self.run_btn.configure(text="Обработка…", state="disabled")
        self.progress.configure(value=0)

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
                q.put(("current", str(f)))
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
            self.status_var.set(payload)
        elif kind == "current":
            self.status_var.set(f"Обработка: {Path(payload).name}")
            if payload in self.row_ids:
                self.tree.set(self.row_ids[payload], "status", "…")
        elif kind == "progress":
            self.progress.configure(value=payload)
        elif kind == "done":
            key, text = payload
            if key in self.row_ids:
                self.tree.set(self.row_ids[key], "status", text)
                self.tree.item(self.row_ids[key], tags=("ok",))
        elif kind == "fail":
            key, text = payload
            if key in self.row_ids:
                self.tree.set(self.row_ids[key], "status", text)
                self.tree.item(self.row_ids[key], tags=("err",))
        elif kind == "finished":
            total, last_dir = payload
            self.processing = False
            self.run_btn.configure(text="Увеличить", state="normal")
            self.progress.configure(value=1.0)
            self.status_var.set(f"Готово! Обработано: {total}")
            if last_dir:
                self.last_output_dir = Path(last_dir)
                self.open_btn.grid()
        elif kind == "error":
            self.processing = False
            self.run_btn.configure(text="Увеличить", state="normal")
            self.status_var.set(f"Ошибка: {payload.splitlines()[0]}")

    def _open_output(self):
        if self.last_output_dir and self.last_output_dir.exists():
            subprocess.run(["open", str(self.last_output_dir)], check=False)

    def run(self):
        self.root.mainloop()


def main():
    UpscalerApp().run()


if __name__ == "__main__":
    main()
