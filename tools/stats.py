#!/usr/bin/env python3
"""Download counts for Aquamarine packages, from the GitHub Release that serves the .debs (see update.py).
   python3 tools/stats.py            per package + per version
Counts are downloads (installs, reinstalls, updates — not unique people). Only packages switched to release
hosting (meta.json repo.release_hosted) are counted; anything served from GitHub Pages has no stats."""
import json, os, subprocess, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
meta = json.load(open(os.path.join(ROOT, 'meta.json')))
GH, TAG = meta['repo']['github'], meta['repo']['release_tag']
rel = json.loads(subprocess.run(['gh', 'api', f'repos/{GH}/releases/tags/{TAG}'], capture_output=True, text=True, check=True).stdout)
per_pkg, rows = collections.Counter(), []
for a in rel['assets']:
    if not a['name'].endswith('.deb'): continue
    pkg, ver = a['name'].split('_')[:2]
    per_pkg[pkg] += a['download_count']
    rows.append((pkg, ver, a['download_count'], a['created_at'][:10]))
print(f"{'package':32} {'downloads':>9}")
for pkg, n in per_pkg.most_common(): print(f"{pkg:32} {n:>9}")
print(f"{'TOTAL':32} {sum(per_pkg.values()):>9}\n")
print(f"{'package':32} {'version':10} {'downloads':>9}  uploaded")
for pkg, ver, n, d in sorted(rows): print(f"{pkg:32} {ver:10} {n:>9}  {d}")
