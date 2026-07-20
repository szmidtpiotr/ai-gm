"""Stage 11-C C2 — Email service via SMTP (config stored in app_config table)."""
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.logging import get_logger
from app.core.db_runtime import resolve_db_path

logger = get_logger(__name__)
DB_PATH = resolve_db_path()


def _get_smtp_config() -> dict:
    """Read SMTP settings from app_config. Returns empty strings if not set."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT key, value FROM game_config_meta WHERE key LIKE 'smtp_%'"
        ).fetchall()
        conn.close()
        return {r["key"]: (r["value"] or "") for r in rows}
    except Exception:
        return {}


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email. Returns True on success, False on failure (never raises)."""
    cfg = _get_smtp_config()
    host = cfg.get("smtp_host", "").strip()
    port = int(cfg.get("smtp_port", "587") or "587")
    username = cfg.get("smtp_username", "").strip()
    password = cfg.get("smtp_password", "").strip()
    from_name = cfg.get("smtp_from_name", "AI-GM").strip() or "AI-GM"
    from_addr = cfg.get("smtp_from_address", "").strip()
    use_tls = cfg.get("smtp_use_tls", "true").strip().lower() in ("true", "1", "yes")

    if not host or not from_addr:
        logger.warning("email_smtp_not_configured", to=to, subject=subject)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        if username and password:
            server.login(username, password)
        server.sendmail(from_addr, [to], msg.as_string())
        server.quit()
        logger.info("email_sent", to=to, subject=subject)
        return True
    except Exception as e:
        logger.error("email_send_failed", to=to, subject=subject, error=str(e))
        return False


def send_invite_email(
    to: str,
    inviter_name: str,
    message: str | None,
    invite_link: str,
    expires_hours: int = 72,
) -> bool:
    personal_msg = f"<p><em>\"{message}\"</em></p>" if message else ""
    html = f"""
    <html><body style="font-family:Georgia,serif;background:#0a0908;color:#c9a85c;padding:32px;">
      <div style="max-width:500px;margin:0 auto;background:#12100e;border:1px solid #3a2a0a;border-radius:8px;padding:32px;">
        <h1 style="color:#c9961a;font-size:1.6rem;margin-bottom:4px;">⚔ AI-GM</h1>
        <p style="color:#8a7050;margin-top:0;">Zaproszenie do gry</p>
        <hr style="border-color:#2a1a08;margin:16px 0;">
        <p><strong>{inviter_name}</strong> zaprasza Cię do świata AI-GM.</p>
        {personal_msg}
        <p style="margin-top:24px;">
          <a href="{invite_link}"
             style="display:inline-block;padding:12px 28px;background:#7a4a0a;color:#f0c050;
                    text-decoration:none;border-radius:6px;font-size:1rem;">
            ⚔ Wstąp do przygody
          </a>
        </p>
        <p style="color:#6a5030;font-size:0.85rem;margin-top:24px;">
          Link ważny {expires_hours} godziny. Możesz użyć go tylko raz.
        </p>
      </div>
    </body></html>
    """
    return send_email(to, f"{inviter_name} zaprasza Cię do AI-GM", html)


def send_verification_email(to: str, verify_link: str) -> bool:
    html = f"""
    <html><body style="font-family:Georgia,serif;background:#0a0908;color:#c9a85c;padding:32px;">
      <div style="max-width:500px;margin:0 auto;background:#12100e;border:1px solid #3a2a0a;border-radius:8px;padding:32px;">
        <h1 style="color:#c9961a;">⚔ AI-GM</h1>
        <p>Potwierdź swój adres email, aby móc kontynuować przygodę.</p>
        <p style="margin-top:24px;">
          <a href="{verify_link}"
             style="display:inline-block;padding:12px 28px;background:#7a4a0a;color:#f0c050;
                    text-decoration:none;border-radius:6px;">
            Potwierdź email
          </a>
        </p>
        <p style="color:#6a5030;font-size:0.85rem;margin-top:24px;">Link ważny 72 godziny.</p>
      </div>
    </body></html>
    """
    return send_email(to, "AI-GM — potwierdź swój adres email", html)


def send_password_reset_email(to: str, reset_link: str) -> bool:
    html = f"""
    <html><body style="font-family:Georgia,serif;background:#0a0908;color:#c9a85c;padding:32px;">
      <div style="max-width:500px;margin:0 auto;background:#12100e;border:1px solid #3a2a0a;border-radius:8px;padding:32px;">
        <h1 style="color:#c9961a;">⚔ AI-GM</h1>
        <p>Otrzymaliśmy prośbę o reset hasła dla Twojego konta.</p>
        <p style="margin-top:24px;">
          <a href="{reset_link}"
             style="display:inline-block;padding:12px 28px;background:#7a4a0a;color:#f0c050;
                    text-decoration:none;border-radius:6px;">
            Ustaw nowe hasło
          </a>
        </p>
        <p style="color:#6a5030;font-size:0.85rem;margin-top:24px;">
          Link ważny 2 godziny i może być użyty tylko raz.<br>
          Jeśli nie prosiłeś o reset — zignoruj tę wiadomość.
        </p>
      </div>
    </body></html>
    """
    return send_email(to, "AI-GM — reset hasła", html)


def send_test_email(to: str) -> bool:
    html = """
    <html><body style="font-family:Georgia,serif;background:#0a0908;color:#c9a85c;padding:32px;">
      <div style="max-width:500px;margin:0 auto;background:#12100e;border:1px solid #3a2a0a;border-radius:8px;padding:32px;">
        <h1 style="color:#c9961a;">⚔ AI-GM</h1>
        <p>Testowy email z konfiguracji SMTP.</p>
        <p style="color:#4caf78;">✓ Konfiguracja SMTP działa poprawnie.</p>
      </div>
    </body></html>
    """
    return send_email(to, "AI-GM — test konfiguracji SMTP", html)
