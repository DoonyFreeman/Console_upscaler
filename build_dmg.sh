#!/bin/bash
# Упаковка Upscaler.app в DMG-установщик (перетащи в «Программы»)
set -e

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP="dist/Upscaler.app"
DMG="dist/Upscaler.dmg"
STAGE="dist/dmg_stage"

if [ ! -d "$APP" ]; then
    echo -e "${YELLOW}Сначала собери приложение: ./build.sh${NC}"
    exit 1
fi

echo -e "${CYAN}Подготовка содержимого DMG...${NC}"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

echo -e "${CYAN}Сборка DMG (сжатие может занять пару минут)...${NC}"
hdiutil create -volname "Upscaler" \
    -srcfolder "$STAGE" \
    -ov -format UDZO \
    "$DMG" >/dev/null

rm -rf "$STAGE"

SIZE=$(du -h "$DMG" | cut -f1)
echo ""
echo -e "${GREEN}Готово!${NC} Установщик: ${CYAN}$DMG${NC} ($SIZE)"
echo "Открой его двойным кликом и перетащи Upscaler в «Программы»."
