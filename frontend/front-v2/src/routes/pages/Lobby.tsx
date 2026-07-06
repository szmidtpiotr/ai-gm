import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle,
  CircleDashed,
  CircleNotch,
  Copy,
  Crown,
  HourglassMedium,
  LinkSimple,
  Play,
  Plus,
  ShareNetwork,
  UserPlus,
  X,
} from "@phosphor-icons/react";
import {
  useDeclineLobby,
  useInviteByUsername,
  useInviteLink,
  useKickPlayer,
  useLobby,
  useStartLobby,
} from "@/hooks/useLobby";
import { formatMinutes, type LobbyMember } from "@/lib/multiplayer";
import { cn } from "@/lib/utils";

// FE15 (#1264) — F-13 Lobby MP. Makieta 1:1: temp-img/design-concepts/zar9-lobby.html.
// Sloty drużyny (gospodarz + gracze + puste), ready, zaproszenie (kod/link), timer,
// start (tylko gospodarz). Polling 5 s (useLobby). Start → /gra/:id.
export default function Lobby() {
  const { campaignId: raw } = useParams();
  const campaignId = raw ? Number(raw) : undefined;
  const navigate = useNavigate();
  const lobby = useLobby(campaignId);

  const invite = useInviteByUsername(campaignId ?? 0);
  const inviteLink = useInviteLink(campaignId ?? 0);
  const kick = useKickPlayer(campaignId ?? 0);
  const start = useStartLobby(campaignId ?? 0);
  const decline = useDeclineLobby(campaignId ?? 0);

  const [username, setUsername] = useState("");
  const [linkUrl, setLinkUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [startErr, setStartErr] = useState<string | null>(null);

  // Gospodarz wystartował → wszyscy do gry (backend zmienia lobby_status).
  useEffect(() => {
    if (lobby.data?.lobby_status === "started" && campaignId) {
      navigate(`/gra/${campaignId}`, { replace: true });
    }
  }, [lobby.data?.lobby_status, campaignId, navigate]);

  if (!campaignId) return null;
  if (lobby.isLoading) return <LobbyLoader />;
  if (lobby.isError || !lobby.data) {
    return (
      <div className="py-16 text-center font-serif text-prose text-text-2">
        Nie znaleziono drużyny. Wróć do listy kampanii.
      </div>
    );
  }

  const d = lobby.data;
  const timerMin = d.round_timer_minutes || d.round_timer_hours * 60;
  const empties = Math.max(0, d.max_players - d.members.length);
  const canStart = d.accepted_count >= 2;

  async function genLink() {
    const res = await inviteLink.mutateAsync();
    setLinkUrl(`${location.origin}/v2/?join=${res.token}`);
  }

  function copyCode() {
    const text = linkUrl ?? "";
    if (!text) return;
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function doStart() {
    setStartErr(null);
    try {
      await start.mutateAsync();
      navigate(`/gra/${campaignId}`, { replace: true });
    } catch (e) {
      setStartErr(e instanceof Error ? e.message : "Nie udało się rozpocząć");
    }
  }

  async function doLeave() {
    if (!confirm("Opuścić drużynę? Stracisz swoje miejsce w sesji.")) return;
    try {
      await decline.mutateAsync();
    } catch {
      /* i tak wychodzimy z ekranu */
    }
    navigate("/bohaterowie");
  }

  return (
    <div className="-mx-4 -my-4 flex min-h-[calc(100dvh-3.5rem)] flex-col">
      {/* Nagłówek drużyny — makieta: back · tytuł/podtytuł · timer */}
      <header className="flex items-center gap-2.5 border-b border-line bg-surface px-4 py-3">
        <button
          onClick={() => navigate(-1)}
          aria-label="Wstecz"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-bg text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow"
        >
          <ArrowLeft size={17} />
        </button>
        <div className="min-w-0 flex-1">
          <div className="truncate font-serif text-title font-semibold text-text">
            Drużyna: {d.title}
          </div>
          <div className="font-ui text-micro text-text-3">
            Współpraca · {d.max_players} miejsc
          </div>
        </div>
        <div className="flex items-center gap-1.5 rounded-pill border border-line-ember bg-[rgba(255,122,61,.08)] px-3 py-1.5 font-mono text-label text-ember-glow">
          <HourglassMedium size={15} /> {formatMinutes(timerMin)}
        </div>
      </header>

      <div className="mx-auto w-full max-w-[640px] flex-1 px-4 py-5">
        <SectionHead
          label="Drużyna"
          count={`${d.accepted_count} / ${d.max_players} gotowych`}
        />

        {d.members.map((m) => (
          <Slot
            key={m.user_id}
            m={m}
            canKick={d.is_host && m.role !== "owner"}
            onKick={() => kick.mutate(m.user_id)}
          />
        ))}
        {Array.from({ length: empties }).map((_, i) => (
          <EmptySlot key={`empty-${i}`} />
        ))}

        {/* Zaproszenie — gospodarz: kod/link + username; gość: informacja */}
        {d.is_host ? (
          <div className="my-4 rounded-lg border border-line bg-surface p-3.5">
            <div className="mb-2.5 flex items-center gap-1.5 font-ui text-label text-text-2">
              <LinkSimple weight="fill" className="text-ember" size={16} /> Zaproś do
              drużyny
            </div>

            {/* Zaproszenie po nazwie użytkownika */}
            <div className="mb-2.5 flex gap-2">
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="@nazwa gracza"
                className="min-w-0 flex-1 rounded-md border border-line bg-bg px-3 py-2.5 font-ui text-label text-text outline-none placeholder:text-text-3 focus:border-line-ember"
              />
              <button
                onClick={() => {
                  const u = username.trim().replace(/^@/, "");
                  if (u) invite.mutate(u, { onSuccess: () => setUsername("") });
                }}
                disabled={invite.isPending || !username.trim()}
                className="flex shrink-0 items-center gap-1.5 rounded-md border border-line-ember bg-[rgba(255,122,61,.1)] px-3.5 font-ui text-label font-semibold text-ember-glow disabled:opacity-40"
              >
                <UserPlus size={15} /> Zaproś
              </button>
            </div>
            {invite.isError && (
              <div className="mb-2 font-ui text-micro text-danger">
                {(invite.error as Error)?.message}
              </div>
            )}
            {invite.isSuccess && (
              <div className="mb-2 font-ui text-micro text-success">
                ✓ Zaproszono
              </div>
            )}

            {/* Kod / link */}
            {linkUrl ? (
              <div className="flex gap-2">
                <button
                  onClick={copyCode}
                  className="flex min-w-0 flex-1 items-center justify-between gap-2 rounded-md border border-line bg-bg px-3.5 py-2.5 text-left font-mono text-label text-text"
                >
                  <span className="truncate">{linkUrl}</span>
                  <Copy className="shrink-0 text-text-3" size={16} />
                </button>
                <button
                  onClick={() => {
                    if (navigator.share) navigator.share({ url: linkUrl }).catch(() => {});
                    else copyCode();
                  }}
                  className="flex shrink-0 items-center gap-1.5 rounded-md border border-line-ember bg-[rgba(255,122,61,.1)] px-3.5 font-ui text-label font-semibold text-ember-glow"
                >
                  <ShareNetwork size={15} /> {copied ? "Skopiowano" : "Udostępnij"}
                </button>
              </div>
            ) : (
              <button
                onClick={genLink}
                disabled={inviteLink.isPending}
                className="flex w-full items-center justify-center gap-2 rounded-md border border-line bg-bg py-2.5 font-ui text-label text-text-2 transition-colors hover:border-line-ember hover:text-ember-glow disabled:opacity-40"
              >
                <LinkSimple size={15} />
                {inviteLink.isPending ? "Generowanie…" : "Wygeneruj link zaproszenia"}
              </button>
            )}
          </div>
        ) : (
          <div className="my-4 rounded-lg border border-line bg-surface p-3.5 text-center font-ui text-label text-text-2">
            Czekasz, aż gospodarz rozpocznie sesję…
          </div>
        )}
      </div>

      {/* Stopka — start (gospodarz) / opuść (gość) */}
      <footer
        className="sticky bottom-0 border-t border-line bg-surface px-4 py-3"
        style={{ paddingBottom: "max(12px, var(--sa-bottom))" }}
      >
        <div className="mx-auto w-full max-w-[640px]">
          {d.is_host ? (
            <>
              <button
                onClick={doStart}
                disabled={!canStart || start.isPending}
                className={cn(
                  "flex w-full items-center justify-center gap-2 rounded-lg py-3.5 font-ui text-body font-semibold text-white",
                  "bg-gradient-to-br from-[#d1602c] to-ember shadow-[0_0_18px_rgba(255,122,61,.35)]",
                  "disabled:opacity-40 disabled:shadow-none",
                )}
              >
                <Play weight="fill" size={18} /> Rozpocznij grę
              </button>
              <div className="mt-2 text-center font-ui text-micro text-text-3">
                {startErr
                  ? <span className="text-danger">{startErr}</span>
                  : canStart
                    ? `${d.accepted_count} graczy gotowych`
                    : `Potrzeba min. 2 graczy (${d.accepted_count}/${d.max_players})`}
              </div>
            </>
          ) : (
            <button
              onClick={doLeave}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-line-danger py-3.5 font-ui text-body font-semibold text-danger-glow"
            >
              Opuść drużynę
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}

function SectionHead({ label, count }: { label: string; count: string }) {
  return (
    <div className="mb-3 mt-1 flex items-center gap-2.5 px-0.5">
      <span className="font-ui text-[10.5px] font-bold uppercase tracking-[0.2em] text-ember">
        {label}
      </span>
      <span className="font-ui text-micro text-text-3">{count}</span>
      <span className="h-px flex-1 bg-line-soft" />
    </div>
  );
}

function initials(m: LobbyMember): string {
  return (m.display_name || m.username || "?").charAt(0).toUpperCase();
}

function Slot({
  m,
  canKick,
  onKick,
}: {
  m: LobbyMember;
  canKick: boolean;
  onKick: () => void;
}) {
  const isOwner = m.role === "owner";
  const isSpectator = m.role === "spectator";
  const accepted = m.status === "accepted";
  const meta = isOwner
    ? "Gospodarz"
    : isSpectator
      ? "Widz"
      : accepted
        ? "Dołączył"
        : "Zaproszony…";

  return (
    <div className="mb-2.5 flex items-center gap-3 rounded-lg border border-line bg-player-card px-3.5 py-3">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-line-ember bg-[radial-gradient(circle_at_40%_35%,rgba(255,122,61,.2),#241c13)] font-serif text-title text-ember-glow">
        {initials(m)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 truncate font-serif text-body font-semibold text-text">
          {m.display_name}
          {isOwner && (
            <span className="inline-flex items-center gap-1 rounded-pill border border-line-mech px-2 py-0.5 font-ui text-[9px] font-bold uppercase tracking-wider text-gold">
              <Crown weight="fill" size={9} /> Gospodarz
            </span>
          )}
        </div>
        <div className="font-ui text-micro text-text-2">{meta}</div>
      </div>
      {accepted ? (
        <span className="flex shrink-0 items-center gap-1.5 font-ui text-micro font-semibold text-success">
          <CheckCircle weight="fill" size={16} /> Gotowy
        </span>
      ) : (
        <span className="flex shrink-0 items-center gap-1.5 font-ui text-micro font-semibold text-text-3">
          <CircleDashed size={16} /> Czeka…
        </span>
      )}
      {canKick && (
        <button
          onClick={onKick}
          aria-label="Wyrzuć gracza"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-text-3 transition-colors hover:text-danger"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}

function EmptySlot() {
  return (
    <div className="mb-2.5 flex items-center gap-3 rounded-lg border border-dashed border-line bg-player-card px-3.5 py-3 opacity-75">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-dashed border-line bg-surface text-text-3">
        <Plus size={18} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-serif text-body font-semibold text-text-3">
          Wolne miejsce
        </div>
        <div className="font-ui text-micro text-text-3">Zaproś kompana</div>
      </div>
    </div>
  );
}

function LobbyLoader() {
  return (
    <div className="flex items-center justify-center gap-2 py-20 text-text-3">
      <CircleNotch className="animate-spin" size={22} />
      <span className="font-ui text-body">Wczytywanie drużyny…</span>
    </div>
  );
}
