# Aquamarine

Tweaks by Thonin for rootless jailbreaks (iOS 15+).

**Add to Sileo / Zebra:** `https://thoninbazi.github.io/aquamarine/`

| Package | What it does |
|---|---|
| ChargeWatts | Live charging watts under your battery icon |
| DoubleTapLock | Double-tap to lock — and to unlock (Face ID / passcode still required) |
| CloseAll | Close every app from the app switcher (button or swipe down); hold a card to lock an app |
| FullOff | Control Center's Wi-Fi and Bluetooth buttons turn the radio fully off |

Maintainer notes: drop a `.deb` into `debs/`, describe it in `meta.json`, run `python3 tools/update.py`, commit and push.
Packages listed in `meta.json` → `repo.release_hosted` are served from the `debs` GitHub Release (uploaded automatically) so downloads are counted: `python3 tools/stats.py`.
