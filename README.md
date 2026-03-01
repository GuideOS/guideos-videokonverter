Diese Version enthält:

Die Konvertierung mit ffmpeg und der Hardwareunterstützung für Grafikkarten.
Für eine einwandfreie Funktion muss ein aktueller Treiber installiert sein.

✅ Unterstützung: NVIDIA (NVENC); AMD (AMF/VAAPI); Intel (VAAPI); CPU (Software)\
✅ Der Audio-Codec im Videofile kann geändert werden: PCM 16bit, AAC, Flac\
✅ Konvertierung des Video-Files in h.264, h.265 oder AV1\
✅ Auswahl der Qualitätsstufe\
✅ Auswahl der Bitrate\
✅ Vorgabe der Ausgabegröße\
✅ Skalierung auf 720p, 1080p, 1440p und 2160p durch ffmpeg mit Lanczos\
✅ Fortschrittsfenster\
✅ Abbruch möglich\
***
### Funktionsübersicht
Die Software bietet umfangreiche Funktionen zur Video- und Audiokonvertierung unter Nutzung moderner Hard- und Software-Enkoder.

### Enkoder-Unterstützung
Für die Videokodierung stehen folgende Encoder zur Verfügung:\
    • NVIDIA: Hardwarebeschleunigung über NVENC\
    • AMD: Hardwarebeschleunigung über AMF bzw. VAAPI\
    • Intel: Hardwarebeschleunigung über VAAPI\
    • CPU: Softwarebasierte Kodierung ohne Hardwarebeschleunigung

Die Auswahl des Encoders erfolgt abhängig von der verfügbaren Hardware des Systems.

### Videoformate
Das Quellvideo kann in eines der folgenden Zielformate konvertiert werden:\
    • H.264 (AVC)\
    • H.265 (HEVC)\
    • AV1

### Audioeinstellungen
Der im Videofile enthaltene Audio-Codec kann unabhängig vom Videoformat\
geändert werden. Zusätzlich lässt sich auch nur der Audio-Codec ändern, wobei\
das Videoformat  nicht verändert wird.

Unterstützt werden:\
    • PCM (16 Bit)\
    • AAC\
    • FLAC (16 Bit)

### Qualität und Bitrate
Die Software ermöglicht:\
    • die Auswahl einer vordefinierten Qualitätsstufe\
    • die manuelle Einstellung der Zielbitrate\
    • die gewünschte Ausgabegröße

Diese Parameter beeinflussen die resultierende Dateigröße und Bildqualität.
### Auflösung und Skalierung
Es stehen folgende vordefinierte Zielauflösungen zur Verfügung:\
    • 1280 × 720   (720p)\
    • 1920 × 1080 (1080p)\
    • 2560 × 1440 (1440p)\
    • 3840 × 2160 (2160p)

Die Skalierung erfolgt mittels FFmpeg unter Verwendung des Lanczos-Filters,\
um eine hochwertige Bildskalierung zu gewährleisten.
### Prozesssteuerung
Während der Konvertierung wird der aktuelle Fortschritt in einem separaten\
Fortschrittsfenster angezeigt, der Konvertierungsvorgang kann jederzeit durch\
den Benutzer abgebrochen werden.

## 🔧 Installation

### Build from DEB Package:

```bash
# Clone repository
git clone https://github.com/GuideOS/guideos-videokonverter.git
cd guideos-videokonverter

# Create DEB package
dpkg-buildpackage -us -uc

# Install (as root)
sudo dpkg -i ./guideos-videokonverter_1.0.3_all.deb

```
