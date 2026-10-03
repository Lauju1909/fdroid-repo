# ♿ Laujus Barrierefreie Android-Apps – F-Droid Repository

Offizielles F-Droid Repository für alle barrierefreien Android-Apps von **Lauju1909**, optimiert für **TalkBack**, Screenreader und Menschen mit Sehbehinderung oder Blindheit.

---

## 📲 Zu F-Droid auf dem Smartphone hinzufügen

### 1-Klick-Installation (auf dem Smartphone öffnen)
Tippe auf folgenden Link, um das Repository direkt in F-Droid oder Neo Store einzubinden:
👉 **[In F-Droid hinzufügen](fdroidrepos://lauju1909.github.io/fdroid-repo/fdroid/repo?fingerprint=6CB811B89526A24CE7D41FB3FB4045B9FD0541D2017F96127CA4C407D43FCF0F)**

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
| **TalkBack Deutsch-Übersetzer** | `com.talkback.translator` | Barrierefreie Begleit-App, die englische Apps live auf Deutsch vorliest |

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
