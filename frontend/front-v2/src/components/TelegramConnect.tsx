import { useEffect, useRef, useState } from "react";
import { TelegramLogo, QrCode, CheckCircle, LinkSimple } from "@phosphor-icons/react";
import {
  createTelegramLink,
  getTelegramStatus,
  unlinkTelegram,
  isMobile,
  type TelegramLink,
} from "@/lib/notify";

// #883 (N1 of #602) — Telegram easy-click linking.
// Mobile: tap „Połącz" → opens t.me deep-link pre-filled with /start <token> → 1 tap.
// Desktop: shows a QR of the same deep-link to scan with the phone.
// After the tap the bot webhook binds chat_id; we poll status until connected.
export function TelegramConnect() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [link, setLink] = useState<TelegramLink | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getTelegramStatus()
      .then((s) => {
        setConnected(s.connected);
        setConfigured(s.configured);
      })
      .catch(() => setConnected(false));
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    let ticks = 0;
    pollRef.current = setInterval(async () => {
      ticks += 1;
      try {
        const s = await getTelegramStatus();
        if (s.connected) {
          setConnected(true);
          setLink(null);
          setQr(null);
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {
        /* keep polling */
      }
      if (ticks > 60 && pollRef.current) clearInterval(pollRef.current); // stop after ~3 min
    }, 3000);
  }

  async function onConnect() {
    setBusy(true);
    setErr(null);
    try {
      const l = await createTelegramLink();
      if (!l.configured || !l.deep_link) {
        setConfigured(false);
        setErr("Bot Telegram nie jest jeszcze skonfigurowany na serwerze.");
        return;
      }
      setLink(l);
      if (isMobile()) {
        window.open(l.deep_link, "_blank");
      } else {
        const QR = await import("qrcode");
        setQr(await QR.toDataURL(l.deep_link, { margin: 1, width: 200 }));
      }
      startPolling();
    } catch {
      setErr("Nie udało się wygenerować linku. Spróbuj ponownie.");
    } finally {
      setBusy(false);
    }
  }

  async function onUnlink() {
    setBusy(true);
    try {
      await unlinkTelegram();
      setConnected(false);
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }

  const iconBox =
    "flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md border border-line bg-bg";

  return (
    <div className="flex flex-col gap-2.5 rounded-md border border-line-soft bg-surface p-3.5">
      <div className="flex items-center gap-2.5">
        <span className={`${iconBox} text-[#229ED9]`}>
          <TelegramLogo size={20} weight="fill" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-ui text-body font-semibold text-text">Telegram</span>
          <span className="block font-ui text-micro text-text-3">
            Najpewniejszy kanał — działa też przy uśpionym telefonie
          </span>
        </span>
        {connected && (
          <span className="inline-flex items-center gap-1 rounded-pill border border-emerald-500/30 px-2.5 py-1 font-mono text-[9.5px] uppercase tracking-wide text-emerald-400">
            <CheckCircle size={12} weight="fill" /> Połączony
          </span>
        )}
      </div>

      {connected === false && (
        <>
          <button
            type="button"
            id="telegram-connect-btn"
            data-clog="telegram_connect"
            disabled={busy || configured === false}
            onClick={onConnect}
            className="inline-flex items-center justify-center gap-2 rounded-md border border-[#229ED9]/40 bg-[#229ED9]/[0.08] py-2.5 font-ui text-body font-semibold text-[#5cc3ee] disabled:opacity-50"
          >
            <LinkSimple size={16} /> Połącz Telegram
          </button>

          {link && qr && (
            <div className="flex flex-col items-center gap-1.5 rounded-md border border-line-soft bg-bg p-3">
              <span className="flex items-center gap-1.5 font-ui text-micro text-text-3">
                <QrCode size={13} /> Zeskanuj telefonem
              </span>
              <img src={qr} alt="Telegram QR" width={180} height={180} className="rounded" />
              <a
                href={link.deep_link ?? "#"}
                target="_blank"
                rel="noreferrer"
                className="break-all text-center font-mono text-[10px] text-[#5cc3ee] underline"
              >
                {link.deep_link}
              </a>
            </div>
          )}
          {link && !qr && (
            <p className="font-ui text-micro text-text-3">
              Otwarto Telegram — kliknij <b>START</b> w czacie. Czekam na połączenie…
            </p>
          )}
          {configured === false && (
            <p className="font-ui text-micro text-text-3">
              Bot niedostępny — powiadomienia Telegram będą aktywne po konfiguracji serwera.
            </p>
          )}
          {err && <p className="font-ui text-micro text-danger">{err}</p>}
        </>
      )}

      {connected && (
        <button
          type="button"
          id="telegram-unlink-btn"
          disabled={busy}
          onClick={onUnlink}
          className="self-start font-ui text-micro text-text-3 underline disabled:opacity-50"
        >
          Rozłącz
        </button>
      )}
    </div>
  );
}
