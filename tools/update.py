#!/usr/bin/env python3
"""Regenerate the Aquamarine repo index from debs/ + meta.json:
Packages (+ .gz .bz2 .xz .zst), Release (MD5Sum/SHA1/SHA256), depictions/<pkg>/{depiction.json,index.html},
sileo-featured.json, index.html, .nojekyll.  Run after adding/replacing a .deb:  python3 tools/update.py"""
import bz2, gzip, hashlib, html, json, lzma, os, subprocess, sys, time
from email.utils import formatdate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
meta = json.load(open('meta.json'))
REPO, PKGS = meta['repo'], meta['packages']
BASE = REPO['base_url'].rstrip('/') + '/'

# Download counts: packages listed in repo.release_hosted ("*" = all) are served from the GitHub Release
# repo.release_tag (GitHub counts every download; tools/stats.py reads them) via an absolute Filename URL —
# Sileo (DownloadManager.swift) and Zebra 1.1.x (ZBDownloadManager.m) both download absolute URLs directly.
# The same .deb stays in debs/ (the source of truth). Missing assets are uploaded; an asset that differs from the
# local file stops the run (a published version must never change — bump the version instead).
GH, TAG, HOSTED = REPO.get('github'), REPO.get('release_tag'), REPO.get('release_hosted') or []
_assets = None
def release_assets(refresh=False):
    global _assets
    if _assets is None or refresh:
        out = subprocess.run(['gh', 'api', f'repos/{GH}/releases/tags/{TAG}'], capture_output=True, text=True, check=True).stdout
        _assets = {a['name']: a for a in json.loads(out)['assets']}
    return _assets
def hosted_url(path, sha256):
    name = os.path.basename(path)
    if name not in release_assets():
        subprocess.run(['gh', 'release', 'upload', TAG, path, '--repo', GH], check=True)
        print(f'uploaded {name} to release {TAG}')
        release_assets(refresh=True)
    a = release_assets()[name]
    if a['size'] != os.path.getsize(path) or (a.get('digest') and a['digest'] != 'sha256:' + sha256):
        sys.exit(f'{name}: the release asset differs from debs/{name} — never change a published version; bump it')
    return a['browser_download_url']

def control(deb):
    out = subprocess.run(['dpkg-deb', '-f', deb], capture_output=True, text=True, check=True).stdout
    fields, key = {}, None
    for line in out.splitlines():
        if line.startswith((' ', '\t')) and key: fields[key] += '\n' + line
        elif ':' in line: key, v = line.split(':', 1); fields[key.strip()] = v.strip()
    return fields

def ver_key(v):   # good-enough Debian-ish ordering for x.y.z versions
    return [int(p) if p.isdigit() else p for p in v.replace('-', '.').replace('~', '.').split('.')]

# ---------------------------------------------------------------- Packages
entries, latest = [], {}
for f in sorted(os.listdir('debs')):
    if not f.endswith('.deb'): continue
    if PKGS.get(control(os.path.join('debs', f))['Package'], {}).get('hidden'):
        sys.exit(f'{f}: package is marked hidden in meta.json — keep its .deb out of debs/ (it would be downloadable)')
    p = os.path.join('debs', f); data = open(p, 'rb').read(); c = control(p)
    pid = c['Package']
    c.update({'Filename': p, 'Size': str(len(data)), 'MD5sum': hashlib.md5(data).hexdigest(),
              'SHA1': hashlib.sha1(data).hexdigest(), 'SHA256': hashlib.sha256(data).hexdigest()})
    if GH and TAG and (HOSTED == '*' or '*' in HOSTED or pid in HOSTED):
        c['Filename'] = hosted_url(p, c['SHA256'])
    if os.path.exists(f'icons/{pid}.png'): c['Icon'] = BASE + f'icons/{pid}.png'
    c['Depiction'] = BASE + f'depictions/{pid}/'
    c['SileoDepiction'] = BASE + f'depictions/{pid}/depiction.json'
    entries.append(c)
    if pid not in latest or ver_key(c['Version']) > ver_key(latest[pid]['Version']): latest[pid] = c
order = ['Package', 'Name', 'Version', 'Architecture', 'Description', 'Maintainer', 'Author', 'Section', 'Depends',
         'Conflicts', 'Replaces', 'Provides', 'Tag', 'Icon', 'Depiction', 'SileoDepiction', 'Filename', 'Size',
         'MD5sum', 'SHA1', 'SHA256']
