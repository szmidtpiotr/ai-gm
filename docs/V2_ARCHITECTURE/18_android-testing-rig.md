# Android Testing Rig — Moto G32

End-to-end mobile test bench for AI-GM. One Android phone on the LAN, driven by
Appium running on the Claude VM (`.19`), with a live screen mirror to the user's
desktop (`.170`) so you can watch Claude play.

## Architecture

```
   ┌───────────────────────────────┐
   │  Moto G32 (Android)           │
   │  - Wireless debugging ON      │
   │  - Chrome installed           │
   │  - On LAN @ <PHONE_IP>:5555   │
   └────────────┬──────────────────┘
                │ ADB over WiFi
                ▼
   ┌───────────────────────────────┐
   │  Claude VM .19                │
   │  - adb server (listens :5037) │   ◀── Claude drives here
   │  - Appium server   (:4723)    │
   │  - Python test scripts        │
   └────────────┬──────────────────┘
                │ ADB_SERVER_SOCKET=tcp:192.168.1.19:5037
                ▼
   ┌───────────────────────────────┐
   │  User Desktop .170            │
   │  - scrcpy (live screen view)  │   ◀── User watches here
   └───────────────────────────────┘
```

Only `.19` holds the phone's ADB connection. `.170` borrows it through scrcpy.
This avoids the "ADB device offline because another host stole it" classic.

---

## Step 1 — One-time phone prep

On the **Moto G32**:

1. Settings → About phone → tap **Build number** 7× to unlock Developer options.
2. Settings → System → Developer options → enable **USB debugging** *and*
   **Wireless debugging**.
3. Open **Wireless debugging** → note the **IP & Port** at the top
   (e.g. `192.168.1.55:37123`). This port is the **persistent** port.
4. Tap **Pair device with pairing code** → note the **pairing IP:port**
   (different from the persistent one) and the **6-digit code**.

Leave that screen open — you'll feed the code into `.19` in Step 3.

### Recommended phone settings for an always-on test target

- Settings → Display → **Sleep**: 30 min (or never; keep it plugged in).
- Settings → Display → **Stay awake while charging**: ON (Developer options).
- Settings → Battery → exclude Chrome from battery optimization.
- Lock screen PIN: leave OFF, or set a known one and unlock it once before each
  session. Appium can wake the screen but cannot bypass secure-lock.
- WiFi: assign a **DHCP reservation** on your router so `<PHONE_IP>` doesn't
  change. Without this, you'll re-pair every few days.

---

## Step 2 — Install tooling on `.19`

Run on `.19` (or let Claude do it):

```bash
# adb + JDK + Node 20 LTS + python venv support
sudo apt update
sudo apt install -y adb default-jdk-headless curl python3-venv
# (Node 20+ is fine; install via NodeSource if your distro ships an older one)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Appium 2.x + UiAutomator2 driver
sudo npm install -g appium
appium driver install uiautomator2

# Minimal ANDROID_HOME shim — the uiautomator2 driver checks $ANDROID_HOME
# at session creation; it just needs platform-tools/adb to exist there.
mkdir -p ~/android-sdk/platform-tools
ln -sf /usr/bin/adb ~/android-sdk/platform-tools/adb

# Python client
python3 -m venv ~/appium-venv
~/appium-venv/bin/pip install Appium-Python-Client selenium
```

Verify:

```bash
adb --version           # Android Debug Bridge version 1.0.41 or newer
appium --version        # 2.x or 3.x
appium driver list --installed   # uiautomator2 present
```

---

## Step 3 — Pair the phone with `.19` (one-time)

On the **phone**, with **Pair device with pairing code** screen showing the
`<PAIR_IP>:<PAIR_PORT>` and 6-digit code:

```bash
# On .19
adb pair <PAIR_IP>:<PAIR_PORT>
# Paste the 6-digit code when prompted
```

You should see: `Successfully paired to ...`.

Then connect to the **persistent** port (from Step 1.3, **not** the pairing
port):

```bash
adb connect <PHONE_IP>:<PERSISTENT_PORT>
adb devices
# List of devices attached
# 192.168.1.55:37123    device
```

Sanity check:

```bash
adb shell getprop ro.product.model       # → "moto g32"
adb shell input keyevent KEYCODE_WAKEUP  # screen lights up
adb exec-out screencap -p > /tmp/shot.png  # screenshot
```

---

## Step 4 — Make the ADB server listenable from the LAN

By default `adb server` binds to `127.0.0.1:5037`, so `.170` can't reach it. We
need it on all interfaces.

Create a systemd user service on `.19`:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/adb-server.service <<'EOF'
[Unit]
Description=ADB server (LAN-reachable)
After=network.target

