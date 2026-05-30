# 🔍 Upscaler

[English](README.md) | **Русский**

> Нативное приложение для macOS, которое увеличивает разрешение фотографий и восстанавливает чёткость с помощью нейросети Real-ESRGAN. HD → 4K без подписок и без облака — всё локально, на вашем железе.

[![Latest release](https://img.shields.io/github/v/release/DoonyFreeman/Console_upscaler?logo=github)](https://github.com/DoonyFreeman/Console_upscaler/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/DoonyFreeman/Console_upscaler/total?logo=github&label=downloads)](https://github.com/DoonyFreeman/Console_upscaler/releases)
[![Python](https://img.shields.io/badge/python-3.10--3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/macOS-Apple%20Silicon-black?logo=apple)](https://developer.apple.com/metal/pytorch/)
[![UI](https://img.shields.io/badge/UI-PySide6%20(Qt)-41cd52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

<p align="center">
  <img src="docs/images/app_main.png" alt="Окно приложения Upscaler" width="420">
</p>

Перетащите фото в окно, выберите увеличение (2x или 4x) — и приложение прогонит его через [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN), восстанавливая детали и резкость. Портреты можно дополнительно докрутить через [GFPGAN](https://github.com/TencentARC/GFPGAN). Есть и графический интерфейс, и CLI.

---

## ✨ Возможности

- 🖥 **Нативное приложение для macOS** — скачал `.dmg`, перетащил в «Программы», пользуешься
- 🖱 **Drag-and-drop** — перетаскивайте фото и папки прямо в окно
- 🖼 **2x / 4x увеличение** на Real-ESRGAN (`x2plus` / `x4plus`)
- 👤 **Восстановление лиц** через GFPGAN (галочка в настройках)
- 📁 **Пакетная обработка** — целая папка за раз
- 🍎 **Apple Silicon MPS** из коробки (Metal-ускорение)
- 🎨 Форматы на выходе — **JPG / PNG / WebP** + настройка качества
- ⌨️ **CLI в комплекте** — для скриптов и автоматизации

---

## 🖼 До и после

| До | После (4x) |
|:---:|:---:|
| <img src="docs/images/before.jpg" width="360"> | <img src="docs/images/after.jpg" width="360"> |
| 720×480 | 2880×1920 |

| Портрет до | Портрет после (с GFPGAN) |
|:---:|:---:|
| <img src="docs/images/portrait_before.jpg" width="280"> | <img src="docs/images/portrait_after.jpg" width="280"> |

---

## 📥 Установка

### Требования

- Mac на **Apple Silicon** (M1/M2/M3/M4)
- **macOS 12** или новее
- Интернет при **первом** запуске (скачать модели ~130 МБ)

### Вариант 1. Скачать готовое приложение (проще всего)

1. Зайди на страницу [**Releases**](https://github.com/DoonyFreeman/Console_upscaler/releases/latest) и скачай **`Upscaler.dmg`**.
2. Открой `Upscaler.dmg` двойным кликом.
3. **Перетащи `Upscaler` в папку «Программы»** (Applications).
4. **Первый запуск:** в «Программах» сделай **правый клик** по `Upscaler` → **«Открыть»** → ещё раз **«Открыть»**.

> ⚠️ Шаг 4 нужен только **один раз**. Приложение не подписано платным сертификатом Apple, поэтому при обычном двойном клике macOS показывает предупреждение. Через правый клик → «Открыть» система запомнит разрешение.
>
> Если пишет «повреждено», выполни один раз в Терминале:
> ```bash
> xattr -dr com.apple.quarantine /Applications/Upscaler.app
> ```

### Вариант 2. Собрать из исходников

```bash
git clone https://github.com/DoonyFreeman/Console_upscaler.git
cd Console_upscaler
./install.sh        # окружение и зависимости (Python 3.10–3.12)
./build.sh          # собирает dist/Upscaler.app
./build_dmg.sh      # (опц.) упаковывает в dist/Upscaler.dmg
```

> ⚠️ Нужен Python **3.10–3.12** (3.13+ пока не поддерживается из-за старого `basicsr`).

---

## 🚀 Использование

### Приложение (GUI)

1. Перетащи фото или папку в окно (или нажми «Выбрать файлы / папку»).
2. Настрой увеличение, формат, качество, при необходимости включи «Улучшать лица».
3. Нажми **«Увеличить»**.
4. По готовности — **«Открыть папку с результатом»**.

Результаты сохраняются рядом с оригиналом с суффиксом `_4x` / `_2x`.

| Выбор файлов | Обработка завершена |
|:---:|:---:|
| <img src="docs/images/app_main.png" width="340"> | <img src="docs/images/app_done.png" width="340"> |

### Командная строка (CLI)

```bash
upscale photo.jpg                    # 4x по умолчанию → photo_4x.jpg
upscale photo.jpg -s 2               # 2x — быстрее
upscale photo.jpg -o result.png      # явный путь вывода
upscale ./photos/                    # пакетно по всей папке
upscale photo.jpg --face             # с восстановлением лица (GFPGAN)
upscale photo.jpg --format webp --quality 90
upscale photo.jpg --tile 256         # меньше тайл — меньше памяти
upscale                              # интерактивный визард
```

| Флаг | По умолчанию | Что делает |
|---|---|---|
| `-s`, `--scale` | `4` | Кратность: `2` или `4` |
| `-o`, `--output` | рядом с оригиналом | Путь к файлу или папке |
| `--face` | выкл. | Включить GFPGAN для лиц |
| `--format` | как у исходника | `jpg` / `png` / `webp` |
| `--quality` | `95` | Качество JPEG/WebP, 1–100 |
| `--tile` | `512` | Размер тайла; меньше = меньше памяти |

Поддерживаемые форматы на вход: `jpg`, `jpeg`, `png`, `webp`, `tiff`, `tif`, `bmp`.

---

## 🧠 Как это работает

Под капотом две нейросети:

1. **Real-ESRGAN** (RRDBNet) — основной апскейлер. Для 4x используется `RealESRGAN_x4plus`, для 2x — `RealESRGAN_x2plus`. Картинка режется на тайлы (по умолчанию 512 px, чтобы хватало памяти), каждый прогоняется через сеть и склеивается обратно.
2. **GFPGAN v1.3** — включается галочкой «Улучшать лица». Реконструирует именно лица: глаза, рот, кожу. Полезно для старых и групповых фото.

Устройство выбирается автоматически: **MPS** (Metal) на Apple Silicon → **CUDA** → **CPU**. Веса моделей качаются с официальных релизов при первом запуске в `~/.upscaler/models/`.

---

## 🛠 Стек

Python · PyTorch (MPS) · Real-ESRGAN · GFPGAN · **PySide6 (Qt)** для GUI · Click + Rich для CLI · Pillow · OpenCV · PyInstaller для сборки `.app`

```
upscaler/
├── gui.py        # Графический интерфейс на PySide6 (drag-and-drop, миниатюры)
├── app.py        # Точка входа GUI
├── cli.py        # CLI на Click (флаги, пакетная обработка)
├── interactive.py# Интерактивный визард на Rich
├── engine.py     # Обёртка над Real-ESRGAN + GFPGAN, выбор устройства
└── utils.py      # collect_images, make_output_path, get_image_info
install.sh        # Установка окружения
build.sh          # Сборка Upscaler.app (PyInstaller)
build_dmg.sh      # Упаковка в DMG
upscaler.spec     # Конфиг PyInstaller
```

---

## 🐛 FAQ

<details>
<summary><b>«Не удаётся открыть, разработчик не проверен»</b></summary>

Приложение не подписано сертификатом Apple ($99/год). Сделай правый клик по приложению → «Открыть» → ещё раз «Открыть». Нужно один раз. Либо: `xattr -dr com.apple.quarantine /Applications/Upscaler.app`.
</details>

<details>
<summary><b>Можно ли отправить другу?</b></summary>

Да, если у друга **Apple Silicon Mac**. Отправь ему `.dmg` (или ссылку на Releases). Первый запуск — через правый клик → «Открыть». На Intel-Маках текущая сборка не работает (нужна отдельная universal-сборка).
</details>

<details>
<summary><b>Падает с нехваткой памяти / зависает</b></summary>

В CLI уменьши тайл: `upscale photo.jpg --tile 256` (или 128 для очень больших фото).
</details>

<details>
<summary><b>Медленно работает</b></summary>

Проверь, что используется `mps` (Apple Silicon), а не `cpu`. На M-чипах MPS подхватывается сам, если PyTorch свежий.
</details>

<details>
<summary><b>Где модели? Как перекачать?</b></summary>

`~/.upscaler/models/`. Удали файл — он перекачается при следующем запуске.
</details>

<details>
<summary><b>install.sh ругается на Python 3.13</b></summary>

Real-ESRGAN тянет старый `basicsr`, несовместимый с 3.13. Поставь 3.11: `pyenv install 3.11.9` или `brew install python@3.11`, затем снова `./install.sh`.
</details>

---

## 🙏 Благодарности

- [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — модель и архитектура
- [TencentARC/GFPGAN](https://github.com/TencentARC/GFPGAN) — восстановление лиц
- Команде PyTorch — за MPS-бэкенд
- [Qt for Python (PySide6)](https://doc.qt.io/qtforpython/) — за надёжный GUI на macOS

---

## 📄 Лицензия

[MIT](LICENSE). Не забудьте про лицензии моделей: Real-ESRGAN — BSD 3-Clause, GFPGAN — Apache 2.0.