def stanza(c):
    keys = [k for k in order if k in c] + sorted(k for k in c if k not in order)
    return '\n'.join(f'{k}: {c[k]}' for k in keys)
packages = ('\n\n'.join(stanza(c) for c in sorted(entries, key=lambda c: (c['Package'], ver_key(c['Version'])))) + '\n').encode()
open('Packages', 'wb').write(packages)
open('Packages.gz', 'wb').write(gzip.compress(packages, 9, mtime=0))
open('Packages.bz2', 'wb').write(bz2.compress(packages, 9))
open('Packages.xz', 'wb').write(lzma.compress(packages))
try:
    import zstandard
    open('Packages.zst', 'wb').write(zstandard.ZstdCompressor(level=19).compress(packages))
except ImportError:
    print('note: python zstandard missing — Packages.zst skipped', file=sys.stderr)
# self-check: every variant decodes to the same bytes
assert gzip.decompress(open('Packages.gz', 'rb').read()) == packages
assert bz2.decompress(open('Packages.bz2', 'rb').read()) == packages
assert lzma.decompress(open('Packages.xz', 'rb').read()) == packages

# ---------------------------------------------------------------- Release
idx = [f for f in ('Packages', 'Packages.gz', 'Packages.bz2', 'Packages.xz', 'Packages.zst') if os.path.exists(f)]
rel = [f"Origin: {REPO['name']}", f"Label: {REPO['name']}", 'Suite: stable', 'Version: 1.0',
       f"Codename: {REPO['name'].lower()}", 'Architectures: iphoneos-arm64', 'Components: main',
       f"Description: {REPO['description']}", f"Date: {formatdate(usegmt=True)}"]
for algo, name in (('md5', 'MD5Sum'), ('sha1', 'SHA1'), ('sha256', 'SHA256')):
    rel.append(f'{name}:')
    for f in idx:
        d = open(f, 'rb').read(); rel.append(f' {hashlib.new(algo, d).hexdigest()} {len(d)} {f}')
open('Release', 'w').write('\n'.join(rel) + '\n')

# ---------------------------------------------------------------- depictions
def human_size(n):
    n = int(n)
    return f'{n / 1048576:.2f} MB' if n >= 1048576 else f'{max(1, round(n / 1024))} KB'
def release_date(c):
    local = c['Filename'] if not c['Filename'].startswith('http') else os.path.join('debs', os.path.basename(c['Filename']))
    return time.strftime('%B %-d, %Y', time.localtime(os.path.getmtime(local)))
def info_rows(c, m):   # the "Information" section (Version / Size / iOS Versions / Updated / Developer)
    return [('Version', c['Version']), ('Size', human_size(c['Size'])), ('iOS Versions', m.get('ios', '')),
            ('Updated', release_date(c)), ('Developer', c.get('Author', 'Thonin'))]
CSS = """body{margin:0;font:16px -apple-system,system-ui,sans-serif;background:#0b1622;color:#e8f4f3}
.wrap{max-width:720px;margin:auto;padding:24px 18px}.hd{display:flex;gap:16px;align-items:center}
.hd img{width:72px;height:72px;border-radius:16px}.tag{color:#9fc7c4}h1{margin:0;font-size:26px}
.card{background:#132536;border-radius:16px;padding:16px 18px;margin:16px 0}a{color:#5fe0d6}
table{width:100%;border-collapse:collapse}td{padding:6px 0;border-bottom:1px solid #1f3448}td:first-child{color:#9fc7c4}
ul{padding-left:20px}li{margin:4px 0}.btn{display:inline-block;background:#2bb8b0;color:#04201e;font-weight:600;
padding:10px 16px;border-radius:12px;text-decoration:none;margin:6px 8px 0 0}"""

def md_to_html(md):
    out, inlist = [], False
    for line in md.split('\n'):
        if line.startswith('- '):
            if not inlist: out.append('<ul>'); inlist = True
            out.append(f'<li>{html.escape(line[2:])}</li>')
        else:
            if inlist: out.append('</ul>'); inlist = False
            if line.strip(): out.append(f'<p>{html.escape(line)}</p>')
    if inlist: out.append('</ul>')
    return '\n'.join(out)

