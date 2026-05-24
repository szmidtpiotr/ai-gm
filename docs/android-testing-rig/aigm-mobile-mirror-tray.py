#!/usr/bin/env python3
"""AI-GM Mobile Mirror — system-tray manager around an SSH tunnel + scrcpy.

Lifecycle:
  - On launch: open SSH tunnel to the lab adb-server, start scrcpy mirroring
    the test phone, show a tray icon.
  - Close the scrcpy window: the tray icon stays. Use it to reopen.
  - Quit (tray menu, or SIGTERM): terminate scrcpy AND close the SSH tunnel.

Singleton: a Unix domain socket lock prevents two instances. Re-launching the
desktop entry while one is already running simply notifies the user.
"""
from __future__ import annotations

import atexit
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

# Prefer the modern Ayatana indicator (current Ubuntu); fall back to the legacy one.
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # type: ignore
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator  # type: ignore

from gi.repository import GLib, Gtk  # noqa: E402

ADB_HOST = "192.168.1.19"
ADB_USER = "claude"
TUNNEL_PORT = 27183
ADB_PORT = 5037

ICON_RUNNING = "/opt/scrcpy/scrcpy.png"
ICON_IDLE = "phone"  # generic system icon when mirror not active

LOG_DIR = Path.home() / ".local/share/aigm-mobile-mirror"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "tray.log"
LOCK_PATH = f"\0aigm-mobile-mirror-{os.getuid()}"  # abstract Unix socket


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    try:
        with LOG_FILE.open("a") as f:
            f.write(line)
    except OSError:
        pass


