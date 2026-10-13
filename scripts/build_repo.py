#!/usr/bin/env python3
import os
import sys
import json
import base64
import shutil
import urllib.request
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FDROID_DIR = ROOT_DIR / "fdroid"
REPO_DIR = FDROID_DIR / "repo"
SITE_DIR = ROOT_DIR / "_site"
ICONS_DIR = REPO_DIR / "icons"
APPS_FILE = ROOT_DIR / "apps.json"

FINGERPRINT = "6CB811B89526A24CE7D41FB3FB4045B9FD0541D2017F96127CA4C407D43FCF0F"
FINGERPRINT_SPACED = " ".join([FINGERPRINT[i:i+2] for i in range(0, len(FINGERPRINT), 2)])
REPO_URL = "https://lauju1909.github.io/fdroid-repo/fdroid/repo"
FDROID_LINK = f"fdroidrepos://lauju1909.github.io/fdroid-repo/fdroid/repo?fingerprint={FINGERPRINT}"

def load_apps_list():
    if not APPS_FILE.exists():
        print(f"Error: {APPS_FILE} not found!")
        sys.exit(1)
    with open(APPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_apps_list(apps):
    with open(APPS_FILE, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2, ensure_ascii=False)

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

def fetch_github_release(repo_name, is_beta=False):
    token = os.environ.get("GITHUB_TOKEN")
    clean_repo = repo_name.strip().replace("https://github.com/", "").rstrip("/")
    headers = {"User-Agent": "Python-FDroid-Builder"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if is_beta:
        url = f"https://api.github.com/repos/{clean_repo}/releases"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                releases = json.loads(resp.read().decode("utf-8"))
                for r in releases:
                    if r.get("prerelease") or "beta" in r.get("tag_name", "").lower():
                        return r
                return releases[0] if releases else None
        except Exception as e:
            print(f"Error fetching beta release for {clean_repo}: {e}")
            return None
    else:
        url = f"https://api.github.com/repos/{clean_repo}/releases/latest"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Error fetching latest release for {clean_repo}: {e}")
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

def process_apps(apps):
    app_results = []
    # Nur freigeschaltete Apps (approved) im Repository bauen
    approved_apps = [a for a in apps if a.get("status") == "approved"]
    
    print(f"\nVerarbeite {len(approved_apps)} freigeschaltete Apps von insgesamt {len(apps)}...")

    for app in approved_apps:
        print(f"\nProcessing {app['name']} ({app['repo']})...")
        
        # Download icon
        icon_path = ICONS_DIR / f"{app['id']}.png"
        icon_url = app.get("icon")
        if icon_url:
            try:
                req = urllib.request.Request(icon_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req) as resp, open(icon_path, "wb") as f:
                    f.write(resp.read())
                print(f"Downloaded icon to {icon_path.name}")
            except Exception as e:
                print(f"Could not download icon for {app['name']}: {e}")

        is_beta = bool(app.get("isBeta", False))
        rel = fetch_github_release(app["repo"], is_beta=is_beta)
        if not rel:
            print(f"No release found for {app['name']}")
            continue

        tag = rel.get("tag_name", "unknown")
        assets = rel.get("assets", [])
        
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
            "author": app.get("author", "Laurin Schneider"),
            "version": tag,
            "desc": app["desc"],
            "apk_file": apk_filename,
            "apk_size": f"{os.path.getsize(final_apk) / (1024*1024):.1f} MB",
            "release_url": rel.get("html_url"),
            "paymentType": app.get("paymentType", "free"),
            "price": app.get("price", ""),
            "paymentUrl": app.get("paymentUrl", ""),
            "isBeta": is_beta
        })

    return app_results

def update_fdroid():
    print("\nRunning fdroid update...")
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
    
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(content)

    index_v1 = REPO_DIR / "index-v1.json"
    if not index_v1.exists():
        raise RuntimeError("fdroid update failed to generate index-v1.json!")

    print(f"fdroid update successful! Generated index size: {index_v1.stat().st_size} bytes")

