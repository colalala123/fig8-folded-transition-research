"""Verify frozen archive byte hashes. Offline, no repair or write side effects."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
items=json.loads((root/'provenance/ARCHIVE_MANIFEST.json').read_text(encoding='utf8'))
errors=[]
for r in items:
 p=root/r['path']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:errors.append(r['path'])
print(json.dumps({'files':len(items),'errors':errors,'ok':not errors},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
