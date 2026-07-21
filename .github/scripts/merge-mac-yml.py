#!/usr/bin/env python3
"""
Merge two architecture-specific latest-mac.yml files (produced by separate
electron-builder x64 and arm64 builds) into a single combined file that
electron-updater can use to serve the correct binary per architecture.

Usage:
    python3 merge-mac-yml.py <version> <x64-yml> <arm64-yml> <output-yml>

The filenames inside each yml are renamed from electron-builder's generic
artifact names to the human-readable release asset names, e.g.:
    skellycam_2.0.0-alpha.2_x64_installer.zip
    → skellycam_2.0.0-alpha.2_macos-x64-intel.zip
"""

import sys
import yaml


def patch_entry(entry: dict, arch_label: str, version: str) -> dict:
    patched = dict(entry)
    name = entry.get("url", "")
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext:
        patched["url"] = f"skellycam_{version}_{arch_label}.{ext}"
    return patched


def load_yml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    if len(sys.argv) != 5:
        sys.exit(f"Usage: {sys.argv[0]} <version> <x64-yml> <arm64-yml> <output-yml>")

    version, x64_path, arm64_path, out_path = sys.argv[1:]

    x64 = load_yml(x64_path)
    arm64 = load_yml(arm64_path)

    x64_files = [patch_entry(e, "macos-x64-intel", version) for e in x64.get("files", [])]
    arm64_files = [patch_entry(e, "macos-arm64-apple-silicon", version) for e in arm64.get("files", [])]

    # Root-level path/sha512 → x64 zip (fallback for older electron-updater)
    primary = next((f for f in x64_files if f["url"].endswith(".zip")), x64_files[0])

    merged = {
        "version": x64["version"],
        "files": x64_files + arm64_files,
        "path": primary["url"],
        "sha512": primary["sha512"],
        "releaseDate": x64.get("releaseDate") or arm64.get("releaseDate", ""),
    }

    with open(out_path, "w") as f:
        yaml.dump(merged, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Wrote {out_path}")
    for entry in merged["files"]:
        print(f"  {entry['url']}")


if __name__ == "__main__":
    main()
