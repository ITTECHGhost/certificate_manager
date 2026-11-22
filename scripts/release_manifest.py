"""Release manifest (path + sha256 of every client file) and the changes-only zip.

Usage: py -3 scripts/release_manifest.py <app_dir> <version> <out_dir> [--changes <old_manifest.json>]
Writes <out_dir>/manifest_v<version>.json and, with --changes,
<out_dir>/patch_v<version>_from_<old version>.zip holding only new/modified files.
server_config.json is never included (a laptop's own settings).
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

SKIP = {"server_config.json"}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(app_dir) -> dict:
    root = Path(app_dir)
    return {p.relative_to(root).as_posix(): sha256_file(p)
            for p in sorted(root.rglob("*")) if p.is_file() and p.name.lower() not in SKIP}


def changed_files(old: dict, new: dict) -> list:
    return sorted(p for p, h in new.items() if old.get(p) != h)


def write_changes_zip(app_dir, old: dict, zip_path) -> int:
    root = Path(app_dir)
    paths = changed_files(old, build_manifest(root))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in paths:
            z.write(root / rel, rel)
    return len(paths)


def main(argv) -> int:
    args = list(argv)
    old_path = None
    if "--changes" in args:
        i = args.index("--changes")
        old_path = args[i + 1]
        del args[i:i + 2]
    app_dir, version, out_dir = args
    out = Path(out_dir)
    manifest = build_manifest(app_dir)
    (out / f"manifest_v{version}.json").write_text(
        json.dumps({"version": version, "files": manifest}, indent=0), encoding="utf-8")
    print(f"manifest: {len(manifest)} files")
    if old_path:
        old = json.loads(Path(old_path).read_text(encoding="utf-8"))
        zp = out / f"patch_v{version}_from_{old['version']}.zip"
        n = write_changes_zip(app_dir, old["files"], zp)
        print(f"changes: {n} files -> {zp.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