def notify(message: str, urgency: str = "normal") -> None:
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-i", ICON_RUNNING,
             "AI-GM Mobile Mirror", message],
            check=False, timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def acquire_singleton() -> socket.socket | None:
    """Bind an abstract Unix socket as a lock. Returns the socket on success."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        s.bind(LOCK_PATH)
        return s
    except OSError:
        return None


class MirrorApp:
    def __init__(self) -> None:
        self.scrcpy_proc: subprocess.Popen | None = None
        self.tunnel_proc: subprocess.Popen | None = None
        self.tunnel_owned = False  # True if we started the SSH tunnel ourselves
        self._stopping = False

        self.indicator = AppIndicator.Indicator.new(
            "aigm-mobile-mirror",
            ICON_RUNNING if Path(ICON_RUNNING).exists() else ICON_IDLE,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("AI-GM Mobile Mirror")
        self.indicator.set_label("📱", "")

        self.show_item = Gtk.MenuItem(label="Show window")
        self.show_item.connect("activate", self.on_show)
        self.status_item = Gtk.MenuItem(label="status: starting…")
        self.status_item.set_sensitive(False)
        self.logs_item = Gtk.MenuItem(label="Open log folder")
        self.logs_item.connect("activate", self.on_open_logs)
        self.quit_item = Gtk.MenuItem(label="Quit (clears tunnel)")
        self.quit_item.connect("activate", self.on_quit)

        menu = Gtk.Menu()
        menu.append(self.show_item)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self.status_item)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self.logs_item)
        menu.append(self.quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)

        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, lambda *_: self.on_quit(None))
        signal.signal(signal.SIGTERM, lambda *_: self.on_quit(None))

        # Kick off the mirror right after the main loop starts
        GLib.idle_add(self._auto_start)

    # -- status display -----------------------------------------------------

    def _set_status(self, text: str) -> None:
        GLib.idle_add(self.status_item.set_label, f"status: {text}")

    # -- core flow ----------------------------------------------------------

    def _auto_start(self) -> bool:
        threading.Thread(target=self._start_mirror, daemon=True).start()
        return False

    def _ensure_tunnel(self) -> bool:
        # If something already listens on TUNNEL_PORT, reuse it (do not kill — not ours)
        try:
            with socket.create_connection(("127.0.0.1", TUNNEL_PORT), timeout=0.5):
                log(f"Reusing existing tunnel on :{TUNNEL_PORT}")
                self.tunnel_owned = False
                return True
        except (OSError, socket.timeout):
            pass

        log(f"Opening SSH tunnel to {ADB_USER}@{ADB_HOST}")
        self.tunnel_proc = subprocess.Popen(
            ["ssh", "-N",
             "-o", "BatchMode=yes",
             "-o", "ExitOnForwardFailure=yes",
             "-o", "ServerAliveInterval=15",
             "-o", "ServerAliveCountMax=3",
             "-L", f"{TUNNEL_PORT}:127.0.0.1:{TUNNEL_PORT}",
             f"{ADB_USER}@{ADB_HOST}"],
            stdin=subprocess.DEVNULL,
        )
        self.tunnel_owned = True
        for _ in range(30):
            if self.tunnel_proc.poll() is not None:
                log(f"SSH tunnel exited early (code {self.tunnel_proc.returncode})")
                self.tunnel_proc = None
                return False
            try:
                with socket.create_connection(("127.0.0.1", TUNNEL_PORT), timeout=0.3):
                    log("Tunnel ready")
                    return True
            except (OSError, socket.timeout):
                time.sleep(0.3)
        log("Tunnel did not open within timeout")
        return False

    def _phone_attached(self) -> bool:
        env = dict(os.environ, ADB_SERVER_SOCKET=f"tcp:{ADB_HOST}:{ADB_PORT}")
        try:
            out = subprocess.check_output(
                ["/opt/scrcpy/adb", "devices"], env=env, timeout=5, text=True
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
        return any(line.endswith("\tdevice") for line in out.splitlines())

    def _start_mirror(self) -> None:
        if self.scrcpy_proc and self.scrcpy_proc.poll() is None:
            log("scrcpy already running — show()")
            return

        self._set_status("connecting…")

        if not self._reachable():
            self._set_status("offline — check VPN")
            notify(f"Cannot reach {ADB_HOST}. Is the VPN up?", urgency="critical")
            return

        if not self._ensure_tunnel():
            self._set_status("tunnel failed")
            notify("SSH tunnel to the lab failed.", urgency="critical")
            return

        if not self._phone_attached():
            self._set_status("no phone")
            notify("No phone attached to the remote adb server.", urgency="critical")
            return

        env = dict(os.environ, ADB_SERVER_SOCKET=f"tcp:{ADB_HOST}:{ADB_PORT}")
        log("Launching scrcpy")
        self.scrcpy_proc = subprocess.Popen(
            ["scrcpy",
             f"--tunnel-port={TUNNEL_PORT}",
             "--window-title=AI-GM Mobile (Moto G32)",
             "--max-size=1280",
             "--no-audio"],
            env=env,
            stdin=subprocess.DEVNULL,
        )
        self._set_status("mirroring")
        threading.Thread(target=self._wait_scrcpy, daemon=True).start()

    def _wait_scrcpy(self) -> None:
        if self.scrcpy_proc is None:
            return
        rc = self.scrcpy_proc.wait()
        log(f"scrcpy exited (code {rc})")
        self.scrcpy_proc = None
        if self._stopping:
            return
        self._set_status("idle — click 'Show window' to reopen")

    def _reachable(self) -> bool:
        try:
            subprocess.run(["ping", "-c", "1", "-W", "2", ADB_HOST],
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=4)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    # -- menu handlers ------------------------------------------------------

    def on_show(self, _widget) -> None:
        if self.scrcpy_proc and self.scrcpy_proc.poll() is None:
            try:
                subprocess.run(["wmctrl", "-a", "AI-GM Mobile (Moto G32)"],
                               check=False, timeout=2)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            return
        threading.Thread(target=self._start_mirror, daemon=True).start()

    def on_open_logs(self, _widget) -> None:
        subprocess.Popen(["xdg-open", str(LOG_DIR)])

    def on_quit(self, _widget) -> None:
        log("Quit requested")
        self._stopping = True
        self.cleanup()
        try:
            Gtk.main_quit()
        except RuntimeError:
            pass

    # -- cleanup ------------------------------------------------------------

    def cleanup(self) -> None:
        if self.scrcpy_proc and self.scrcpy_proc.poll() is None:
            log("Terminating scrcpy")
            self.scrcpy_proc.terminate()
            try:
                self.scrcpy_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.scrcpy_proc.kill()
            self.scrcpy_proc = None
        if self.tunnel_owned and self.tunnel_proc and self.tunnel_proc.poll() is None:
            log("Closing SSH tunnel")
            self.tunnel_proc.terminate()
            try:
                self.tunnel_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.tunnel_proc.kill()
            self.tunnel_proc = None


def main() -> int:
    lock = acquire_singleton()
    if lock is None:
        notify("Already running — check your system tray.", urgency="low")
        log("Singleton lock held — another instance is running. Exiting.")
        return 0

    log("=== aigm-mobile-mirror tray starting ===")
    MirrorApp()
    try:
        Gtk.main()
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
