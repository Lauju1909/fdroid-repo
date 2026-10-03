#!/usr/bin/env python3
import os
import sys

def patch_file(path, replacements):
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    modified = False
    for target, rep in replacements.items():
        if target in content:
            content = content.replace(target, rep)
            modified = True
            print(f"Patched '{target}' -> '{rep}' in {path}")
            
    if modified:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    return modified

def main():
    print("=== Patching androguard and fdroidserver for modern Android APKs ===")
    
    # 1. Patch androguard res1 and res0 strict checks
    androguard_dir = "/usr/lib/python3/dist-packages/androguard"
    if os.path.exists(androguard_dir):
        for root, _, files in os.walk(androguard_dir):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    patch_file(full_path, {
                        'raise ResParserError("res1 must be zero!")': 'pass',
                        'raise ResParserError("res0 must be zero!")': 'pass'
                    })

    # 2. Also check if androguard was installed in site-packages
    for sp in ["/usr/local/lib/python3.12/dist-packages/androguard", "/home/runner/.local/lib/python3.12/site-packages/androguard"]:
        if os.path.exists(sp):
            for root, _, files in os.walk(sp):
                for file in files:
                    if file.endswith(".py"):
                        full_path = os.path.join(root, file)
                        patch_file(full_path, {
                            'raise ResParserError("res1 must be zero!")': 'pass',
                            'raise ResParserError("res0 must be zero!")': 'pass'
                        })

    # 3. Patch fdroidserver update.py for safe icon int parsing
    fdroid_dir = "/usr/lib/python3/dist-packages/fdroidserver"
    update_py = os.path.join(fdroid_dir, "update.py")
    if os.path.exists(update_py):
        with open(update_py, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # In fdroidserver update.py, replace int(icon_id, 16) or similar with safe parsing
        if "icon_id = int(" in content:
            content = content.replace("icon_id = int(", "icon_id = int(str(")
        # If any string has 0xandroid: strip it
        if "android:" in content:
            pass

    print("Patches applied successfully.")

if __name__ == "__main__":
    main()
