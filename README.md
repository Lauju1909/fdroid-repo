# ♿ Laujus Barrierefreie Android-Apps – F-Droid Repository

Offizielles F-Droid Repository für alle barrierefreien Android-Apps von **Lauju1909**, optimiert für **TalkBack**, Screenreader und Menschen mit Sehbehinderung oder Blindheit.

---

## 📲 Zu F-Droid oder Neo Store auf dem Smartphone hinzufügen

### 1. F-Droid oder Neo Store herunterladen (einmalig)
Weder F-Droid noch Neo Store gibt es im Google Play Store (Google erlaubt dort keine alternativen App-Stores). Lade die kostenlose Original-App direkt über die offiziellen Links herunter:
- 📥 **[F-Droid direkt herunterladen (Offizielle APK)](https://f-droid.org/F-Droid.apk)** (Webseite: https://f-droid.org/de/)
- 📥 **[Neo Store herunterladen (Offizielle APK / GitHub)](https://github.com/NeoApplications/Neo-Store/releases/latest)**

### 2. 1-Klick-Installation (auf dem Smartphone öffnen)
Tippe auf folgenden Link, um das Repository mit nur einem Klick direkt in **F-Droid** oder **Neo Store** einzubinden:
👉 **[Mit 1 Klick in F-Droid / Neo Store hinzufügen](fdroidrepos://lauju1909.github.io/fdroid-repo/fdroid/repo?fingerprint=6CB811B89526A24CE7D41FB3FB4045B9FD0541D2017F96127CA4C407D43FCF0F)**

### 3. Kurze Schritt-für-Schritt-Anleitung
1. Lade **F-Droid** (oder **Neo Store**) über den Link oben herunter und installiere die APK (bei Nachfrage einmalig *„Aus dieser Quelle installieren“* erlauben).
2. Tippe anschließend auf den **1-Klick-Link** oben und bestätige mit **Hinzufügen** / **OK**.
3. Nach kurzer Synchronisation stehen alle barrierefreien Apps inklusive automatischer Updates direkt bereit!

---

### Manuelle Einrichtung in der F-Droid App
1. Öffne die **F-Droid App** (oder Neo Store) auf deinem Android-Gerät.
2. Gehe auf **Einstellungen** ➔ **Paketquellen** (Repositories).
3. Tippe auf das **+** (Neue Quelle hinzufügen).
4. Gib die folgende Adresse ein:
   ```text
   https://lauju1909.github.io/fdroid-repo/fdroid/repo
   ```
5. Gib den Fingerprint zur Verifizierung ein (optional, wird meist automatisch erkannt):
   ```text
   6C B8 11 B8 95 26 A2 4C E7 D4 1F B3 FB 40 45 B9 FD 05 41 D2 01 7F 96 12 7C A4 C4 07 D4 3F CF 0F
   ```
6. Tippe auf **Hinzufügen**. Nach der ersten Synchronisation stehen dir alle Apps und automatischen Updates zur Verfügung!

---

## 📦 Enthaltene Apps

| App | Paket-ID | Beschreibung |
| :--- | :--- | :--- |
| **Haushaltsbuch Barrierefrei** | `de.lauri.finanzapp` | Barrierefreies Haushaltsbuch mit TalkBack-Unterstützung, Beleg-Scanner und sicherem Offline-Tresor |
| **Audio Studio Tycoon** | `de.lauri.audiostudiotycoon` | Vollständig zugängliche Spieleentwickler-Simulation mit Sprachausgabe |
| **Barrierefreies WebUntis** | `de.lwl.stundenplan` | Barrierefreier Stundenplan für Schüler am LWL-Berufskolleg Soest |
| **Audio Mini Games** | `de.lauri.minigames` | Über 60 barrierefreie Minispiele, spielbar nach Gehör und Haptik |
| **Lernplattform Android** | `de.lauri.lernplatform` | Barrierefreie Lern- und Wissensplattform für Schule & Alltag |

---

## ⚙️ Wie dieses Repository funktioniert

1. **Automatischer Build & Signierung:** Eine GitHub Actions Workflow-Pipeline fragt regelmäßig die neuesten Releases der fünf App-Repositories ab.
2. **Offizielle Entwickler-Signatur:** Alle APKs werden mit dem offiziellen Release-Schlüssel von Lauju signiert (`apksigner`).
3. **F-Droid Katalog:** `fdroidserver` erstellt den signierten F-Droid Index (`index-v1.json`, `index.jar`).
4. **Hosting via GitHub Pages:** Der Katalog wird über GitHub Pages öffentlich und sicher bereitgestellt.

---

## 📜 Lizenz
Alle enthaltenen Anwendungen und Repository-Tools sind Open Source unter der **MIT-Lizenz**.
Copyright (c) 2026 Lauju1909.
