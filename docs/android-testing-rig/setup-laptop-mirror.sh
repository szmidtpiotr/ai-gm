#!/usr/bin/env bash
# Install scrcpy + the AI-GM mobile mirror tray app on a laptop/desktop client.
#
# Connects to the ADB server on the Claude VM (.19) over LAN or VPN and mirrors
# the Moto G32 test phone. Adds a clickable "AI-GM Mobile Mirror" entry to the
# app menu; the app lives in the system tray so closing the scrcpy window does
# not lose the connection. Quit from the tray menu tears down the SSH tunnel.
#
# Usage:  bash setup-laptop-mirror.sh
# Requires: Debian/Ubuntu (tested on 24.04), passwordless SSH from this user
#           to claude@192.168.1.19, sudo (will prompt once for password).
set -euo pipefail

ADB_HOST="192.168.1.19"
ADB_USER="claude"
TUNNEL_PORT=27183
SCRCPY_VERSION="v4.0"
SCRCPY_TARBALL="scrcpy-linux-x86_64-${SCRCPY_VERSION}.tar.gz"
SCRCPY_URL="https://github.com/Genymobile/scrcpy/releases/download/${SCRCPY_VERSION}/${SCRCPY_TARBALL}"
SCRCPY_SHA_URL="https://github.com/Genymobile/scrcpy/releases/download/${SCRCPY_VERSION}/SHA256SUMS.txt"

TRAY_PATH="/usr/local/bin/aigm-mobile-mirror-tray"
WRAPPER_PATH="/usr/local/bin/aigm-mobile-mirror"   # kept as a CLI shim
DESKTOP_PATH="${HOME}/.local/share/applications/aigm-mobile-mirror.desktop"
LOG_DIR="${HOME}/.local/share/aigm-mobile-mirror"

# Source the tray app from next to this script.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRAY_SOURCE="${HERE}/aigm-mobile-mirror-tray.py"

