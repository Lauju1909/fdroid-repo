use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Duration;
use walkdir::WalkDir;

const GITHUB_USER_DEFAULT: &str = "Lauju1909";
const REPO_NAME_DEFAULT: &str = "fdroid-repo";

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AppEntry {
    #[serde(default)]
    id: Option<String>,
    repo: String,
    #[serde(default)]
    name: String,
    #[serde(default)]
    author: Option<String>,
    #[serde(default)]
    category: String,
    #[serde(default)]
    summary: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    desc: Option<String>,
    #[serde(default)]
    package_name: Option<String>,
    #[serde(default)]
    version_name: Option<String>,
    #[serde(default)]
    version_code: Option<u64>,
    #[serde(default)]
    release_tag: Option<String>,
    #[serde(default)]
    direct_apk_url: Option<String>,
    #[serde(default)]
    release_date: Option<String>,
    #[serde(default)]
    icon: Option<String>,
    #[serde(default)]
    icon_url: Option<String>,
    #[serde(default)]
    status: Option<String>,
    #[serde(default)]
    payment_type: Option<String>,
    #[serde(default)]
    price: Option<String>,
    #[serde(default)]
    payment_url: Option<String>,
    #[serde(default)]
    is_beta: Option<bool>,
    #[serde(default)]
    hide_author: Option<bool>,
    #[serde(flatten)]
    extra: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
}

#[derive(Debug, Deserialize)]
struct GitHubRelease {
    #[serde(default)]
    tag_name: String,
    #[serde(default)]
    published_at: String,
    #[serde(default)]
    assets: Vec<GitHubAsset>,
}

