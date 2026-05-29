"""Графический интерфейс Upscaler на PySide6 (Qt).

Qt рисуется надёжно на современных macOS (в отличие от tkinter, который на
macOS 26 либо не отрисовывается, либо падает), даёт нативный drag-and-drop
и полноценную стилизацию.
"""
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QThread, Signal, Slot, QSize
from PySide6.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QComboBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QFileDialog,
    QListWidget, QListWidgetItem, QProgressBar, QButtonGroup,
    QGraphicsDropShadowEffect,
)

from upscaler.utils import collect_images, get_image_info, make_output_path

ACCENT = "#2F6FED"
FORMATS = ["Как оригинал", "JPEG", "PNG", "WebP"]
FORMAT_MAP = {"Как оригинал": None, "JPEG": "jpg", "PNG": "png", "WebP": "webp"}
QUALITIES = ["95%", "85%", "100%"]
EXTS = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.tiff", "*.tif", "*.bmp")

STYLE = """
#window { background: #ECEEF2; }
#title { font-size: 26px; font-weight: 800; color: #161A20; }
#subtitle { font-size: 13px; color: #6B7280; }
#badge { background: #E6EEFE; color: #2F6FED; font-size: 11px; font-weight: 700;
         border-radius: 8px; padding: 4px 8px; }

#drop { background: #F3F7FE; border: 2px dashed #B9CBF2; border-radius: 16px; }
#drop[hover="true"] { background: #E6EEFE; border: 2px dashed #2F6FED; }
#dropChip { background: #E1ECFE; color: #2F6FED; font-size: 22px; font-weight: 800;
            border-radius: 24px; min-width: 48px; max-width: 48px;
            min-height: 48px; max-height: 48px; }
#dropTitle { font-size: 14px; font-weight: 700; color: #1B1F24; }
#dropSub { font-size: 12px; color: #6B7280; }

#card { background: #FFFFFF; border: 1px solid #DCE0E6; border-radius: 16px; }
#rowLabel { font-size: 13px; color: #1B1F24; }

QPushButton#accent { background: #2F6FED; color: white; border: none;
    border-radius: 11px; padding: 13px 18px; font-size: 15px; font-weight: 700; }
QPushButton#accent:hover { background: #2559C4; }
QPushButton#accent:disabled { background: #A9C2F4; }

QPushButton#secondary { background: #FFFFFF; color: #1B1F24; border: 1px solid #DCE0E6;
    border-radius: 10px; padding: 9px 14px; font-size: 13px; }
QPushButton#secondary:hover { background: #EEF1F5; }

QPushButton#ghost { background: transparent; color: #6B7280; border: none;
    border-radius: 10px; padding: 9px 12px; font-size: 13px; }
QPushButton#ghost:hover { background: #E1E4EA; }

QPushButton#seg { background: #F4F5F8; color: #1B1F24; border: 1px solid #DCE0E6;
    padding: 6px 18px; font-size: 13px; font-weight: 700; }
QPushButton#seg:checked { background: #2F6FED; color: white; border: 1px solid #2F6FED; }
QPushButton#seg[side="L"] { border-top-left-radius: 9px; border-bottom-left-radius: 9px; }
QPushButton#seg[side="R"] { border-top-right-radius: 9px; border-bottom-right-radius: 9px; }

QComboBox { background: #F4F5F8; color: #1B1F24; border: none; border-radius: 9px;
    padding: 7px 12px; font-size: 13px; min-width: 130px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: white; color: #1B1F24;
    selection-background-color: #2F6FED; selection-color: white; outline: none; }

QCheckBox { font-size: 13px; color: #1B1F24; spacing: 8px; }
QCheckBox::indicator { width: 20px; height: 20px; border-radius: 6px;
    border: 1px solid #C3C8D0; background: white; }
QCheckBox::indicator:checked { background: #2F6FED; border: 1px solid #2F6FED; }

#list { background: #FFFFFF; border: 1px solid #DCE0E6; border-radius: 16px;
    outline: none; padding: 6px; }
#list::item { border: none; margin: 0; }
#fileRow { background: #F6F7F9; border-radius: 12px; }
#fileName { font-size: 13px; font-weight: 700; color: #1B1F24; }
#fileDim { font-size: 11px; color: #6B7280; }
#fileStatus { font-size: 12px; font-weight: 700; color: #6B7280; }
#empty { font-size: 13px; color: #9AA0AA; }

#status { font-size: 12px; color: #6B7280; }

QProgressBar { background: #DCE0E6; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #2F6FED; border-radius: 4px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #C3C8D0; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


class Worker(QObject):
    status = Signal(str)
    progress = Signal(float)
    file_done = Signal(str, str)
    file_fail = Signal(str, str)
    finished = Signal(int, str)
    error = Signal(str)

    def __init__(self, files, scale, fmt, quality, face):
        super().__init__()
        self.files, self.scale = files, scale
        self.fmt, self.quality, self.face = fmt, quality, face

    @Slot()
    def run(self):
        try:
            self.status.emit("Загрузка модели…")
            from upscaler.engine import UpscaleEngine
            engine = UpscaleEngine(scale=self.scale, face_enhance=self.face, tile=512)
            self.status.emit(f"Модель загружена · {engine.device}")
            total = len(self.files)
            last_dir = None
            for i, f in enumerate(self.files):
                self.status.emit(f"Обработка: {Path(f).name}")
                out = make_output_path(Path(f), None, self.scale, self.fmt)
                last_dir = out.parent
                try:
                    ow, oh = engine.upscale(Path(f), out, quality=self.quality)
                    self.file_done.emit(str(f), f"✓ {ow}×{oh}")
                except Exception as e:
                    self.file_fail.emit(str(f), "✗ ошибка")
                    self.status.emit(f"Ошибка на {Path(f).name}: {e}")
                self.progress.emit((i + 1) / total)
            self.finished.emit(total, str(last_dir) if last_dir else "")
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")


def _rounded_pix(path: Path, size=44, radius=11) -> QPixmap | None:
    src = QPixmap(str(path))
    if src.isNull():
        return None
    src = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (src.width() - size) // 2
    y = (src.height() - size) // 2
    src = src.copy(x, y, size, size)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path_ = QPainterPath()
    path_.addRoundedRect(0, 0, size, size, radius, radius)
    p.setClipPath(path_)
    p.drawPixmap(0, 0, src)
    p.end()
    return out


def _shadow(widget, blur=22, dy=3, alpha=28):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(dy)
    eff.setColor(QColor(20, 30, 60, alpha))
    widget.setGraphicsEffect(eff)


class FileRow(QWidget):
    def __init__(self, path: Path, info: str):
        super().__init__()
        self.setObjectName("fileRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 14, 8)
        lay.setSpacing(12)
        thumb = QLabel()
        thumb.setFixedSize(44, 44)
        pm = _rounded_pix(path)
        if pm:
            thumb.setPixmap(pm)
        lay.addWidget(thumb)
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(path.name)
        name.setObjectName("fileName")
        dim = QLabel(info)
        dim.setObjectName("fileDim")
        col.addWidget(name)
        col.addWidget(dim)
        lay.addLayout(col, 1)
        self.status = QLabel("")
        self.status.setObjectName("fileStatus")
        lay.addWidget(self.status)

    def set_status(self, text, color):
        self.status.setText(text)
        self.status.setStyleSheet(f"font-size:12px; font-weight:700; color:{color};")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("window")
        self.setWindowTitle("Upscaler")
        self.resize(640, 820)
        self.setMinimumSize(600, 760)
        self.setAcceptDrops(True)

        self.files: list[Path] = []
        self.rows: dict[str, FileRow] = {}
        self.last_output_dir: Path | None = None
        self.processing = False
        self.thread = None
        self.worker = None

        self._build()
        self.setStyleSheet(STYLE)

    # ------------------------------------------------------------- UI
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(0)

        # заголовок
        top = QHBoxLayout()
        title = QLabel("Upscaler"); title.setObjectName("title")
        badge = QLabel("Real-ESRGAN"); badge.setObjectName("badge")
        top.addWidget(title); top.addStretch(1); badge.setAlignment(Qt.AlignVCenter)
        top.addWidget(badge)
        root.addLayout(top)
        sub = QLabel("Увеличение разрешения фото с восстановлением чёткости")
        sub.setObjectName("subtitle")
        root.addWidget(sub)
        root.addSpacing(16)

        # зона перетаскивания
        self.drop = QFrame(); self.drop.setObjectName("drop")
        self.drop.setFixedHeight(132)
        self.drop.setProperty("hover", "false")
        self.drop.mousePressEvent = lambda e: self._choose_files()
        self.drop.setCursor(Qt.PointingHandCursor)
        dl = QVBoxLayout(self.drop); dl.setAlignment(Qt.AlignCenter); dl.setSpacing(4)
        chip = QLabel("↑"); chip.setObjectName("dropChip"); chip.setAlignment(Qt.AlignCenter)
        dl.addWidget(chip, 0, Qt.AlignCenter)
        dt = QLabel("Перетащите фото или папку сюда"); dt.setObjectName("dropTitle")
        dt.setAlignment(Qt.AlignCenter); dl.addWidget(dt)
        ds = QLabel("или нажмите, чтобы выбрать"); ds.setObjectName("dropSub")
        ds.setAlignment(Qt.AlignCenter); dl.addWidget(ds)
        root.addWidget(self.drop)
        root.addSpacing(12)

        # кнопки выбора
        acts = QHBoxLayout()
        b1 = QPushButton("Выбрать файлы"); b1.setObjectName("secondary")
        b1.setCursor(Qt.PointingHandCursor); b1.clicked.connect(self._choose_files)
        b2 = QPushButton("Выбрать папку"); b2.setObjectName("secondary")
        b2.setCursor(Qt.PointingHandCursor); b2.clicked.connect(self._choose_folder)
        b3 = QPushButton("Очистить"); b3.setObjectName("ghost")
        b3.setCursor(Qt.PointingHandCursor); b3.clicked.connect(self._clear)
        acts.addWidget(b1); acts.addWidget(b2); acts.addStretch(1); acts.addWidget(b3)
        root.addLayout(acts)
        root.addSpacing(14)

        # настройки
        card = QFrame(); card.setObjectName("card")
        g = QGridLayout(card); g.setContentsMargins(16, 14, 16, 14)
        g.setHorizontalSpacing(12); g.setVerticalSpacing(12); g.setColumnStretch(1, 1)

        g.addWidget(self._rl("Увеличение"), 0, 0, Qt.AlignLeft)
        seg = QHBoxLayout(); seg.setSpacing(0)
        self.scale_group = QButtonGroup(self)
        for i, val in enumerate(("2x", "4x")):
            b = QPushButton(val); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("seg")
            b.setProperty("side", "L" if i == 0 else "R")
            self.scale_group.addButton(b, i)
            seg.addWidget(b)
            if val == "4x":
                b.setChecked(True)
        self.scale_group.buttonClicked.connect(lambda *_: self._render())
        segw = QWidget(); segw.setLayout(seg)
        g.addWidget(segw, 0, 1, Qt.AlignRight)

        g.addWidget(self._rl("Формат"), 1, 0, Qt.AlignLeft)
        self.format_cb = QComboBox(); self.format_cb.addItems(FORMATS)
        g.addWidget(self.format_cb, 1, 1, Qt.AlignRight)

        g.addWidget(self._rl("Качество"), 2, 0, Qt.AlignLeft)
        self.quality_cb = QComboBox(); self.quality_cb.addItems(QUALITIES)
        g.addWidget(self.quality_cb, 2, 1, Qt.AlignRight)

        g.addWidget(self._rl("Улучшать лица"), 3, 0, Qt.AlignLeft)
        self.face_cb = QCheckBox("GFPGAN")
        g.addWidget(self.face_cb, 3, 1, Qt.AlignRight)
        root.addWidget(card)
        root.addSpacing(14)

        # список файлов
        self.list = QListWidget(); self.list.setObjectName("list")
        self.list.setIconSize(QSize(40, 40))
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setFocusPolicy(Qt.NoFocus)
        root.addWidget(self.list, 1)
        root.addSpacing(14)

        # прогресс + статус
        self.pbar = QProgressBar(); self.pbar.setRange(0, 1000); self.pbar.setValue(0)
        self.pbar.setTextVisible(False)
        root.addWidget(self.pbar)
        root.addSpacing(6)
        self.status = QLabel("Готов к работе"); self.status.setObjectName("status")
        root.addWidget(self.status)
        root.addSpacing(12)

        # кнопки запуска
        self.run_btn = QPushButton("Увеличить"); self.run_btn.setObjectName("accent")
        self.run_btn.setCursor(Qt.PointingHandCursor); self.run_btn.clicked.connect(self._start)
        root.addWidget(self.run_btn)
        self.open_btn = QPushButton("Открыть папку с результатом")
        self.open_btn.setObjectName("secondary"); self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(self._open_output); self.open_btn.hide()
        root.addSpacing(8); root.addWidget(self.open_btn)

        _shadow(self.drop)
        _shadow(card)

        self._render()

    def _rl(self, text):
        lbl = QLabel(text); lbl.setObjectName("rowLabel"); return lbl

    # --------------------------------------------------------- drag&drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.drop.setProperty("hover", "true")
            self.drop.style().unpolish(self.drop); self.drop.style().polish(self.drop)

    def dragLeaveEvent(self, e):
        self.drop.setProperty("hover", "false")
        self.drop.style().unpolish(self.drop); self.drop.style().polish(self.drop)

    def dropEvent(self, e):
        self.drop.setProperty("hover", "false")
        self.drop.style().unpolish(self.drop); self.drop.style().polish(self.drop)
        if self.processing:
            return
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.toLocalFile()]
        if paths:
            self._add(paths)

    # ------------------------------------------------------------- файлы
    def _choose_files(self):
        if self.processing:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите изображения", "",
                                                f"Изображения ({' '.join(EXTS)})")
        if files:
            self._add([Path(p) for p in files])

    def _choose_folder(self):
        if self.processing:
            return
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с изображениями")
        if folder:
            self._add([Path(folder)])

    def _clear(self):
        if self.processing:
            return
        self.files = []
        self._render()

    def _add(self, paths):
        collected = []
        for p in paths:
            collected.extend(collect_images(p))
        seen = {str(f) for f in self.files}
        for f in collected:
            if str(f) not in seen:
                seen.add(str(f)); self.files.append(f)
        self._render()

    def _scale(self):
        return 2 if self.scale_group.checkedId() == 0 else 4

    def _render(self):
        self.list.clear()
        self.rows.clear()
        if not self.files:
            self.status.setText("Готов к работе")
            it = QListWidgetItem()
            it.setFlags(Qt.NoItemFlags)
            it.setSizeHint(QSize(0, 60))
            self.list.addItem(it)
            ph = QLabel("Файлы не выбраны"); ph.setObjectName("empty")
            ph.setAlignment(Qt.AlignCenter)
            self.list.setItemWidget(it, ph)
            return
        scale = self._scale()
        for f in self.files:
            try:
                w, h, _ = get_image_info(f)
                info = f"{w}×{h}  →  {w*scale}×{h*scale}"
            except Exception:
                info = "—"
            it = QListWidgetItem()
            it.setFlags(Qt.NoItemFlags)
            it.setSizeHint(QSize(0, 64))
            self.list.addItem(it)
            row = FileRow(f, info)
            self.list.setItemWidget(it, row)
            self.rows[str(f)] = row
        self.status.setText(f"Выбрано файлов: {len(self.files)}")

    # ------------------------------------------------------- обработка
    def _start(self):
        if self.processing:
            return
        if not self.files:
            self.status.setText("Сначала выберите изображения")
            return
        self.processing = True
        self.open_btn.hide()
        self.run_btn.setEnabled(False); self.run_btn.setText("Обработка…")
        self.pbar.setValue(0)

        self.thread = QThread()
        self.worker = Worker(list(map(str, self.files)), self._scale(),
                             FORMAT_MAP[self.format_cb.currentText()],
                             int(self.quality_cb.currentText().replace("%", "")),
                             self.face_cb.isChecked())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status.setText)
        self.worker.progress.connect(lambda v: self.pbar.setValue(int(v * 1000)))
        self.worker.file_done.connect(lambda k, t: self._mark(k, t, "#157F3B"))
        self.worker.file_fail.connect(lambda k, t: self._mark(k, t, "#CF222E"))
        self.worker.finished.connect(self._finished)
        self.worker.error.connect(self._error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.start()

    def _mark(self, key, text, color):
        row = self.rows.get(key)
        if row:
            row.set_status(text, color)

    def _finished(self, total, last_dir):
        self.processing = False
        self.run_btn.setEnabled(True); self.run_btn.setText("Увеличить")
        self.pbar.setValue(1000)
        self.status.setText(f"Готово! Обработано: {total}")
        if last_dir:
            self.last_output_dir = Path(last_dir)
            self.open_btn.show()

    def _error(self, msg):
        self.processing = False
        self.run_btn.setEnabled(True); self.run_btn.setText("Увеличить")
        self.status.setText(f"Ошибка: {msg.splitlines()[0]}")

    def _open_output(self):
        if self.last_output_dir and self.last_output_dir.exists():
            import subprocess
            subprocess.run(["open", str(self.last_output_dir)], check=False)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Upscaler")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
