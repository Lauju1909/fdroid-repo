#!/usr/bin/env python3
import os
import sys
import json
import base64
import shutil
import urllib.request
import subprocess
from pathlib import Path

APPS = [
    {
        "repo": "Lauju1909/BarrierefreieFinanzApp-Android",
        "name": "Haushaltsbuch Barrierefrei",
        "id": "de.lauri.finanzapp",
        "icon": "https://raw.githubusercontent.com/Lauju1909/BarrierefreieFinanzApp-Android/main/fastlane/metadata/android/de-DE/images/icon.png",
        "desc": "Barrierefreies Haushaltsbuch mit TalkBack-Unterstützung und sicherem Offline-Tresor"
    },
    {
        "repo": "Lauju1909/Audio-Studio-Tycoon-Android",
        "name": "Audio Studio Tycoon",
        "id": "de.lauri.audiostudiotycoon",
        "icon": "https://raw.githubusercontent.com/Lauju1909/Audio-Studio-Tycoon-Android/main/fastlane/metadata/android/de-DE/images/icon.png",
        "desc": "Tiefe Spieleentwickler-Simulation für blinde und sehbehinderte Spieler (TalkBack-optimiert)"
    },
    {
        "repo": "Lauju1909/BarrierefreierStundenplanLWL-Android",
        "name": "Barrierefreies WebUntis",
        "id": "de.lwl.stundenplan",
        "icon": "https://raw.githubusercontent.com/Lauju1909/BarrierefreierStundenplanLWL-Android/main/fastlane/metadata/android/de-DE/images/icon.png",
        "desc": "Barrierefreier Stundenplan für WebUntis am LWL-Berufskolleg Soest"
    },
    {
        "repo": "Lauju1909/Mini_Game_Sammlung_Android",
        "name": "Audio Mini Games",
        "id": "de.lauri.minigames",
        "icon": "https://raw.githubusercontent.com/Lauju1909/Mini_Game_Sammlung_Android/main/fastlane/metadata/android/de-DE/images/icon.png",
        "desc": "Über 60 barrierefreie Audio-Minispiele spielbar nach Gehör und Vibration"
    },
    {
        "repo": "Lauju1909/TalkBack-Deutsch-Uebersetzer-Android",
        "name": "TalkBack Deutsch-Übersetzer",
        "id": "com.talkback.translator",
        "icon": "https://raw.githubusercontent.com/Lauju1909/TalkBack-Deutsch-Uebersetzer-Android/main/fastlane/metadata/android/de-DE/images/icon.png",
        "desc": "Barrierefreie Begleit-App für TalkBack – übersetzt Bildschirminhalte live ins Deutsche"
    }
]

ROOT_DIR = Path(__file__).resolve().parent.parent
FDROID_DIR = ROOT_DIR / "fdroid"
REPO_DIR = FDROID_DIR / "repo"
SITE_DIR = ROOT_DIR / "_site"
ICONS_DIR = REPO_DIR / "icons"

FINGERPRINT = "6CB811B89526A24CE7D41FB3FB4045B9FD0541D2017F96127CA4C407D43FCF0F"
FINGERPRINT_SPACED = " ".join([FINGERPRINT[i:i+2] for i in range(0, len(FINGERPRINT), 2)])
REPO_URL = "https://lauju1909.github.io/fdroid-repo/fdroid/repo"
FDROID_LINK = f"fdroidrepos://lauju1909.github.io/fdroid-repo/fdroid/repo?fingerprint={FINGERPRINT}"

def setup_directories():
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    (FDROID_DIR / "metadata").mkdir(parents=True, exist_ok=True)
    SITE_DIR.mkdir(parents=True, exist_ok=True)

