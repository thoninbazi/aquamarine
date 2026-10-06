#!/bin/bash
# Package the single-dylib SpringBoard tweaks (ChargeWatts, DoubleTapLock) as rootless debs into ../debs/.
# Usage: tools/build_tweak_debs.sh [package-id …]   (no args = all). Never rebuild an already-published version:
# update.py refuses when a .deb differs from its GitHub Release asset — bump the version instead.
set -e; cd "$(dirname "$0")/.."
T=/Users/thonin/Projects/Bazi23/tweak/springboard
ONLY="$*"
mk() {  # mk <pkg> <Name> <dir> <version> <description>
  if [ $# -gt 0 ] && [ -n "$ONLY" ] && ! printf "%s\n" $ONLY | grep -qx "$1"; then return; fi
  local S; S=$(mktemp -d); chmod 755 "$S"
  mkdir -p "$S/DEBIAN" "$S/var/jb/Library/MobileSubstrate/DynamicLibraries"
  cp "$T/$3/$3.dylib" "$T/$3/$3.plist" "$S/var/jb/Library/MobileSubstrate/DynamicLibraries/"
  cat > "$S/DEBIAN/control" <<CTL
Package: $1
Name: $2
Version: $4
Architecture: iphoneos-arm64
Description: $5
Maintainer: Thonin
Author: Thonin
Section: Tweaks
Depends: firmware (>= 15.0), mobilesubstrate
CTL
  printf '#!/bin/sh\nfd=${SILEO:-$CYDIA}; fd=${fd%%%% *}\n[ -n "$fd" ] && eval "echo finish:restart >&$fd"\nexit 0\n' > "$S/DEBIAN/postinst"
  chmod 755 "$S/DEBIAN/postinst"; chmod 644 "$S"/var/jb/Library/MobileSubstrate/DynamicLibraries/*
  dpkg-deb --root-owner-group -Zxz -b "$S" "debs/${1}_${4}_iphoneos-arm64.deb" >/dev/null; rm -rf "$S"
  echo "built debs/${1}_${4}_iphoneos-arm64.deb"
}
mk com.thonin.chargewatts ChargeWatts ChargeWatts 1.0.0 "Live charging watts under your battery icon."
mk com.thonin.doubletaplock DoubleTapLock DoubleTapLock 1.0.1 "Double-tap empty space to lock (screen off, like the side button), and on the Lock Screen to unlock (Face ID / passcode still required)."