[Service]
ExecStart=/usr/bin/adb -a -P 5037 nodaemon server
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now adb-server.service
sudo loginctl enable-linger claude   # so it survives logout
```

Verify from `.19`:

```bash
ss -ltn | grep 5037   # should show 0.0.0.0:5037 or *:5037, not 127.0.0.1:5037
```

**Security**: this exposes ADB control to anything on your LAN. Fine on a home
network. If you later add untrusted devices, firewall port 5037 to
`192.168.1.0/24` or only to `.170`/`.101`:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 5037
```

After restarting the adb server you'll need to `adb connect <PHONE_IP>:<PORT>`
once more to re-attach the phone (pairing persists, the live connection does
not).

---

## Step 5 — Install scrcpy on `.170` for live view

On **user desktop `.170`** (Debian/Ubuntu).

> **Do not use `apt install scrcpy`** on Ubuntu 22.04 / 24.04. The repo version
> (scrcpy 1.25) was last released in 2022 and its server-side stub calls
> Android APIs (`SurfaceControl.createDisplay`, `IClipboard.addPrimaryClipChangedListener`)
> that were removed in Android 14+. It fails with `NoSuchMethodException` on
> any modern phone.
>
> The community `sisco311` snap is current (3.x) but ships with content slots
> (`gpu-2404`, `gnome-46-2404`) that aren't auto-connected and require manual
> `snap connect` + a disable/enable cycle to bind cleanly. Skippable.

Use Genymobile's official prebuilt Linux tarball — self-contained, includes a
bundled `adb` and `scrcpy-server.jar` matched to the client:

```bash
# adb is still useful as a standalone command
sudo apt install -y adb

cd /tmp
LATEST=$(curl -sIL https://github.com/Genymobile/scrcpy/releases/latest | \
         grep -i '^location:' | tail -1 | grep -oE 'v[0-9.]+$')
curl -LO "https://github.com/Genymobile/scrcpy/releases/download/${LATEST}/scrcpy-linux-x86_64-${LATEST}.tar.gz"
curl -LO "https://github.com/Genymobile/scrcpy/releases/download/${LATEST}/SHA256SUMS.txt"
grep "scrcpy-linux-x86_64-${LATEST}.tar.gz" SHA256SUMS.txt | sha256sum -c -

sudo rm -rf /opt/scrcpy
sudo mkdir -p /opt/scrcpy
sudo tar -xzf "scrcpy-linux-x86_64-${LATEST}.tar.gz" -C /opt/scrcpy --strip-components=1
sudo ln -sf /opt/scrcpy/scrcpy /usr/local/bin/scrcpy

scrcpy --version   # should be 4.x or newer
```

Run scrcpy pointing at the remote adb server on `.19`:

```bash
ADB_SERVER_SOCKET=tcp:192.168.1.19:5037 scrcpy --max-size 1280 --no-audio
```

If SDL complains about Wayland on Ubuntu 24.04, force X11:

```bash
SDL_VIDEODRIVER=x11 ADB_SERVER_SOCKET=tcp:192.168.1.19:5037 scrcpy --max-size 1280 --no-audio
```

A window opens mirroring the phone. You can also **interact** with it
(mouse-as-touch, keyboard input). Useful flags:

- `--no-control` — view-only, can't accidentally tap.
- `--record session.mp4` — record the session.
- `-S` — turn off the phone's own display (saves battery; mirror still works).
- `--shortcut-mod=lalt` — change scrcpy hotkeys if Alt clashes.

Make a desktop shortcut so you don't retype the env var each time.

---

## Step 6 — Sanity-check Appium end-to-end

On `.19`, start the Appium server (in a `tmux` or systemd unit):

```bash
appium --address 0.0.0.0 --port 4723
```

In another shell on `.19`:

```bash
source ~/appium-venv/bin/activate
python3 - <<'PY'
from appium import webdriver
from appium.options.android import UiAutomator2Options

opts = UiAutomator2Options()
opts.platform_name = "Android"
opts.device_name = "moto g32"
opts.udid = "192.168.1.55:37123"   # ← your phone
opts.automation_name = "UiAutomator2"
opts.no_reset = True

driver = webdriver.Remote("http://127.0.0.1:4723", options=opts)
print("Connected. Current activity:", driver.current_activity)
driver.press_keycode(26)   # power button → toggles screen
driver.quit()
PY
```

If scrcpy is open on `.170`, you should see the screen react. That confirms the
full chain: `.19` Python → Appium → adb server on `.19` → phone, with `.170`
observing read-only.

---

## Step 7 — Play AI-GM as a player on the phone

A minimal Python script that opens Chrome on the phone, navigates to the DEV
URL, logs in, and submits one turn.

Save as `~/aigm-mobile-test/play_one_turn.py`:

