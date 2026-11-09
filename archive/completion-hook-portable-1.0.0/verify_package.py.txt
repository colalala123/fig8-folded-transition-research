"""Verify release source integrity. SHA256 is not a publisher signature."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root/'SHA256SUMS.json').read_text(encoding='utf-8'))
for name, expected in manifest['files'].items():
    path = (root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise SystemExit('Missing/invalid file: '+name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('SHA256 mismatch: '+name)
print(f"Verified {len(manifest['files'])} packaged source files; version {manifest['version']}.")
