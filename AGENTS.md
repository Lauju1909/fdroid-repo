# AGENTS.md - Developer & AI Assistant Guidelines for fdroid-repo

This repository manages and publishes Lauju's custom F-Droid repository via GitHub Pages.

## Core Rules & Architecture
1. **Never commit keystores:** All signing keystores (`*.p12`, `*.jks`, `*.keystore`) are strictly gitignored. They are stored as base64 in GitHub Secrets:
   - `FDROID_REPO_KEYSTORE_BASE64`: Repository index signing key (PKCS12, alias `fdroid`).
   - `APP_RELEASE_KEYSTORE_BASE64`: APK signing key (`releasekey`).
2. **Repository URL & Fingerprint:**
   - URL: `https://lauju1909.github.io/fdroid-repo/fdroid/repo`
   - Fingerprint: `6CB811B89526A24CE7D41FB3FB4045B9FD0541D2017F96127CA4C407D43FCF0F`
   - NEVER regenerate the repo keystore or change the fingerprint, as this would break F-Droid on all user devices!
3. **Workflow:** `.github/workflows/update-repo.yml` runs on push to main, workflow_dispatch, and every 6 hours. It fetches the latest releases from Lauju1909's 5 app repositories, signs them with `apksigner`, runs `fdroid update`, and deploys to GitHub Pages.
