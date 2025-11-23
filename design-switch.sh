#!/bin/bash

FILE="guideos-gpu-vc.py"

# Zenity Auswahl
choice=$(zenity --list \
  --title="Design auswählen" \
  --text="Welches Design soll aktiviert werden?" \
  --column="Design" \
  "Hell" "Dunkel")

if [[ -z "$choice" ]]; then
    exit 0
fi

# Block Hell
read -r -d '' LIGHT_BLOCK << 'EOF'
# >>> DESIGN_START
# -------------------- Design / Farben --------------------
BG = "#d9d9d9"
FIELD = "#efefef"
FIELD2 = "#efefef"
FIELD3 = "#efefef"
TEXT = "#000000"
ACCENT = "#a0a0a0"
PROG = "#4b9e8c"
# >>> DESIGN_END
EOF

# Block Dunkel
read -r -d '' DARK_BLOCK << 'EOF'
# >>> DESIGN_START
# -------------------- Design / Farben --------------------
BG = "#1e1e1e"
FIELD = "#2a2a2a"
FIELD2 = "#3d3b3b"
FIELD3 = "#595959"
TEXT = "#ffffff"
ACCENT = "#3a3a3a"
PROG = "#4b9e8c"
# >>> DESIGN_END
EOF

# Wähle Block
if [[ "$choice" == "Hell" ]]; then
    NEW_BLOCK="$LIGHT_BLOCK"
else
    NEW_BLOCK="$DARK_BLOCK"
fi

# Datei Zeile für Zeile verarbeiten und Block ersetzen
awk -v newblock="$NEW_BLOCK" '
BEGIN {inside=0}
{
    if ($0 ~ /# >>> DESIGN_START/) {
        print newblock
        inside=1
        next
    }
    if ($0 ~ /# >>> DESIGN_END/) {
        inside=0
        next
    }
    if (!inside) print $0
}' "$FILE" > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"

zenity --info --text="Design erfolgreich auf '$choice' geändert!"
chmod +x "$FILE"
