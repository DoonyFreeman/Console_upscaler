#!/bin/bash
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Upscaler — Photo Enhancer      ║${NC}"
echo -e "${CYAN}║   Real-ESRGAN + GFPGAN           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════╝${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

PYTHON=""
for candidate in \
    "$HOME/.pyenv/versions/3.11.*/bin/python3" \
    "$HOME/.pyenv/versions/3.12.*/bin/python3" \
    "$HOME/.pyenv/versions/3.10.*/bin/python3" \
    "$(command -v python3.11 2>/dev/null)" \
    "$(command -v python3.12 2>/dev/null)" \
    "$(command -v python3.10 2>/dev/null)" \
    "$(command -v python3 2>/dev/null)"; do
    # expand glob
    for p in $candidate; do
        if [ -x "$p" ] 2>/dev/null; then
            PY_VER=$("$p" -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>/dev/null)
            PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [ "$PY_MAJOR" = "3" ] && [ "$PY_MINOR" -ge 10 ] && [ "$PY_MINOR" -le 12 ]; then
                PYTHON="$p"
                break 2
            fi
        fi
    done
done

if [ -z "$PYTHON" ]; then
    echo -e "${YELLOW}Python 3.10-3.12 required (3.13+ not supported by Real-ESRGAN).${NC}"
    echo -e "${YELLOW}Install via: pyenv install 3.11.9 or brew install python@3.11${NC}"
    exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}Using Python ${PY_VERSION} (${PYTHON})${NC}"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${CYAN}Creating virtual environment...${NC}"
    "$PYTHON" -m venv "$VENV_DIR"
fi

echo -e "${CYAN}Activating environment...${NC}"
source "$VENV_DIR/bin/activate"

echo -e "${CYAN}Upgrading pip...${NC}"
pip install --upgrade pip --quiet

echo -e "${CYAN}Installing PyTorch (MPS-optimized for Apple Silicon)...${NC}"
pip install torch torchvision --quiet

echo -e "${CYAN}Installing Real-ESRGAN and dependencies...${NC}"
pip install basicsr realesrgan gfpgan click rich opencv-python-headless Pillow --quiet

echo -e "${CYAN}Installing GUI toolkit (PySide6)...${NC}"
pip install "PySide6>=6.6" --quiet

echo -e "${CYAN}Installing upscaler...${NC}"
pip install -e "$SCRIPT_DIR" --quiet

echo ""
echo -e "${GREEN}══════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}══════════════════════════════════${NC}"
echo ""
echo -e "Activate the environment first:"
echo -e "  ${CYAN}source $VENV_DIR/bin/activate${NC}"
echo ""
echo -e "Запустить приложение (GUI):"
echo -e "  ${CYAN}upscaler-gui${NC}                   # окно с drag-and-drop"
echo -e "Собрать .app для macOS:"
echo -e "  ${CYAN}./build.sh${NC}                     # → dist/Upscaler.app"
echo ""
echo -e "Или через командную строку:"
echo -e "  ${CYAN}upscale photo.jpg${NC}              # 4x upscale"
echo -e "  ${CYAN}upscale photo.jpg -s 2${NC}         # 2x upscale"
echo -e "  ${CYAN}upscale photo.jpg --face${NC}       # with face enhancement"
echo -e "  ${CYAN}upscale ./photos/${NC}              # batch processing"
echo -e "  ${CYAN}upscale --help${NC}                 # all options"
echo ""
