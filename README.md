## Guideos-Videokonverter
ist ein auf Linux ausgerichtetes Video-Verarbeitungstool, das dem Benutzer das Konvertieren von Video-Clips in andere Formate erleichtert. Es dient ferner der kompakten Speicherung großer Clips in platzsparenden Formaten und unterstützt jeweils den umgekehrten Prozess. Zur Beschleunigung der Arbeitsabläufe wird, sofern verfügbar, die vorhandene Hardware so weit wie möglich genutzt. Unterstützte Codecs sind H.264, H.265 und AV1. Die Konvertierung in AV1 bildet einen Sonderfall, da ältere Hardware diesen Codec möglicherweise nicht unterstützt. Falls keine Hardware-Unterstützung vorhanden ist, wird eine entsprechende Fehlermeldung ausgegeben; in diesem Fall ist jedoch eine Software-basierte Konvertierung weiterhin möglich.

<div style="display:flex; gap:10px;">
  <img src="screenshot/hochkant-preview.webp" width="270" height="183">
  <img src="screenshot/querformat-preview.webp" width="270" height="183">
  <img src="screenshot/schnittbereich-preview.webp" width="270" height="183">
</div>

### Für eine einwandfreie Funktion muss ein aktueller Treiber und python3 installiert sein.

✅ Unterstützung: NVIDIA (NVENC); AMD (AMF/VAAPI); Intel (VAAPI); CPU (Software)\
✅ Der Audio-Codec im Videofile kann geändert werden: PCM 16bit, AAC, Flac\
✅ Der Audio-Codec im Videofile kann kopiert werden, praktisch z.B. 5.1 Audio\
✅ Konvertierung des Video-Files in h.264, h.265 oder AV1\
✅ Qualitätssteuerung: Auswahl nach CRF (Qualitätsstufe), fester Bitrate oder Ziel-Dateigröße (MB)\
✅ Skalierung: Hochwertiges Upscaling (720p bis 4K) via FFmpeg (Lanczos-Filter)\
✅ Batch-Verarbeitung: Unterstützung für Drag & Drop und gleichzeitige Auswahl mehrerer Dateien\
✅ Schnittfunktion: Visuelle Festlegung von Startzeit und Dauer über ein Vorschau-Modul\
✅ Prozesskontrolle: Echtzeit-Log-Fenster, Fortschrittsbalken und Abbruchfunktion\
***
### Funktionsübersicht

#### 🚀 Enkoder-Unterstützung
* **NVIDIA**: Hardwarebeschleunigung über NVENC
* **AMD**: Hardwarebeschleunigung über VAAPI / AMF
* **Intel**: Hardwarebeschleunigung über VAAPI / QuickSync
* **CPU**: Softwarebasierte Kodierung (Fallback bei inkompatiblen Clipsegmenten)
* 

#### 📽 Videoformate & Codecs
* **Container**: MP4 (`.mp4`), Matroska (`.mkv`), WebM (`.webm`)
* **Video-Codecs**: H.264 (AVC), H.265 (HEVC), VP9, AV1 oder Modus *"Nur Audio"*
* **Farbtiefe**: 8-Bit (Standard) & 10-Bit (HDR/High Quality)
* **Smartphone-Rotation**: Automatische Beibehaltung von 9:16 Flags gegen ungewollte Verzerrungen

#### 🎵 Audioeinstellungen
* **Stream Copy (Audio-Copy)** 🆕: Übernahme der Audiospur ohne Neukodierung (spart Zeit und erhält 5.1/7.1 Sound 1:1)
* **Audio-Codecs**: AAC, Opus (Standard für WebM), FLAC (Lossless) und PCM (16-Bit)
* **Lautstärke-Normalisierung** 🆕: Integrierte EBU R128 Loudness-Normalisierung (-30 bis -5 LUFS, ideal für Web & TV)

#### 🎚 Qualität & Bitrate
* **CQ / CRF**: Qualitätsbasierte Kodierung mit konfigurierbaren Werten
* **Bitrate**: Manuelle Festlegung der Zielbitrate in kbit/s
* **Zieldateigröße**: Automatische Bitratenberechnung basierend auf einer gewünschten Ziel-Megabyte-Zahl

#### 📐 Auflösung, Skalierung & Schärfe
* **Auflösungen**: Original, 720p (HD), 1080p (Full HD), 1440p (2K), 2160p (4K)
* **Skalierung**: FFmpeg Lanczos-Filter für maximale Schärfe beim Up-/Downscaling
* **Unsharp-Filter** 🆕: Integrierter Nachschärfefilter (*Leicht*, *Mittel*, *Stark*) zur Optimierung skalierten Bildmaterials

---

### 🔍 Modul: Video-Vorschau & Schnittbereich (video_preview.py)
<div style="display:flex; gap:10px;">
  <img src="screenshot/schnittbereich-preview.webp" width="270" height="183">
</div>

**Kernfunktionen:**
* **Visuelles Scrubbing**: Flüssiges Spulen und Ansteuern genauer Videopositionen per PyQt6-Slider.
* **In/Out-Point Definition**: Start- und Endpunkte können direkt in der Vorschau gesetzt werden. Die resultierende Dauer wird automatisch berechnet und ins Hauptfenster übernommen.
* **Ressourceneffizienz**: Multithreaded Frame-Extraktion verhindert ein Einfrieren der Benutzeroberfläche (GUI-Lag) beim schnellen Suchen.

---
## 🔧 Installation

### 1. Die fertige guideos-videokonverter.deb hier herunterladen
### 2. Als DEB-Paket bauen und installieren:

Erstelle ein beliebiges Verzeichnis, öffne darin das Terminal und führe folgende Schritte aus: 

```bash
# Repository klonen
git clone [https://github.com/GuideOS/guideos-videokonverter.git](https://github.com/GuideOS/guideos-videokonverter.git)
cd guideos-videokonverter

# DEB-Paket bauen
dpkg-buildpackage -us -uc

# Paket installieren
sudo dpkg -i ../guideos-videokonverter_*.deb
sudo apt-get install -f  # Fehlende Abhängigkeiten automatisch auflösen