def generate_web_portal(app_results, all_apps):
    print("\nGenerating static web portal with submit & edit capabilities...")
    
    app_cards_html = ""
    for app in app_results:
        beta_badge = '<span class="badge badge-beta">🧪 Beta</span>' if app.get("isBeta") else ''
        
        # Zahlungsbadge & Button
        payment_btn = ""
        payment_badge = '<span class="badge badge-free">Kostenlos</span>'
        if app.get("paymentType") == "donation" and app.get("paymentUrl"):
            payment_badge = '<span class="badge badge-donation">☕ Spende</span>'
            payment_btn = f'<a href="{app["paymentUrl"]}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">☕ Spenden</a>'
        elif app.get("paymentType") == "paid" and app.get("paymentUrl"):
            price_label = app.get("price") or "Kauf"
            payment_badge = f'<span class="badge badge-paid">💰 {price_label}</span>'
            payment_btn = f'<a href="{app["paymentUrl"]}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">💰 Kaufen ({price_label})</a>'

        app_cards_html += f"""
        <article class="app-card" role="region" aria-label="{app['name']}">
            <div class="app-header">
                <img src="fdroid/repo/icons/{app['id']}.png" alt="App Icon für {app['name']}" class="app-icon" width="64" height="64" onerror="this.src='fdroid/icon.png'">
                <div>
                    <h3 class="app-title">{app['name']}</h3>
                    <span class="app-version">Von {app.get('author', 'Laurin Schneider')} · Version {app['version']} ({app['apk_size']})</span>
                    <div style="margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap;">
                        {beta_badge}
                        {payment_badge}
                    </div>
                </div>
            </div>
            <p class="app-desc">{app['desc']}</p>
            <div class="app-actions">
                <a href="fdroid/repo/{app['apk_file']}" class="btn btn-primary" download aria-label="{app['name']} Version {app['version']} APK herunterladen">
                    <span aria-hidden="true">⬇</span> APK Download
                </a>
                {payment_btn}
                <a href="{app['release_url']}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" aria-label="Versionshinweise">
                    Changelog
                </a>
            </div>
        </article>
        """

    # JSON der gesamten Datenbank für die Live-Webseiten-Suche / Bearbeitung
    apps_json_escaped = json.dumps(all_apps, ensure_ascii=False).replace("</script>", "<\\/script>")

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laujus Barrierefreie Apps – F-Droid Paketquelle &amp; Entwickler-Portal</title>
    <meta name="description" content="Offizielle F-Droid Paketquelle für Laujus barrierefreie Android-Apps mit 1-Klick GitHub Einreichung.">
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
            --badge-beta: #8957e5;
            --badge-donation: #d29922;
            --badge-paid: #f0883e;
            --badge-free: #238636;
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
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }}
        h1 {{ font-size: 2.2rem; margin-bottom: 8px; }}
        .subtitle {{ color: var(--text-muted); font-size: 1.1rem; }}
        
        .portal-nav {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-bottom: 30px;
        }}
        .portal-nav-btn {{
            padding: 10px 20px;
            border-radius: 8px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            cursor: pointer;
            font-weight: 600;
            font-size: 1rem;
        }}
        .portal-nav-btn.active {{
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
        }}

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
            padding: 10px 18px;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
            transition: background 0.15s ease, border-color 0.15s ease;
            border: none;
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
        .btn:focus-visible, a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {{
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

        .badge {{
            display: inline-block;
            font-size: 0.75rem;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 12px;
            color: #fff;
        }}
        .badge-beta {{ background-color: var(--badge-beta); }}
        .badge-donation {{ background-color: var(--badge-donation); }}
        .badge-paid {{ background-color: var(--badge-paid); }}
        .badge-free {{ background-color: var(--badge-free); }}
        .badge-pending {{ background-color: #d29922; }}

        .apps-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
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
        .app-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .app-actions .btn {{ font-size: 0.9rem; padding: 8px 12px; }}

        /* Formular Sektion für Veröffentlichung & Bearbeitung */
        .submit-section {{
            background: var(--card-bg);
            border: 2px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 40px;
        }}
        .form-row {{
            margin-bottom: 18px;
        }}
        .form-input, .form-select {{
            width: 100%;
            padding: 12px 14px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background: var(--bg-color);
            color: var(--text-main);
            font-size: 1rem;
            margin-top: 6px;
        }}
        .form-helper {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .status-box {{
            padding: 16px;
            border-radius: 8px;
            background: rgba(46, 160, 67, 0.15);
            border: 1px solid var(--accent);
            margin-top: 20px;
            display: none;
        }}

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

    <div class="portal-nav" role="navigation" aria-label="Portalbereiche">
        <button id="nav-btn-apps" class="portal-nav-btn active" onclick="showPortalTab('apps')">📦 Alle Apps ({len(app_results)})</button>
        <button id="nav-btn-submit" class="portal-nav-btn" onclick="showPortalTab('submit')">➕ Neue App veröffentlichen / bearbeiten</button>
        <button id="nav-btn-status" class="portal-nav-btn" onclick="showPortalTab('status')">🔍 Prüfungsstatus &amp; Verwaltung</button>
    </div>

    <main role="main">
        <!-- TAB 1: APPS LISTE -->
        <section id="portal-tab-apps">
            <section class="setup-banner" aria-labelledby="repo-setup-title">
                <h2 id="repo-setup-title">📲 Zu F-Droid hinzufügen</h2>
                <p style="margin-bottom: 16px;">
                    Füge dieses Repository direkt zu deiner <strong>F-Droid</strong> oder <strong>Lauju Store</strong> App auf deinem Android-Smartphone hinzu, um alle barrierefreien Apps und künftige Updates vollautomatisch zu erhalten.
                </p>

                <div class="cta-box">
                    <a href="{FDROID_LINK}" class="btn btn-primary" aria-label="Repository mit 1 Klick in F-Droid öffnen">
                        <span aria-hidden="true">➕</span> In F-Droid / Lauju Store hinzufügen (1-Klick)
                    </a>
                </div>

                <span class="label">Repository-URL (manuell eintragen):</span>
                <div class="code-box" tabindex="0" role="textbox" aria-label="Repository Webadresse">{REPO_URL}</div>

                <span class="label">Fingerprint (SHA-256):</span>
                <div class="code-box" tabindex="0" role="textbox" aria-label="Sicherheits-Fingerprint des Repositories">{FINGERPRINT_SPACED}</div>
            </section>

            <section aria-labelledby="apps-heading">
                <h2 id="apps-heading" style="margin-bottom: 20px;">📦 Freigeschaltete Apps im Repository ({len(app_results)})</h2>
                <div class="apps-grid">
                    {app_cards_html}
                </div>
            </section>
        </section>

        <!-- TAB 2: APP VERÖFFENTLICHEN & BEARBEITEN -->
        <section id="portal-tab-submit" class="submit-section" style="display: none;">
            <h2>🚀 App in Laujus Paketquelle veröffentlichen oder bearbeiten</h2>
            <p style="color: var(--text-muted); margin-bottom: 24px;">
                Du brauchst <strong>keine</strong> komplizierten F-Droid Strukturen! Es reicht einfach nur dein <strong>GitHub-Code-Link</strong>. Den Rest (Paket-ID, Name, Releases &amp; APKs) liest unser System vollautomatisch aus.
            </p>

            <form id="app-submit-form" onsubmit="handleAppSubmission(event)">
                <div class="form-row">
                    <label for="input-github-repo" style="font-weight: bold;">1. GitHub-Quellcode Link:</label>
                    <div style="display: flex; gap: 8px; margin-top: 6px;">
                        <input type="text" id="input-github-repo" class="form-input" placeholder="https://github.com/Benutzer/Meine-App" required style="margin-top: 0;">
                        <button type="button" class="btn btn-secondary" onclick="fetchGitHubMetadata()" style="white-space: nowrap;">🔍 Prüfen &amp; Laden</button>
                    </div>
                    <p class="form-helper">Gib die GitHub-Adresse deines Projekts ein. Bei einer bestehenden App kannst du hier auch bestehende Einstellungen laden &amp; bearbeiten!</p>
                </div>

                <div id="detected-metadata-box" style="display: none; padding: 14px; background: rgba(56, 189, 248, 0.1); border: 1px solid var(--focus-ring); border-radius: 8px; margin-bottom: 18px;">
                    <h3 style="font-size: 1.1rem; margin-bottom: 6px;">✨ Erkannte App-Informationen:</h3>
                    <p><strong>Name:</strong> <span id="meta-app-name">-</span></p>
                    <p><strong>Beschreibung:</strong> <span id="meta-app-desc">-</span></p>
                    <p><strong>Neueste Version:</strong> <span id="meta-app-version">-</span></p>
                </div>

                <div class="form-row">
                    <label for="input-payment-type" style="font-weight: bold;">2. Bezahl- &amp; Erlösmodell:</label>
                    <select id="input-payment-type" class="form-select" onchange="togglePaymentInputs()">
                        <option value="free">Kostenlos (0,00 €)</option>
                        <option value="donation">Freiwillige Spende (Pay-What-You-Want)</option>
                        <option value="paid">Kauf-App (Fester oder flexibler Preis)</option>
                    </select>
                </div>

                <div id="row-price" class="form-row" style="display: none;">
                    <label for="input-app-price" style="font-weight: bold;">Preis (in €):</label>
                    <input type="text" id="input-app-price" class="form-input" placeholder="z. B. 2,99 € oder Wunschbetrag">
                    <p class="form-helper">Betrag, den Käufer im Store sehen.</p>
                </div>

                <div id="row-payment-url" class="form-row" style="display: none;">
                    <label for="input-payment-url" style="font-weight: bold;">Kostenloser Zahlungslink (PayPal.me oder Ko-fi):</label>
                    <input type="url" id="input-payment-url" class="form-input" placeholder="https://paypal.me/DeinName oder https://ko-fi.com/DeinName">
                    <p class="form-helper">100% kostenloser Link, wohin das Geld bei Klick auf "Kaufen" oder "Spenden" überwiesen wird.</p>
                </div>

                <div class="form-row">
                    <label style="font-weight: bold; display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="input-is-beta" style="width: 20px; height: 20px;">
                        <span>🧪 Als Beta-Version veröffentlichen</span>
                    </label>
                    <p class="form-helper">Beta-Apps werden mit dem Beta-Abzeichen markiert und können von Testern vorab ausprobiert werden.</p>
                </div>

                <button type="submit" id="btn-submit-app" class="btn btn-primary" style="width: 100%; font-size: 1.1rem; padding: 14px;">
                    ✅ App zur Prüfung einreichen / Änderungen speichern
                </button>
            </form>

            <div id="submission-result-box" class="status-box">
                <h3 id="submission-title">🎉 Einreichung erfolgreich vorbereitet!</h3>
                <p id="submission-text" style="margin-top: 6px;"></p>
                <div style="margin-top: 14px;">
                    <a id="submission-issue-link" href="#" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
                        📝 Jetzt auf GitHub mit 1 Klick einreichen (Issue erstellen)
                    </a>
                </div>
            </div>
        </section>

        <!-- TAB 3: STATUS & PRÜFUNG -->
        <section id="portal-tab-status" class="submit-section" style="display: none;">
            <h2>🔍 Prüfungsstatus &amp; Paketquellen-Verwaltung</h2>
            <p style="color: var(--text-muted); margin-bottom: 20px;">
                Alle eingereichten Apps durchlaufen vor der offiziellen Freischaltung eine Prüfung, um höchste Barrierefreiheit und Sicherheit zu garantieren.
            </p>
            <div id="status-apps-list" class="apps-grid">
                <!-- Wird dynamisch mit JS aus all_apps befüllt -->
            </div>
        </section>
    </main>

    <footer role="contentinfo">
        <p>Entwickelt mit ❤️ für Barrierefreiheit, TalkBack & Screenreader. Quelloffen unter MIT-Lizenz.</p>
        <p style="margin-top: 8px;"><a href="https://github.com/Lauju1909" target="_blank" rel="noopener noreferrer" style="color: var(--accent);">Lauju1909 auf GitHub</a></p>
    </footer>

    <script>
        const ALL_APPS = {apps_json_escaped};

        function showPortalTab(tab) {{
            document.getElementById('portal-tab-apps').style.display = (tab === 'apps') ? 'block' : 'none';
            document.getElementById('portal-tab-submit').style.display = (tab === 'submit') ? 'block' : 'none';
            document.getElementById('portal-tab-status').style.display = (tab === 'status') ? 'block' : 'none';

            document.getElementById('nav-btn-apps').classList.toggle('active', tab === 'apps');
            document.getElementById('nav-btn-submit').classList.toggle('active', tab === 'submit');
            document.getElementById('nav-btn-status').classList.toggle('active', tab === 'status');

            if (tab === 'status') renderStatusList();
        }}

        function togglePaymentInputs() {{
            const val = document.getElementById('input-payment-type').value;
            document.getElementById('row-price').style.display = (val === 'paid') ? 'block' : 'none';
            document.getElementById('row-payment-url').style.display = (val === 'paid' || val === 'donation') ? 'block' : 'none';
        }}

        let detectedMeta = null;

        async function fetchGitHubMetadata() {{
            const rawUrl = document.getElementById('input-github-repo').value.trim();
            if (!rawUrl) return alert('Bitte zuerst eine GitHub-Adresse eingeben!');
            
            const cleanRepo = rawUrl.replace('https://github.com/', '').replace(/\/+$/, '');
            
            // Prüfen ob bereits in Datenbank zum Bearbeiten
            const existing = ALL_APPS.find(a => a.repo.toLowerCase() === cleanRepo.toLowerCase());
            if (existing) {{
                document.getElementById('input-payment-type').value = existing.paymentType || 'free';
                document.getElementById('input-app-price').value = existing.price || '';
                document.getElementById('input-payment-url').value = existing.paymentUrl || '';
                document.getElementById('input-is-beta').checked = !!existing.isBeta;
                togglePaymentInputs();
            }}

            try {{
                const res = await fetch(`https://api.github.com/repos/${{cleanRepo}}`);
                if (!res.ok) throw new Error('Repository auf GitHub nicht gefunden!');
                const repoData = await res.json();

                const relRes = await fetch(`https://api.github.com/repos/${{cleanRepo}}/releases/latest`);
                const relData = relRes.ok ? await relRes.json() : null;

                detectedMeta = {{
                    repo: cleanRepo,
                    name: repoData.name,
                    desc: repoData.description || 'Keine Beschreibung vorhanden.',
                    version: relData ? relData.tag_name : 'Noch kein Release'
                }};

                document.getElementById('meta-app-name').textContent = detectedMeta.name;
                document.getElementById('meta-app-desc').textContent = detectedMeta.desc;
                document.getElementById('meta-app-version').textContent = detectedMeta.version;
                document.getElementById('detected-metadata-box').style.display = 'block';

                if (existing) {{
                    alert(`Bestehende App "${{existing.name}}" geladen! Du kannst die Einstellungen jetzt direkt anpassen.`);
                }}
            }} catch (e) {{
                alert('Fehler beim Abrufen der GitHub-Informationen: ' + e.message);
            }}
        }}

        function handleAppSubmission(e) {{
            e.preventDefault();
            const rawUrl = document.getElementById('input-github-repo').value.trim();
            const cleanRepo = rawUrl.replace('https://github.com/', '').replace(/\/+$/, '');
            const paymentType = document.getElementById('input-payment-type').value;
            const price = document.getElementById('input-app-price').value.trim();
            const paymentUrl = document.getElementById('input-payment-url').value.trim();
            const isBeta = document.getElementById('input-is-beta').checked;

            const title = `[App Einreichung / Update] ${{cleanRepo}}`;
            const body = `### Neue App Einreichung / Änderung\\n\\n` +
                         `- **GitHub Repo:** https://github.com/${{cleanRepo}}\\n` +
                         `- **Modell:** ${{paymentType}}\\n` +
                         `- **Preis:** ${{price || 'Kostenlos'}}\\n` +
                         `- **Zahlungslink:** ${{paymentUrl || 'Keiner'}}\\n` +
                         `- **Beta:** ${{isBeta ? 'Ja' : 'Nein'}}\\n\\n` +
                         `*Automatisch generiert über das Lauju F-Droid Entwicklerportal.*`;

            const issueUrl = `https://github.com/Lauju1909/fdroid-repo/issues/new?title=${{encodeURIComponent(title)}}&body=${{encodeURIComponent(body)}}`;

            document.getElementById('submission-result-box').style.display = 'block';
            document.getElementById('submission-title').textContent = '🎉 Bereit zur Freischaltung!';
            document.getElementById('submission-text').innerHTML = `Deine App <strong>${{cleanRepo}}</strong> wurde vorbereitet. Klicke unten, um den Freigabe-Antrag mit 1 Klick an Lauju1909 zu senden.`;
            document.getElementById('submission-issue-link').href = issueUrl;
        }}

        function renderStatusList() {{
            const list = document.getElementById('status-apps-list');
            list.innerHTML = '';

            ALL_APPS.forEach(app => {{
                const isApproved = (app.status === 'approved');
                const card = document.createElement('article');
                card.className = 'app-card';
                card.innerHTML = `
                    <div class="app-header">
                        <img src="${{app.icon || 'fdroid/icon.png'}}" class="app-icon" width="56" height="56" onerror="this.src='fdroid/icon.png'">
                        <div>
                            <h3 class="app-title">${{app.name}}</h3>
                            <span class="app-version">${{app.repo}}</span>
                            <div style="margin-top: 6px;">
                                <span class="badge ${{isApproved ? 'badge-free' : 'badge-pending'}}">
                                    ${{isApproved ? '🟢 Freigeschaltet &amp; Aktiv' : '🟡 In Prüfung (Pending)'}}
                                </span>
                            </div>
                        </div>
                    </div>
                    <p class="app-desc">${{app.desc}}</p>
                    <div class="app-actions">
                        <button class="btn btn-secondary" onclick="editApp('${{app.repo}}')">✏️ Bearbeiten</button>
                        <a href="https://github.com/${{app.repo}}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">🔗 Quellcode</a>
                    </div>
                `;
                list.appendChild(card);
            }});
        }}

        function editApp(repo) {{
            showPortalTab('submit');
            document.getElementById('input-github-repo').value = 'https://github.com/' + repo;
            fetchGitHubMetadata();
        }}
    </script>
</body>
</html>
"""
    # Write to _site/index.html
    with open(SITE_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # Also write to root index.html for local preview
    with open(ROOT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Copy apps.json into _site
    shutil.copyfile(APPS_FILE, SITE_DIR / "apps.json")

    # Copy fdroid dir into _site/fdroid
    shutil.copytree(FDROID_DIR, SITE_DIR / "fdroid", dirs_exist_ok=True)
    print("Web portal and repo successfully staged in _site/")

def main():
    setup_directories()
    restore_keystores()
    apps = load_apps_list()
    app_results = process_apps(apps)
    update_fdroid()
    generate_web_portal(app_results, apps)
    print("\nAll done! Ready to deploy to GitHub Pages.")

if __name__ == "__main__":
    main()