say()  { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '   \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- prereq checks ---------------------------------------------------------

say "Prerequisite checks"
[[ -f /etc/debian_version ]] || die "Not a Debian/Ubuntu system."
command -v curl >/dev/null || die "curl missing — apt install curl first."
[[ -f "$TRAY_SOURCE" ]] || die "Tray app source not found at $TRAY_SOURCE"
ok "Debian/Ubuntu base, curl present, tray source found"

ssh -o BatchMode=yes -o ConnectTimeout=5 "${ADB_USER}@${ADB_HOST}" \
    'echo ssh-from-laptop: OK' >/dev/null \
  || die "Passwordless SSH to ${ADB_USER}@${ADB_HOST} is required. Run ssh-copy-id first."
ok "Passwordless SSH to ${ADB_USER}@${ADB_HOST} works"

# --- apt deps --------------------------------------------------------------

say "Installing apt dependencies"
sudo apt-get update -qq
sudo apt-get install -y \
  adb openssh-client libnotify-bin wmctrl xdg-utils \
  python3-gi gir1.2-gtk-3.0
# AppIndicator: try Ayatana first (current Ubuntu), fall back to legacy.
if ! sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1 2>/dev/null; then
  sudo apt-get install -y gir1.2-appindicator3-0.1
fi
ok "adb $(adb --version | head -1 | awk '{print $5}'), python3-gi, AppIndicator binding"

# --- scrcpy (Genymobile prebuilt, current) ---------------------------------

say "Installing scrcpy ${SCRCPY_VERSION}"
if [[ -x /usr/local/bin/scrcpy ]] \
   && /usr/local/bin/scrcpy --version 2>&1 | head -1 | grep -q "${SCRCPY_VERSION#v}"; then
  ok "scrcpy ${SCRCPY_VERSION} already installed"
else
  # If an old apt scrcpy lurks (1.25 on Ubuntu 24.04 — broken with Android 14+),
  # remove it so PATH lookups land on /usr/local/bin/scrcpy.
  if dpkg -l scrcpy 2>/dev/null | grep -q '^ii'; then
    warn "Removing apt scrcpy (incompatible with modern Android)"
    sudo apt-get remove -y scrcpy
  fi

  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT
  pushd "$tmpdir" >/dev/null
  curl -sLO "$SCRCPY_URL"
  curl -sLO "$SCRCPY_SHA_URL"
  grep "$SCRCPY_TARBALL" SHA256SUMS.txt | sha256sum -c - \
    || die "scrcpy tarball SHA256 mismatch — refusing to install"
  ok "SHA256 verified"
  sudo rm -rf /opt/scrcpy
  sudo mkdir -p /opt/scrcpy
  sudo tar -xzf "$SCRCPY_TARBALL" -C /opt/scrcpy --strip-components=1
  sudo ln -sf /opt/scrcpy/scrcpy /usr/local/bin/scrcpy
  popd >/dev/null
  hash -r
  ok "scrcpy installed: $(scrcpy --version | head -1)"
fi

# --- tray app --------------------------------------------------------------

say "Installing tray app at ${TRAY_PATH}"
sudo install -m 0755 "$TRAY_SOURCE" "$TRAY_PATH"
ok "Tray app installed"

# --- CLI shim --------------------------------------------------------------

say "Installing CLI shim at ${WRAPPER_PATH}"
sudo tee "$WRAPPER_PATH" >/dev/null <<EOF
#!/usr/bin/env bash
# CLI entry point — just runs the tray app.
exec "${TRAY_PATH}" "\$@"
EOF
sudo chmod 755 "$WRAPPER_PATH"
ok "CLI shim installed (run 'aigm-mobile-mirror' from a terminal)"

# --- desktop launcher ------------------------------------------------------

say "Creating desktop launcher at ${DESKTOP_PATH}"
mkdir -p "$(dirname "$DESKTOP_PATH")" "$LOG_DIR"
ICON_PATH="/opt/scrcpy/scrcpy.png"
[[ -f "$ICON_PATH" ]] || ICON_PATH="phone"

cat > "${DESKTOP_PATH}" <<EOF
[Desktop Entry]
Type=Application
Version=1.1
Name=AI-GM Mobile Mirror
GenericName=Phone Mirror
Comment=Mirror the Moto G32 test phone via the lab ADB server (192.168.1.19)
Exec=${TRAY_PATH}
Icon=${ICON_PATH}
Terminal=false
Categories=Development;Network;
Keywords=scrcpy;android;phone;moto;aigm;
StartupNotify=true
SingleMainWindow=true
EOF
chmod 644 "${DESKTOP_PATH}"

if command -v update-desktop-database >/dev/null; then
  update-desktop-database -q "$(dirname "$DESKTOP_PATH")" 2>/dev/null || true
fi
ok "Launcher installed (refresh app menu — you may need to log out/in once)"

# --- self-test -------------------------------------------------------------

say "Self-test"
[[ -x "${TRAY_PATH}" ]]    && ok "tray app is executable"
[[ -x "${WRAPPER_PATH}" ]] && ok "CLI shim is executable"
[[ -r "${DESKTOP_PATH}" ]] && ok "desktop entry readable"
desktop-file-validate "${DESKTOP_PATH}" >/dev/null 2>&1 \
  && ok ".desktop file is valid" \
  || warn ".desktop file failed validation (non-fatal)"

# Confirm the Python imports work before the user clicks
python3 -c '
import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as A
    print("indicator: AyatanaAppIndicator3")
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as A
    print("indicator: AppIndicator3 (legacy)")
from gi.repository import Gtk
print("gtk:", Gtk._version)
' && ok "Python GI bindings OK"

if ping -c 1 -W 2 "${ADB_HOST}" >/dev/null 2>&1; then
  ok "${ADB_HOST} reachable"
  devices=$(ADB_SERVER_SOCKET="tcp:${ADB_HOST}:5037" /opt/scrcpy/adb devices 2>/dev/null \
            | awk '/\tdevice$/ {print $1}')
  if [[ -n "$devices" ]]; then
    ok "Phone attached to remote ADB server: $devices"
  else
    warn "No phone attached to remote ADB server (rig might be off)"
  fi
else
  warn "${ADB_HOST} not reachable right now — bring up the VPN; the app will tell you when you click"
fi

cat <<EOF

────────────────────────────────────────────────────
 Done. Open the app menu and search "AI-GM Mobile Mirror".
 The app sits in your system tray. Close the scrcpy window
 and the tray icon survives — click it to re-open.
 Quit from the tray menu closes the SSH tunnel cleanly.

 CLI:                 ${WRAPPER_PATH}
 Tray app:            ${TRAY_PATH}
 Logs:                ${LOG_DIR}/tray.log
────────────────────────────────────────────────────
EOF