def restore_keystores():
    # 1. Repo keystore
    repo_ks_b64 = os.environ.get("FDROID_REPO_KEYSTORE_BASE64")
    if repo_ks_b64:
        with open(FDROID_DIR / "repo-keystore.p12", "wb") as f:
            f.write(base64.b64decode(repo_ks_b64))
        print("Restored repo-keystore.p12 from environment")
    
    # 2. App release keystore
    app_ks_b64 = os.environ.get("APP_RELEASE_KEYSTORE_BASE64")
    if app_ks_b64:
        with open(ROOT_DIR / "release.keystore", "wb") as f:
            f.write(base64.b64decode(app_ks_b64))
        print("Restored release.keystore from environment")

def fetch_github_release(repo_name):
    token = os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{repo_name}/releases/latest"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Python-FDroid-Builder")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching release for {repo_name}: {e}")
        return None

def sign_apk(input_path, output_path):
    keystore = ROOT_DIR / "release.keystore"
    if not keystore.exists():
        print(f"Keystore {keystore} not found! Copying as-is.")
        shutil.copyfile(input_path, output_path)
        return

    password = os.environ.get("APP_RELEASE_KEYSTORE_PASSWORD", "LauriAndroid2026!")
    alias = os.environ.get("APP_RELEASE_KEY_ALIAS", "releasekey")

    cmd = [
        "apksigner", "sign",
        "--ks", str(keystore),
        "--ks-pass", f"pass:{password}",
        "--key-pass", f"pass:{password}",
        "--ks-key-alias", alias,
        "--out", str(output_path),
        str(input_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"Successfully signed {output_path.name}")
    else:
        print(f"apksigner failed: {res.stderr}. Using original APK.")
        shutil.copyfile(input_path, output_path)

def process_apps():
    app_results = []
    for app in APPS:
        print(f"\nProcessing {app['name']} ({app['repo']})...")
        
        # Download icon
        icon_path = ICONS_DIR / f"{app['id']}.png"
        try:
            req = urllib.request.Request(app["icon"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(icon_path, "wb") as f:
                f.write(resp.read())
            print(f"Downloaded icon to {icon_path.name}")
        except Exception as e:
            print(f"Could not download icon for {app['name']}: {e}")

        rel = fetch_github_release(app["repo"])
        if not rel:
            print(f"No release found for {app['name']}")
            continue

        tag = rel.get("tag_name", "unknown")
        assets = rel.get("assets", [])
        
        # Prefer release apk, fallback to debug
        selected_asset = None
        for a in assets:
            name = a["name"].lower()
            if name.endswith(".apk"):
                if "release" in name and not selected_asset:
                    selected_asset = a
                elif not selected_asset:
                    selected_asset = a

        if not selected_asset:
            print(f"No APK found in release {tag} for {app['name']}")
            continue

        apk_filename = f"{app['id']}_{tag.lstrip('v')}.apk"
        tmp_apk = ROOT_DIR / "tmp" / selected_asset["name"]
        tmp_apk.parent.mkdir(parents=True, exist_ok=True)
        final_apk = REPO_DIR / apk_filename

        print(f"Downloading {selected_asset['name']} ({tag})...")
        urllib.request.urlretrieve(selected_asset["browser_download_url"], tmp_apk)

        # Sign APK
        sign_apk(tmp_apk, final_apk)
        
        app_results.append({
            "name": app["name"],
            "id": app["id"],
            "version": tag,
            "desc": app["desc"],
            "apk_file": apk_filename,
            "apk_size": f"{os.path.getsize(final_apk) / (1024*1024):.1f} MB",
            "release_url": rel.get("html_url")
        })

    return app_results

def update_fdroid():
    print("\nRunning fdroid update...")
    # Inject keystorepass into config.yml
    config_file = FDROID_DIR / "config.yml"
    password = os.environ.get("FDROID_REPO_KEYSTORE_PASSWORD", "LauriFDroidRepo2026!")
    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    content_with_pass = content + f"\nkeystorepass: \"{password}\"\nkeypass: \"{password}\"\n"
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(content_with_pass)

    cmd = ["fdroid", "update", "-c", "--create-metadata"]
    res = subprocess.run(cmd, cwd=FDROID_DIR, capture_output=True, text=True)
    print("FDROID STDOUT:\n", res.stdout)
    print("FDROID STDERR:\n", res.stderr)
    
    # Restore original config without password
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(content)

    index_v1 = REPO_DIR / "index-v1.json"
    if not index_v1.exists():
        raise RuntimeError("fdroid update failed to generate index-v1.json!")

    print(f"fdroid update successful! Generated index size: {index_v1.stat().st_size} bytes")

def generate_web_portal(app_results):
    print("\nGenerating static web portal...")
    
    app_cards_html = ""
    for app in app_results:
        app_cards_html += f"""
        <article class="app-card" role="region" aria-label="{app['name']}">
            <div class="app-header">
                <img src="fdroid/repo/icons/{app['id']}.png" alt="App Icon für {app['name']}" class="app-icon" width="64" height="64" onerror="this.src='fdroid/icon.png'">
                <div>
                    <h3 class="app-title">{app['name']}</h3>
                    <span class="app-version">Version {app['version']} ({app['apk_size']})</span>
                </div>
            </div>
            <p class="app-desc">{app['desc']}</p>
            <div class="app-actions">
                <a href="fdroid/repo/{app['apk_file']}" class="btn btn-primary" download aria-label="{app['name']} Version {app['version']} APK herunterladen">
                    <span aria-hidden="true">⬇</span> APK Download
                </a>
                <a href="{app['release_url']}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" aria-label="Versionshinweise zu {app['name']} auf GitHub öffnen (externer Link)">
                    Changelog
                </a>
            </div>
        </article>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laujus Barrierefreie Apps – F-Droid Paketquelle</title>
    <meta name="description" content="Offizielle F-Droid Paketquelle für Laujus barrierefreie Android-Apps (Haushaltsbuch, Audio Studio Tycoon, WebUntis, Mini Games, TalkBack Übersetzer).">
    <style>
        :root {{
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --border-color: #30363d;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --accent: #2ea043;
            --accent-hover: #3fb950;
            --btn-sec-bg: #21262d;
            --btn-sec-border: #363b42;
            --btn-sec-hover: #30363d;
            --focus-ring: #58a6ff;
        }}
        @media (prefers-color-scheme: light) {{
            :root {{
                --bg-color: #f6f8fa;
                --card-bg: #ffffff;
                --border-color: #d0d7de;
                --text-main: #1f2328;
                --text-muted: #656d76;
                --accent: #1a7f37;
                --accent-hover: #1f883d;
                --btn-sec-bg: #f3f4f6;
                --btn-sec-border: #d0d7de;
                --btn-sec-hover: #e5e7eb;
                --focus-ring: #0969da;
            }}
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 24px 16px;
        }}
        header, main, footer {{ max-width: 900px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 32px; padding: 20px 0; }}
        h1 {{ font-size: 2rem; margin-bottom: 12px; }}
        p.subtitle {{ font-size: 1.15rem; color: var(--text-muted); margin-bottom: 24px; }}
        
        .setup-banner {{
            background: var(--card-bg);
            border: 2px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 40px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .setup-banner h2 {{ font-size: 1.4rem; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
        .cta-box {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 20px; }}
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px 20px;
            font-size: 1.05rem;
            font-weight: 600;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
            transition: background 0.15s ease, border-color 0.15s ease;
        }}
        .btn-primary {{
            background-color: var(--accent);
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .btn-primary:hover, .btn-primary:focus {{ background-color: var(--accent-hover); }}
        .btn-secondary {{
            background-color: var(--btn-sec-bg);
            color: var(--text-main);
            border: 1px solid var(--btn-sec-border);
        }}
        .btn-secondary:hover, .btn-secondary:focus {{ background-color: var(--btn-sec-hover); }}
        .btn:focus-visible, a:focus-visible, button:focus-visible {{
            outline: 3px solid var(--focus-ring);
            outline-offset: 2px;
        }}

        .code-box {{
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 12px 16px;
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 0.95rem;
            word-break: break-all;
            user-select: all;
            margin-bottom: 12px;
        }}
        .label {{ font-size: 0.9rem; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; display: block; }}

        .apps-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }}
        .app-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .app-header {{ display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }}
        .app-icon {{ border-radius: 12px; flex-shrink: 0; background: #21262d; }}
        .app-title {{ font-size: 1.15rem; line-height: 1.3; }}
        .app-version {{ font-size: 0.85rem; color: var(--text-muted); display: block; }}
        .app-desc {{ font-size: 0.95rem; color: var(--text-muted); margin-bottom: 20px; flex-grow: 1; }}
        .app-actions {{ display: flex; gap: 10px; }}
        .app-actions .btn {{ flex: 1; font-size: 0.95rem; padding: 8px 12px; }}

        footer {{
            text-align: center;
            margin-top: 50px;
            padding: 24px 0;
            border-top: 1px solid var(--border-color);
            color: var(--text-muted);
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <header role="banner">
        <h1>♿ Laujus Barrierefreie Apps</h1>
        <p class="subtitle">Offizielles F-Droid Repository für TalkBack-optimierte Android-Anwendungen</p>
    </header>

    <main role="main">
        <section class="setup-banner" aria-labelledby="repo-setup-title">
            <h2 id="repo-setup-title">📲 Zu F-Droid hinzufügen</h2>
            <p style="margin-bottom: 16px;">
                Füge dieses Repository direkt zu deiner <strong>F-Droid</strong> oder <strong>Neo Store</strong> App auf deinem Android-Smartphone hinzu, um alle barrierefreien Apps und künftige Updates vollautomatisch zu erhalten.
            </p>

            <div class="cta-box">
                <a href="{FDROID_LINK}" class="btn btn-primary" aria-label="Repository mit 1 Klick in F-Droid auf diesem Android-Smartphone öffnen">
                    <span aria-hidden="true">➕</span> In F-Droid hinzufügen (1-Klick)
                </a>
            </div>

            <span class="label">Repository-URL (manuell eintragen):</span>
            <div class="code-box" tabindex="0" role="textbox" aria-label="Repository Webadresse">{REPO_URL}</div>

            <span class="label">Fingerprint (SHA-256):</span>
            <div class="code-box" tabindex="0" role="textbox" aria-label="Sicherheits-Fingerprint des Repositories">{FINGERPRINT_SPACED}</div>
        </section>

        <section aria-labelledby="apps-heading">
            <h2 id="apps-heading" style="margin-bottom: 20px;">📦 Enthaltene barrierefreie Apps ({len(app_results)})</h2>
            <div class="apps-grid">
                {app_cards_html}
            </div>
        </section>
    </main>

    <footer role="contentinfo">
        <p>Entwickelt mit ❤️ für Barrierefreiheit, TalkBack & Screenreader. Quelloffen unter MIT-Lizenz.</p>
        <p style="margin-top: 8px;"><a href="https://github.com/Lauju1909" target="_blank" rel="noopener noreferrer" style="color: var(--accent);">Lauju1909 auf GitHub</a></p>
    </footer>
</body>
</html>
"""
    # Write to _site/index.html
    with open(SITE_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # Also write to root index.html for local preview
    with open(ROOT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Copy fdroid dir into _site/fdroid
    shutil.copytree(FDROID_DIR, SITE_DIR / "fdroid", dirs_exist_ok=True)
    print("Web portal and repo successfully staged in _site/")

def main():
    setup_directories()
    restore_keystores()
    apps = process_apps()
    update_fdroid()
    generate_web_portal(apps)
    print("\nAll done! Ready to deploy to GitHub Pages.")

if __name__ == "__main__":
    main()