fn patch_androguard_and_fdroid() {
    println!("=== [Rust] Patching Androguard & fdroidserver for Modern Android Compatibility ===");
    let roots = ["/usr/lib/python3", "/usr/local/lib"];
    let mut axml_files = Vec::new();
    let mut apk_files = Vec::new();
    let mut update_files = Vec::new();

    for root in &roots {
        if !Path::new(root).exists() {
            continue;
        }
        for entry in WalkDir::new(root).into_iter().filter_map(Result::ok) {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            if let Some(name) = path.file_name().and_then(|s| s.to_str()) {
                match name {
                    "axml.py" => axml_files.push(path.to_path_buf()),
                    "apk.py" => apk_files.push(path.to_path_buf()),
                    "update.py" => {
                        if path.to_string_lossy().contains("fdroidserver") {
                            update_files.push(path.to_path_buf());
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    for f in axml_files {
        if let Ok(mut content) = fs::read_to_string(&f) {
            println!("Patching axml {:?}...", f);
            content = content.replace("raise ResParserError", "pass # raise ResParserError");
            let _ = fs::write(&f, content);
        }
    }

    for f in apk_files {
        if let Ok(mut content) = fs::read_to_string(&f) {
            println!("Patching apk {:?}...", f);
            content = content.replace("raise APKError", "pass # raise APKError");
            let _ = fs::write(&f, content);
        }
    }

    for f in update_files {
        if let Ok(content) = fs::read_to_string(&f) {
            println!("Checking / patching scan_apk in {:?}...", f);
            let mut new_lines = Vec::new();
            let mut patched = false;
            for line in content.lines() {
                if line.trim() == "apk = scan_apk(apkfile)" {
                    let indent = line.chars().take_while(|c| c.is_whitespace()).collect::<String>();
                    new_lines.push(format!("{}try:", indent));
                    new_lines.push(format!("{}    apk = scan_apk(apkfile)", indent));
                    new_lines.push(format!("{}except Exception as e:", indent));
                    new_lines.push(format!("{}    logging.warning(f'scan_apk failed on {{apkfile}}: {{e}}')", indent));
                    new_lines.push(format!("{}    return None", indent));
                    patched = true;
                } else {
                    new_lines.push(line.to_string());
                }
            }
            if patched {
                println!("Successfully patched {:?} with consistent indentation.", f);
                let _ = fs::write(&f, new_lines.join("\n"));
            }
        }
    }
}

fn http_agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_read(Duration::from_secs(60))
        .timeout_write(Duration::from_secs(30))
        .user_agent("FDroid-Rust-Builder/2.0 (compatible; Android-Accessibility-Catalog)")
        .build()
}

fn fetch_releases(repo_full_name: &str) -> Vec<GitHubRelease> {
    let url = format!("https://api.github.com/repos/{}/releases", repo_full_name);
    let agent = http_agent();
    let mut req = agent
        .get(&url)
        .set("Accept", "application/vnd.github.v3+json");
    if let Ok(token) = env::var("GITHUB_TOKEN") {
        if !token.trim().is_empty() {
            req = req.set("Authorization", &format!("token {}", token.trim()));
        }
    }

    match req.call() {
        Ok(resp) => resp.into_json::<Vec<GitHubRelease>>().unwrap_or_default(),
        Err(e) => {
            eprintln!("Error fetching releases for {}: {}", repo_full_name, e);
            Vec::new()
        }
    }
}

fn download_file(url: &str, dest_path: &Path) -> bool {
    println!("Downloading {} -> {:?}...", url, dest_path);
    let agent = http_agent();
    for attempt in 1..=3 {
        let mut req = agent
            .get(url)
            .set("Accept", "application/vnd.android.package-archive, application/octet-stream, */*");
        // Only set Authorization for api.github.com, NOT for github.com/releases/download or S3 objects
        if url.contains("api.github.com") {
            if let Ok(token) = env::var("GITHUB_TOKEN") {
                if !token.trim().is_empty() {
                    req = req.set("Authorization", &format!("token {}", token.trim()));
                }
            }
        }
        match req.call() {
            Ok(resp) => {
                let mut bytes = Vec::new();
                if resp.into_reader().read_to_end(&mut bytes).is_ok() && !bytes.is_empty() {
                    if let Some(parent) = dest_path.parent() {
                        let _ = fs::create_dir_all(parent);
                    }
                    if fs::write(dest_path, &bytes).is_ok() {
                        println!("Saved {:?} ({} bytes)", dest_path, bytes.len());
                        return true;
                    }
                }
            }
            Err(e) => {
                eprintln!("Download attempt {}/3 failed for {}: {}", attempt, url, e);
                std::thread::sleep(Duration::from_secs(3));
            }
        }
    }
    false
}

fn fetch_app_icon(repo_full_name: &str, dest_dir: &Path, safe_repo_prefix: &str) -> Option<String> {
    let candidates = [
        "www/icon-512.png",
        "www/icon-192.png",
        "assets/icon.png",
        "icon.png",
        "fastlane/metadata/android/en-US/images/icon.png",
        "fastlane/metadata/android/de-DE/images/icon.png",
        "android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png",
        "app/src/main/res/mipmap-xxxhdpi/ic_launcher.png",
        "app/src/main/ic_launcher-playstore.png",
    ];
    let branches = ["main", "master"];
    let agent = http_agent();

    for branch in &branches {
        for rel_path in &candidates {
            let raw_url = format!(
                "https://raw.githubusercontent.com/{}/{}/{}",
                repo_full_name, branch, rel_path
            );
            if let Ok(resp) = agent.get(&raw_url).call() {
                if resp.status() == 200 {
                    let mut data = Vec::new();
                    if resp.into_reader().read_to_end(&mut data).is_ok() && data.len() > 100 {
                        let _ = fs::create_dir_all(dest_dir);
                        let icon_filename = format!("{}.png", safe_repo_prefix);
                        let icon_dest = dest_dir.join(&icon_filename);
                        if fs::write(&icon_dest, &data).is_ok() {
                            println!(
                                "Fetched app icon for {} from {} ({} bytes)",
                                repo_full_name,
                                rel_path,
                                data.len()
                            );
                            return Some(format!("icons/{}", icon_filename));
                        }
                    }
                }
            }
        }
    }
    println!("No custom icon found for {}, using default.", repo_full_name);
    None
}

fn create_fallback_icon(icon_path: &Path) {
    if icon_path.exists() {
        return;
    }
    let png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
    if let Ok(bytes) = BASE64.decode(png_b64) {
        if let Some(parent) = icon_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let _ = fs::write(icon_path, bytes);
    }
}

fn resign_apk_if_needed(
    apk_path: &Path,
    keystore_path: &Path,
    keystore_pass: &str,
    key_alias: &str,
) -> bool {
    if !keystore_path.exists() {
        return false;
    }
    println!(
        "Signing {:?} with official release key ({})...",
        apk_path.file_name().unwrap_or_default(),
        key_alias
    );
    let pass_arg = format!("pass:{}", keystore_pass);
    let status = Command::new("apksigner")
        .args([
            "sign",
            "--ks",
            &keystore_path.to_string_lossy(),
            "--ks-key-alias",
            key_alias,
            "--ks-pass",
            &pass_arg,
            "--key-pass",
            &pass_arg,
            "--v1-signing-enabled",
            "true",
            "--v2-signing-enabled",
            "true",
            "--v3-signing-enabled",
            "true",
            &apk_path.to_string_lossy(),
        ])
        .status();

    match status {
        Ok(s) if s.success() => true,
        _ => {
            eprintln!("Warning: apksigner failed on {:?}", apk_path);
            false
        }
    }
}

fn extract_index_json_from_jar(jar_path: &Path, output_json_path: &Path) -> bool {
    if !jar_path.exists() {
        return false;
    }
    if let Ok(file) = fs::File::open(jar_path) {
        if let Ok(mut archive) = zip::ZipArchive::new(file) {
            if let Ok(mut index_file) = archive.by_name("index-v1.json") {
                let mut content = Vec::new();
                if index_file.read_to_end(&mut content).is_ok() {
                    if let Some(parent) = output_json_path.parent() {
                        let _ = fs::create_dir_all(parent);
                    }
                    if fs::write(output_json_path, &content).is_ok() {
                        println!("Extracted index-v1.json successfully from {:?} ({} bytes)", jar_path, content.len());
                        return true;
                    }
                }
            }
        }
    }
    false
}

fn copy_dir_recursive(src: &Path, dst: &Path) -> std::io::Result<()> {
    if !dst.exists() {
        fs::create_dir_all(dst)?;
    }
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let file_type = entry.file_type()?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if file_type.is_dir() {
            copy_dir_recursive(&src_path, &dst_path)?;
        } else {
            fs::copy(&src_path, &dst_path)?;
        }
    }
    Ok(())
}

fn html_escape(input: &str) -> String {
    input
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn generate_landing_page(apps_data: &[AppEntry], repo_url: &str, base_dir: &Path) {
    let mut app_cards_html = String::new();
    for app in apps_data {
        let name = html_escape(if app.name.is_empty() {
            &app.repo
        } else {
            &app.name
        });
        let summary = html_escape(if !app.summary.is_empty() {
            &app.summary
        } else if let Some(ref d) = app.desc {
            d
        } else {
            &app.description
        });
        let category = html_escape(if app.category.is_empty() {
            "Allgemein"
        } else {
            &app.category
        });
        let version = html_escape(app.release_tag.as_deref().unwrap_or("Aktuell"));
        let apk_url = app.direct_apk_url.as_deref().unwrap_or("#");
        let gh_url = format!("https://github.com/{}", app.repo);

        let dl_btn = if apk_url != "#" {
            format!(
                r#"<a href="{}" class="btn btn-primary" aria-label="{} Version {} direkt als APK herunterladen">📥 Direkt-APK ({})</a>"#,
                apk_url, name, version, version
            )
        } else {
            r#"<span class="badge">Noch kein APK-Release</span>"#.to_string()
        };

        app_cards_html.push_str(&format!(
            r#"
        <article class="app-card" role="listitem">
            <div class="app-header">
                <span class="category-badge">{category}</span>
                <h3>{name}</h3>
            </div>
            <p>{summary}</p>
            <div class="app-actions">
                {dl_btn}
                <a href="{gh_url}" target="_blank" rel="noopener" class="btn btn-secondary" aria-label="Quellcode von {name} auf GitHub ansehen">💻 GitHub</a>
            </div>
        </article>
        "#
        ));
    }

    let html = format!(
        r#"<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Barrierefreier F-Droid App-Store &amp; Repository (Powered by Rust)</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f8fafc;
            --muted: #cbd5e1;
            --accent: #38bdf8;
            --accent-dark: #0284c7;
            --border: #334155;
            --focus: #facc15;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            margin: 0;
            padding: 0;
        }}
        header, main, footer {{
            max-width: 960px;
            margin: 0 auto;
            padding: 1.5rem;
        }}
        header {{
            border-bottom: 2px solid var(--border);
            margin-bottom: 1.5rem;
        }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .repo-box {{
            background: var(--card);
            border: 2px solid var(--accent);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}
        .repo-url {{
            display: block;
            width: 100%;
            background: #020617;
            color: var(--accent);
            border: 1px solid var(--border);
            padding: 0.85rem;
            font-size: 1.05rem;
            font-family: monospace;
            border-radius: 8px;
            margin: 0.75rem 0;
            word-break: break-all;
        }}
        .btn {{
            display: inline-block;
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            border: 2px solid transparent;
            font-size: 1rem;
            margin-right: 0.5rem;
            margin-top: 0.5rem;
        }}
        .btn:focus-visible, a:focus-visible, button:focus-visible {{
            outline: 3px solid var(--focus);
            outline-offset: 2px;
        }}
        .btn-primary {{
            background: var(--accent);
            color: #020617;
        }}
        .btn-primary:hover {{
            background: #7dd3fc;
        }}
        .btn-secondary {{
            background: transparent;
            color: var(--text);
            border-color: var(--border);
        }}
        .app-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
            gap: 1.25rem;
        }}
        .app-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .category-badge {{
            display: inline-block;
            background: #334155;
            color: var(--accent);
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        footer {{
            border-top: 1px solid var(--border);
            margin-top: 3rem;
            color: var(--muted);
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <header role="banner">
        <h1>♿ Barrierefreies F-Droid Repository</h1>
        <p>Offizieller Katalog für barrierefreie Apps (TalkBack-optimiert). Füge diese Paketquelle in <strong>F-Droid</strong>, <strong>Droid-ify</strong>, <strong>Neo Store</strong> oder direkt in unserer <strong>Barrierefreien App-Store App</strong> hinzu.</p>
    </header>

    <main role="main">
        <section class="repo-box" aria-labelledby="repo-heading">
            <h2 id="repo-heading">🔗 F-Droid Paketquellen-Adresse (Repository URL)</h2>
            <p>Kopiere diesen Link in F-Droid unter <em>Einstellungen → Paketquellen → Neue Paketquelle hinzufügen</em>:</p>
            <code class="repo-url" id="repoUrlText">{repo_url}</code>
            <div>
                <button class="btn btn-primary" onclick="navigator.clipboard.writeText('{repo_url}').then(() => alert('Paketquellen-URL wurde in die Zwischenablage kopiert!'))">
                    📋 URL kopieren
                </button>
                <a class="btn btn-secondary" href="fdroidrepos://{repo_url}">
                    📲 Direkt in F-Droid öffnen
                </a>
            </div>
        </section>

        <section aria-labelledby="apps-heading">
            <h2 id="apps-heading">📦 Enthaltene Apps ({app_count})</h2>
            <div class="app-grid" role="list">
                {app_cards_html}
            </div>
        </section>
    </main>

    <footer role="contentinfo">
        <p>Automatisch aktualisiert via Rust &amp; GitHub Actions • Barrierefrei gestaltet für Screenreader (TalkBack / NVDA).</p>
    </footer>
</body>
</html>
"#,
        repo_url = repo_url,
        app_count = apps_data.len(),
        app_cards_html = app_cards_html
    );

    let site_dir = base_dir.join("_site");
    let _ = fs::create_dir_all(&site_dir);
    let _ = fs::write(site_dir.join("index.html"), &html);
    let _ = fs::write(base_dir.join("index.html"), &html);
}

fn build_repository(base_dir: &Path) {
    println!("=== [Rust] Starting F-Droid Repository Builder ===");
    let apps_json_path = base_dir.join("apps.json");
    let fdroid_dir = base_dir.join("fdroid");
    let repo_dir = fdroid_dir.join("repo");
    let metadata_dir = fdroid_dir.join("metadata");

    let apps_raw = fs::read_to_string(&apps_json_path).expect("Failed to read apps.json");
    let mut apps_data: Vec<AppEntry> =
        serde_json::from_str(&apps_raw).expect("Failed to parse apps.json");

    let github_owner = env::var("GITHUB_REPOSITORY_OWNER")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| GITHUB_USER_DEFAULT.to_string());
    let repo_full = env::var("GITHUB_REPOSITORY").unwrap_or_default();
    let repo_name = repo_full
        .split('/')
        .nth(1)
        .filter(|s| !s.is_empty())
        .unwrap_or(REPO_NAME_DEFAULT)
        .to_string();
    let repo_url = format!("https://{}.github.io/{}/fdroid/repo", github_owner, repo_name);

    let _ = fs::create_dir_all(&repo_dir);
    let _ = fs::create_dir_all(&metadata_dir);

    let keystore_path = fdroid_dir.join("repo-keystore.p12");
    let keystore_pass = env::var("FDROID_REPO_KEYSTORE_PASSWORD")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "fdroid-Accessible-Store-Key-2026".to_string());
    let key_alias = "fdroid-repo-key";

    let app_keystore_path = fdroid_dir.join("app-release-keystore.jks");
    let app_keystore_pass = env::var("APP_RELEASE_KEYSTORE_PASSWORD")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "LauriAndroid2026!".to_string());
    let app_key_alias = env::var("APP_RELEASE_KEY_ALIAS")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "releasekey".to_string());

    if let Ok(app_ks_b64) = env::var("APP_RELEASE_KEYSTORE_BASE64") {
        let trimmed = app_ks_b64.trim();
        if !trimmed.is_empty() {
            if let Ok(decoded) = BASE64.decode(trimmed) {
                let _ = fs::write(&app_keystore_path, decoded);
                println!("Restored official app release keystore from secret.");
            }
        }
    }

    if let Ok(repo_ks_b64) = env::var("FDROID_REPO_KEYSTORE_BASE64") {
        let trimmed = repo_ks_b64.trim();
        if !trimmed.is_empty() {
            if let Ok(decoded) = BASE64.decode(trimmed) {
                let _ = fs::write(&keystore_path, decoded);
                println!("Restored persistent F-Droid repository keystore from secret.");
            }
        }
    }

    if !keystore_path.exists() {
        println!("Generating persistent PKCS12 keystore for F-Droid repo...");
        let _ = Command::new("keytool")
            .args([
                "-genkeypair",
                "-v",
                "-keystore",
                &keystore_path.to_string_lossy(),
                "-storetype",
                "PKCS12",
                "-storepass",
                &keystore_pass,
                "-keypass",
                &keystore_pass,
                "-alias",
                key_alias,
                "-keyalg",
                "RSA",
                "-keysize",
                "4096",
                "-validity",
                "10000",
                "-dname",
                "CN=Lauju Barrierefreier App-Store, OU=Accessibility, O=Lauju1909, L=Berlin, ST=Berlin, C=DE",
            ])
            .status();
    }

    let config_yml = format!(
        r#"repo_url: "{repo_url}"
repo_name: "Lauju Barrierefreier App-Store"
repo_description: "Offizielles F-Droid Repository für barrierefreie Apps (TalkBack-optimiert)."
repo_icon: "icon.png"
archive_older: 0
local_copy_dir: "/tmp/fdroid"
keystore: "repo-keystore.p12"
repo_keyalias: "{key_alias}"
keystorepass: "{keystore_pass}"
keypass: "{keystore_pass}"
keydname: "CN=Lauju Barrierefreier App-Store, OU=Accessibility, O=Lauju1909, L=Berlin, ST=Berlin, C=DE"
"#,
        repo_url = repo_url,
        key_alias = key_alias,
        keystore_pass = keystore_pass
    );

    let config_path = fdroid_dir.join("config.yml");
    let _ = fs::write(&config_path, config_yml);
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&config_path, fs::Permissions::from_mode(0o600));
    }

    create_fallback_icon(&fdroid_dir.join("icon.png"));
    create_fallback_icon(&repo_dir.join("icons").join("icon.png"));

    let site_icons_dir = base_dir.join("_site").join("icons");
    let _ = fs::create_dir_all(&site_icons_dir);

    for app in &mut apps_data {
        let repo_full_name = app.repo.clone();
        println!("Checking releases for {}...", repo_full_name);
        let safe_repo_prefix = repo_full_name.replace('/', "_");

        let pkg_id = app.id.clone().or_else(|| app.package_name.clone()).unwrap_or_else(|| safe_repo_prefix.clone());
        app.id = Some(pkg_id.clone());
        app.package_name = Some(pkg_id.clone());

        if let Some(rel_icon_path) =
            fetch_app_icon(&repo_full_name, &site_icons_dir, &safe_repo_prefix)
        {
            app.icon_url = Some(format!(
                "https://{}.github.io/{}/{}",
                github_owner, repo_name, rel_icon_path
            ));
        }

        let releases = fetch_releases(&repo_full_name);
        let mut downloaded_count = 0usize;
        let mut seen_tags = HashSet::new();

        for (rel_idx, rel) in releases.iter().enumerate() {
            if downloaded_count >= 3 {
                break;
            }
            let tag = if rel.tag_name.is_empty() {
                format!("v1.0.{}", rel_idx)
            } else {
                rel.tag_name.clone()
            };
            if seen_tags.contains(&tag) {
                continue;
            }

            let mut apk_assets: Vec<&GitHubAsset> = rel
                .assets
                .iter()
                .filter(|a| a.name.to_lowercase().ends_with(".apk"))
                .collect();

            if apk_assets.is_empty() {
                continue;
            }

            // Strictly filter out debug and unsigned APKs
            let release_apks: Vec<&GitHubAsset> = apk_assets
                .iter()
                .copied()
                .filter(|a| {
                    let lower = a.name.to_lowercase();
                    !lower.contains("debug") && !lower.contains("unsigned")
                })
                .collect();

            if release_apks.is_empty() {
                println!(
                    "Skipping release {} for {} (only debug/unsigned APKs found)",
                    tag, repo_full_name
                );
                continue;
            }

            apk_assets = release_apks;
            apk_assets.sort_by_key(|a| {
                let lower = a.name.to_lowercase();
                if lower.starts_with("lauju_") || lower.contains("release") {
                    0
                } else {
                    1
                }
            });

            let best_asset = apk_assets[0];
            let dl_url = &best_asset.browser_download_url;
            let safe_tag = tag.replace('/', "_").replace(' ', "_");
            let dest_filename = format!("{}_{}_{}", safe_repo_prefix, safe_tag, best_asset.name);
            let dest_path = repo_dir.join(&dest_filename);

            if downloaded_count == 0 {
                app.release_tag = Some(tag.clone());
                app.direct_apk_url = Some(dl_url.clone());
                app.release_date = Some(rel.published_at.clone());
                let clean_ver = tag.trim_start_matches('v').to_string();
                app.version_name = Some(clean_ver);
            }

            if download_file(dl_url, &dest_path) {
                if app_keystore_path.exists() {
                    resign_apk_if_needed(
                        &dest_path,
                        &app_keystore_path,
                        &app_keystore_pass,
                        &app_key_alias,
                    );
                }

                // Also copy with standardized names so direct URLs always resolve
                let standard_apk = repo_dir.join(format!("{}.apk", pkg_id));
                let _ = fs::copy(&dest_path, &standard_apk);
                let latest_apk = repo_dir.join(format!("{}_latest.apk", pkg_id));
                let _ = fs::copy(&dest_path, &latest_apk);

                downloaded_count += 1;
                seen_tags.insert(tag);
            }
        }
    }

    println!("Running `fdroid update -c --create-metadata`...");
    let status = Command::new("fdroid")
        .args(["update", "-c", "--create-metadata", "--verbose"])
        .current_dir(&fdroid_dir)
        .status();

    let ok = status.map(|s| s.success()).unwrap_or(false);
    if !ok {
        println!("fdroid update returned non-zero, retrying without --create-metadata...");
        let _ = Command::new("fdroid")
            .args(["update", "-c"])
            .current_dir(&fdroid_dir)
            .status();
    }

    // Extract index-v1.json from index-v1.jar if generated
    let jar_path = repo_dir.join("index-v1.jar");
    let json_extracted_path = repo_dir.join("index-v1.json");
    let _ = extract_index_json_from_jar(&jar_path, &json_extracted_path);

    // Remove keystore before staging
    if app_keystore_path.exists() {
        let _ = fs::remove_file(&app_keystore_path);
    }

    let site_dir = base_dir.join("_site");
    let _ = fs::create_dir_all(&site_dir);
    if let Ok(json_out) = serde_json::to_string_pretty(&apps_data) {
        let _ = fs::write(site_dir.join("apps.json"), json_out);
    }

    generate_landing_page(&apps_data, &repo_url, base_dir);

    let site_fdroid = site_dir.join("fdroid");
    let site_repo = site_dir.join("repo");
    if site_fdroid.exists() {
        let _ = fs::remove_dir_all(&site_fdroid);
    }
    if site_repo.exists() {
        let _ = fs::remove_dir_all(&site_repo);
    }
    let _ = fs::create_dir_all(&site_fdroid);
    let _ = fs::create_dir_all(&site_repo);

    if repo_dir.exists() {
        let _ = copy_dir_recursive(&repo_dir, &site_fdroid.join("repo"));
        let _ = copy_dir_recursive(&repo_dir, &site_repo);
    }
    let icon_src = fdroid_dir.join("icon.png");
    if icon_src.exists() {
        let _ = fs::copy(&icon_src, site_fdroid.join("icon.png"));
        let _ = fs::copy(&icon_src, site_dir.join("icon.png"));
    }

    let _ = fs::write(site_dir.join(".nojekyll"), "");
    println!("=== [Rust] Done! Static site and F-Droid repo generated in _site/ ===");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mode = args.get(1).map(|s| s.as_str()).unwrap_or("all");

    let base_dir = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));

    match mode {
        "patch" => patch_androguard_and_fdroid(),
        "build" => build_repository(&base_dir),
        _ => {
            patch_androguard_and_fdroid();
            build_repository(&base_dir);
        }
    }
}
