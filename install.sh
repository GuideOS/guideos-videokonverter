#!/bin/bash

# =======================================================================
# Titel: install.sh
# Version: 1.3
# Autor: Nightworker
# Datum: 2025-12-13
# Beschreibung: Richtet ein virtuelles Python mit tkinterdnd2 ein.
# Shebang des Python-Skripts wird automatisch angepasst.
# Fügt Dateien in Systemverzeichnisse ein und erstellt einen Desktop-Starter.
# Grafikdialogs via Zenity.
# Lizenz: MIT
# =======================================================================

# Zenity prüfen
if ! command -v zenity &> /dev/null; then
    echo "Zenity ist nicht installiert. Bitte installieren: sudo apt install zenity"
    exit 1
fi

FILE="guideos-gpu-vc.py"
ICON_FILE="guideos-gpu-vc.png"
DESKTOP_FILE_NAME="GuideOS Videokonverter.desktop"
USER_NAME=$(whoami)
NEW_SHEBANG="#!/home/$USER_NAME/venv/bin/python3"
USER_HOME="$HOME"
VENV_PATH="$USER_HOME/venv"

# Überprüfung der benötigten Dateien
if [ ! -f "$FILE" ]; then
    zenity --error --title="Fehler" --text="Die Python-Skript-Datei '$FILE' wurde nicht gefunden!"
    exit 1
fi

if [ ! -f "$ICON_FILE" ]; then
    zenity --warning --title="Warnung" --text="Die Icon-Datei '$ICON_FILE' wurde nicht gefunden! Der Desktop-Starter wird erstellt, aber das Icon fehlt möglicherweise."
fi

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
# Ich gehe davon aus, dass die Datei, die kopiert werden soll, guideos-gpu-vc.py ist,
# basierend auf dem 'Exec' Eintrag im Desktop-Skript. Ich nutze hier '$FILE'.
if head -n 1 "$FILE" | grep -q "^#!"; then
    sed -i "1s|.*|$NEW_SHEBANG|" "$FILE"
else
    sed -i "1i $NEW_SHEBANG" "$FILE"
fi

echo "15"; sleep 0.2 # Prozentwerte angepasst
echo "# Aktualisiere Paketliste..."

runsudo apt update -y

echo "25"; sleep 0.2
echo "# Installiere benötigte Python-Pakete..."

runsudo apt install -y python3-venv python3-tk python3-pip

echo "35"; sleep 0.2
echo "# Erstelle virtuelle Umgebung..."

python3 -m venv "$VENV_PATH"

echo "45"; sleep 0.2
echo "# Aktiviere virtuelle Umgebung & installiere Bibliotheken..."

source "$VENV_PATH/bin/activate"
pip install --upgrade pip
pip install tkinterdnd2 customtkinter
deactivate

echo "55"; sleep 0.2
echo "# Kopiere Programm- und Icon-Dateien..."

# --------------------------------------------------------------------------
# Dateien kopieren (NEU)
# --------------------------------------------------------------------------
# guideos-gpu-vc.py nach /usr/bin/
runsudo install -m 755 "$FILE" "/usr/bin/$FILE"

# guideos-gpu-vc.png nach /usr/share/icons/ (falls vorhanden)
if [ -f "$ICON_FILE" ]; then
    runsudo install -m 644 "$ICON_FILE" "/usr/share/icons/$ICON_FILE"
fi

echo "70"; sleep 0.2
echo "# Erstelle und installiere Desktop-Starter..."

# --------------------------------------------------------------------------
# Desktop-Datei erstellen (NEU)
# --------------------------------------------------------------------------
DESKTOP_CONTENT="[Desktop Entry]
Version=1.9
Name=GuideOS Videokonverter
Comment=Video conversion tool for GuideOS
Name[de]=GuideOS Videokonverter
Comment[de]=Videokonvertierungstool für GuideOS
Exec=$FILE
Icon=$ICON_FILE
Terminal=false
Type=Application
Categories=GuideOS;
StartupNotify=true"

# Temporäre Datei erstellen
echo "$DESKTOP_CONTENT" > /tmp/"$DESKTOP_FILE_NAME"

# Kopieren und ausführbar machen (install -m 644 ist oft ausreichend für .desktop, aber 755 schadet nicht)
runsudo install -m 755 /tmp/"$DESKTOP_FILE_NAME" "/usr/share/applications/$DESKTOP_FILE_NAME"

# Temporäre Datei löschen
rm /tmp/"$DESKTOP_FILE_NAME"

echo "85"; sleep 0.2
echo "# Entferne temporäre Systempakete..."

runsudo apt remove -y python3-venv python3-pip

echo "100"; sleep 0.2
) | zenity --progress \
    --title="Installation läuft" \
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
Die Installation des GuideOS Videokonverters ist abgeschlossen.

* Virtuelle Python-Umgebung: $VENV_PATH
* Skript kopiert nach: /usr/bin/$FILE
* Desktop-Starter erstellt: /usr/share/applications/$DESKTOP_FILE_NAME

Sie können das Programm jetzt über das Anwendungsmenü starten."

# Die Datei muss nicht mehr hier ausführbar gemacht werden,
# da sie nach /usr/bin kopiert wurde, und der Shebang auf
# die virtuelle Umgebung verweist, was korrekt ist.
# chmod +x "$FILE"