for pid, c in latest.items():
    m = PKGS.get(pid, {})
    d = f'depictions/{pid}'; os.makedirs(d, exist_ok=True)
    changelog = m.get('changelog', [[c['Version'], '']])
    sileo = {
        'minVersion': '0.1', 'class': 'DepictionTabView', 'tintColor': REPO.get('tint', '#2BB8B0'),
        'headerImage': BASE + 'icons/banner.png',
        'tabs': [
            {'tabname': 'Details', 'class': 'DepictionStackView', 'views': [
                # the tagline goes in the markdown as a bold first line: DepictionHeaderView truncates to one line
                {'class': 'DepictionMarkdownView', 'markdown': f"**{m['tagline']}**\n\n" * bool(m.get('tagline')) + m.get('description', c.get('Description', ''))},
                {'class': 'DepictionSubheaderView', 'title': 'Information', 'useBoldText': True, 'useBottomMargin': True},
                {'class': 'DepictionSeparatorView'},
            ] + [{'class': 'DepictionTableTextView', 'title': k, 'text': v} for k, v in info_rows(c, m) if v]},
            {'tabname': 'Changelog', 'class': 'DepictionStackView', 'views': [
                {'class': 'DepictionMarkdownView', 'markdown': f'**{v}**\n\n{t}'} for v, t in changelog]},
        ]}
    json.dump(sileo, open(f'{d}/depiction.json', 'w'), indent=1, ensure_ascii=False)
    rows = ''.join(f'<tr><td>{k}</td><td>{html.escape(v)}</td></tr>' for k, v in info_rows(c, m) if v)
    log = ''.join(f'<p><b>{html.escape(v)}</b> — {html.escape(t)}</p>' for v, t in changelog)
    open(f'{d}/index.html', 'w').write(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(c.get('Name', pid))}</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="hd"><img src="{BASE}icons/{pid}.png" alt=""><div><h1>{html.escape(c.get('Name', pid))}</h1>
<div class="tag">{html.escape(m.get('tagline', ''))}</div></div></div>
<div class="card">{md_to_html(m.get('description', c.get('Description', '')))}</div>
<div class="card"><h3>Information</h3><table>{rows}</table></div><div class="card"><h3>Changelog</h3>{log}</div>
</div></body></html>""")

# remove pages of packages that are no longer published (hidden / deleted)
import shutil
for d in os.listdir('depictions'):
    if d not in latest and os.path.isdir(os.path.join('depictions', d)): shutil.rmtree(os.path.join('depictions', d))

# ---------------------------------------------------------------- featured + landing page + .nojekyll
json.dump({'class': 'FeaturedBannersView', 'itemSize': '{263, 148}', 'itemCornerRadius': 10,
           'banners': [{'url': BASE + f'icons/{pid}.png', 'title': latest[pid].get('Name', pid), 'package': pid,
                        'hideShadow': False} for pid in sorted(latest)]},
          open('sileo-featured.json', 'w'), indent=1)
cards = ''.join(f"""<a class="card pk" href="depictions/{pid}/"><img src="icons/{pid}.png" alt="">
<div><b>{html.escape(c.get('Name', pid))}</b> <span class="tag">{html.escape(c['Version'])}</span><br>
<span class="tag">{html.escape(PKGS.get(pid, {}).get('tagline', c.get('Description', '')))}</span></div></a>"""
                for pid, c in sorted(latest.items(), key=lambda kv: kv[1].get('Name', kv[0])))
open('index.html', 'w').write(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{REPO['name']}</title>
<style>{CSS} .pk{{display:flex;gap:14px;align-items:center;color:inherit;text-decoration:none}}
.pk img{{width:52px;height:52px;border-radius:12px}}</style></head><body><div class="wrap">
<div class="hd"><img src="CydiaIcon.png" alt=""><div><h1>{REPO['name']}</h1><div class="tag">{html.escape(REPO['description'])}</div></div></div>
<div class="card"><a class="btn" href="sileo://source/{BASE}">Add to Sileo</a><a class="btn" href="zbra://sources/add/{BASE}">Add to Zebra</a>
<p class="tag">Or add this source manually: <b>{BASE}</b></p></div>
{cards}
</div></body></html>""")
open('.nojekyll', 'w').write('')
print(f'{len(entries)} package versions, {len(latest)} packages -> Packages/Release/depictions/index regenerated ({time.strftime("%H:%M:%S")})')
