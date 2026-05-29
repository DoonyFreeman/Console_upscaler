#!/bin/bash
# Сборка Upscaler.app для macOS
set -e

CYAN='\033[0;36m'; GREEN='\033[0;32m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}Активация окружения...${NC}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo -e "${CYAN}Установка PyInstaller...${NC}"
pip install "pyinstaller>=6.0" --quiet

echo -e "${CYAN}Сборка приложения (это займёт несколько минут)...${NC}"
pyinstaller upscaler.spec --clean --noconfirm

echo ""
echo -e "${GREEN}Готово!${NC} Приложение: ${CYAN}dist/Upscaler.app${NC}"
echo ""
echo "Чтобы установить — перетащите dist/Upscaler.app в папку «Программы»."
echo "При первом запуске приложение скачает нейросетевые модели (~130 МБ)."
