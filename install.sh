#!/bin/bash

# =======================================================================
# Titel: install.sh
# Version: 1.1
# Autor: Nightworker
# Datum: 2025-11-17
# Beschreibung: Richtet ein virtuelles Python mit tkinterdnd2 ein.
# Shebang des Python-Skripts wird automatisch angepasst.
# Grafikdialogs via Zenity.
# Lizenz: MIT
# =======================================================================

# Zenity prüfen
if ! command -v zenity &> /dev/null; then
    echo "Zenity ist nicht installiert. Bitte installieren: sudo apt install zenity"
    exit 1
fi

FILE1="guideos-gpu-vc.py"
FILE2="guideos-gpu-vc-dark.py"
USER_NAME=$(whoami)
NEW_SHEBANG="#!/home/$USER_NAME/venv/bin/python3"
USER_HOME="$HOME"
VENV_PATH="$USER_HOME/venv"

# Auswahlmenü
CHOICE=$(zenity --list \
    --title="Dateiauswahl" \
    --text="Welche Datei soll geändert werden?" \
    --column="Option" --column="Beschreibung" \
    1 "Nur $FILE1 ändern" \
    2 "Nur $FILE2 ändern" \
    3 "Beide Dateien ändern" \
)

# Abbruch prüfen
if [ -z "$CHOICE" ]; then
    exit 0
fi

check_and_modify() {
    local FILE="$1"

    # Datei prüfen
    if [ ! -f "$FILE" ]; then
        zenity --error --title="Fehler" --text="Die Datei '$FILE' wurde nicht gefunden!"
        return
    fi

    # Shebang ersetzen
    sed -i "1s|^#!.*|$NEW_SHEBANG|" "$FILE"

    zenity --info --title="Erfolg" --text="Die Datei '$FILE' wurde erfolgreich aktualisiert!"
}

case "$CHOICE" in
    1)
        check_and_modify "$FILE1"
        ;;
    2)
        check_and_modify "$FILE2"
        ;;
    3)
        check_and_modify "$FILE1"
        check_and_modify "$FILE2"
        ;;
esac


###############################################################################
# Passwort abfragen
###############################################################################
PASS=$(zenity --password --title="Root-Passwort benötigt")

if [ $? -ne 0 ]; then
    zenity --error --title="Abgebrochen" --text="Installation wurde abgebrochen."
    exit 1
fi

# Funktion: sudo mit Passwort ausführen
runsudo() {
    echo "$PASS" | sudo -S "$@" 2>/dev/null
}

###############################################################################
# Fortschrittsfenster starten
###############################################################################
(
echo "5"; sleep 0.2
echo "# Ersetze Shebang..."

# --------------------------------------------------------------------------
# Shebang ersetzen oder einfügen
# --------------------------------------------------------------------------
if head -n 1 "$FILE" | grep -q "^#!"; then
    sed -i "1s|.*|$NEW_SHEBANG|" "$FILE"
else
    sed -i "1i $NEW_SHEBANG" "$FILE"
fi

echo "20"; sleep 0.2
echo "# Aktualisiere Paketliste..."

runsudo apt update -y

echo "40"; sleep 0.2
echo "# Installiere benötigte Python-Pakete..."

runsudo apt install -y python3-venv python3-tk python3-pip

echo "55"; sleep 0.2
echo "# Erstelle virtuelle Umgebung..."

python3 -m venv "$VENV_PATH"

echo "70"; sleep 0.2
echo "# Aktiviere virtuelle Umgebung & installiere tkinterdnd2..."

source "$VENV_PATH/bin/activate"
pip install --upgrade pip
pip install tkinterdnd2
deactivate

echo "85"; sleep 0.2
echo "# Entferne temporäre Systempakete..."

runsudo apt remove -y python3-venv python3-pip

echo "100"; sleep 0.2
) | zenity --progress \
    --title="GuideOS – Installation läuft" \
    --text="Starte Installation..." \
    --percentage=0 --width=500 --auto-close

# Wenn Fortschrittsdialog abgebrochen wurde
if [ $? -ne 0 ]; then
    zenity --error --text="Installation abgebrochen."
    exit 1
fi

###############################################################################
# Fertigmeldung
###############################################################################
zenity --info --title="Fertig!" --text="\
Die virtuelle Python-Umgebung wurde erfolgreich eingerichtet.

Pfad: $VENV_PATH

Der Shebang in '$FILE' wurde aktualisiert"