```python
#!/usr/bin/env python3
"""Drive the AI-GM player UI on the Moto G32 via Appium + Android Chrome."""
import time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PHONE_UDID = "192.168.1.55:37123"
DEV_URL = "https://aigm-dev.studio-colorbox.com/"
USERNAME = "test_player"
PASSWORD = "..."

opts = UiAutomator2Options()
opts.platform_name = "Android"
opts.udid = PHONE_UDID
opts.automation_name = "UiAutomator2"
opts.browser_name = "Chrome"             # ← mobile-web mode
opts.chromedriver_autodownload = True
opts.no_reset = True

driver = webdriver.Remote("http://127.0.0.1:4723", options=opts)
wait = WebDriverWait(driver, 20)

try:
    driver.get(DEV_URL)

    wait.until(EC.presence_of_element_located((By.ID, "loginUsername"))).send_keys(USERNAME)
    driver.find_element(By.ID, "loginPassword").send_keys(PASSWORD)
    driver.find_element(By.ID, "loginBtn").click()

    composer = wait.until(EC.presence_of_element_located((By.ID, "turnInput")))
    composer.send_keys("Rozglądam się dookoła.")
    driver.find_element(By.ID, "sendTurnBtn").click()

    # wait for narrator response to render
    wait.until(lambda d: "turn-card" in d.page_source)
    print("Turn submitted and response received.")
    time.sleep(2)   # let scrcpy capture the final frame
finally:
    driver.quit()
```

Run:

```bash
source ~/appium-venv/bin/activate
python3 ~/aigm-mobile-test/play_one_turn.py
```

The IDs above (`loginUsername`, `turnInput`, `sendTurnBtn`) are placeholders —
inspect the real frontend and adjust. With scrcpy open you can watch each tap
in real time.

> Note: the element IDs in the script need to match `frontend/index.html` / the
> player UI in `frontend/front/`. First time you wire this up, run a quick
> `driver.page_source[:2000]` print to find the actual selectors and update.

---

## Step 8 — Optional: pin Appium as a service too

So you don't need a `tmux` for it:

```bash
cat > ~/.config/systemd/user/appium.service <<'EOF'
[Unit]
Description=Appium server
After=adb-server.service
Requires=adb-server.service

[Service]
Environment="ANDROID_HOME=/home/claude/android-sdk"
Environment="ANDROID_SDK_ROOT=/home/claude/android-sdk"
ExecStart=/usr/bin/appium --address 0.0.0.0 --port 4723
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now appium.service
```

---

## Day-to-day usage

| Action | Command |
|---|---|
| Re-connect phone after it dropped | `adb connect <PHONE_IP>:<PORT>` on `.19` |
| Check phone is online | `adb devices` on `.19` |
| Live view on `.170` | `ADB_SERVER_SOCKET=tcp:192.168.1.19:5037 scrcpy` |
| Restart Appium | `systemctl --user restart appium` on `.19` |
| Run a player script | `python3 ~/aigm-mobile-test/<script>.py` on `.19` |
| Wipe Chrome data between runs | `adb shell pm clear com.android.chrome` |
| Phone screenshot | `adb exec-out screencap -p > shot.png` |

---

## Troubleshooting

- **`adb devices` shows the phone as `offline`** — usually means the phone
  rebooted or WiFi flapped. Re-run `adb connect <PHONE_IP>:<PORT>`. If that
  fails, re-pair (Step 3).
- **`unauthorized`** — the pairing was wiped. Re-do Step 3.
- **scrcpy on `.170` says "no devices/emulators found"** — the
  `ADB_SERVER_SOCKET` env var didn't take effect. `echo $ADB_SERVER_SOCKET` to
  confirm; the adb server on `.19` is listening on `0.0.0.0:5037` (check with
  `ss -ltn`); your firewall isn't blocking 5037.
- **Appium "session not created: chromedriver doesn't support Chrome version
  X"** — `chromedriver_autodownload=True` usually handles this; if not, update
  Chrome on the phone *and* `appium driver run uiautomator2 download-chromedriver`.
- **Phone screen keeps locking mid-test** — "Stay awake while charging" off,
  or Chrome got force-killed by battery optimization. Re-check phone prep.
- **`adb -a` warns "cannot bind 'tcp:5037'"** — there's already a localhost-only
  adb server running. `adb kill-server` first, then start the systemd unit.

---

## Security recap

- ADB over WiFi + LAN-bound adb server = anyone on your LAN can take full
  control of the phone *and* of any other Android device that pairs with the
  same adb server. Keep it home-LAN only; firewall 5037 if you ever add
  untrusted clients.
- The phone is essentially rooted-for-test from `.19`'s perspective. Don't sign
  into personal Google accounts, banking apps, etc. on it. Treat it as a
  dedicated test device with throwaway accounts only.
- AI-GM DEV credentials embedded in scripts: keep these out of git
  (`.gitignore` the `aigm-mobile-test/` dir if you put it in the repo, or store
  outside `~/projects/`).
